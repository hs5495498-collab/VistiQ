"""Virtual try-on job endpoints (Phase 5 — experimental).

Ownership rule, identical to app/routes/wardrobe.py: every query that
reads, updates, or deletes a specific job filters by BOTH `id` AND
`user_id == current_user.id`, so a cross-user access attempt and a
genuinely nonexistent id both produce a plain 404.

Job creation never blocks on GPU inference. POST /tryon validates the
input, persists the uploaded person photo, and creates the job row with
status "pending" — then hands the actual worker call off to a
BackgroundTask (`_process_job`), which runs after the response is already
sent. Clients poll GET /tryon/{id} for status, exactly like the frontend's
tryon.ts does.
"""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, sessionmaker

from app.database import connection
from app.database.connection import get_db
from app.database.models import ClothingItem, TryOnJob, User
from app.schemas.tryon import TryOnJobResponse
from app.security.dependencies import get_current_user, require_csrf
from app.services import image_storage, tryon_storage, tryon_worker
from app.services.image_validation import read_and_validate_image

router = APIRouter(prefix="/tryon", tags=["tryon"])


def recover_interrupted_jobs(db: Session) -> int:
    """Called once at process startup (see app/main.py's lifespan). A job
    only ever sits at "pending"/"processing" while this process's own
    BackgroundTask is actively running it — every normal exit path
    (success, TryOnWorkerError, or an unexpected exception) already moves
    it to a terminal status before that task returns. The one case that
    doesn't go through any of those exit paths is the process itself
    dying mid-job (crash, kill, power loss) — any row still non-terminal
    from a *previous* run is therefore orphaned, not actually in
    progress, and would otherwise stay "pending"/"processing" forever
    with nothing left to ever finish it. Returns the number recovered."""
    orphaned = db.query(TryOnJob).filter(TryOnJob.status.in_(["pending", "processing"])).all()
    for job in orphaned:
        job.status = "failed"
        job.error_message = "Virtual try-on was interrupted by a server restart. Please try again."
        job.completed_at = datetime.utcnow()
    if orphaned:
        db.commit()
    return len(orphaned)

ALLOWED_CLOTH_TYPES = {"upper", "lower", "overall"}


def _get_owned_job_or_404(job_id: int, user_id: int, db: Session) -> TryOnJob:
    job = db.query(TryOnJob).filter(TryOnJob.id == job_id, TryOnJob.user_id == user_id).first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Try-on job {job_id} not found")
    return job


def _process_job(job_id: int, garment_image_bytes: bytes, garment_content_type: str, cloth_type: str) -> None:
    """Runs in the background, after the HTTP response for POST /tryon has
    already been sent. Opens its own DB session — the request-scoped one
    FastAPI gave the route handler is already closed by the time this
    runs. Every exit path (success, worker error, or an unexpected
    exception) leaves the job in a terminal status — never stuck at
    "processing" forever."""
    # Built from `connection.engine` read fresh here (NOT the module-level
    # `connection.SessionLocal`, which is bound once at import time) so
    # that tests monkeypatching `connection.engine` to an isolated test
    # database are actually honored by this background task too — it runs
    # outside FastAPI's request-scoped `Depends(get_db)` override system.
    task_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=connection.engine)
    db = task_session_factory()
    try:
        job = db.get(TryOnJob, job_id)
        if job is None:
            return  # job was deleted while queued — nothing to update

        job.status = "processing"
        db.commit()

        person_bytes = (tryon_storage.PERSON_IMAGES_DIR / job.person_image.rsplit("/", 1)[-1]).read_bytes()
        person_content_type = "image/png" if job.person_image.endswith(".png") else "image/jpeg"

        try:
            result_bytes = tryon_worker.run_tryon(
                person_bytes, person_content_type, garment_image_bytes, garment_content_type, cloth_type
            )
        except tryon_worker.TryOnWorkerError as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.utcnow()
            db.commit()
            return
        except Exception:
            # Never leak an internal exception's text to the client.
            job.status = "failed"
            job.error_message = "Virtual try-on failed unexpectedly. Please try again."
            job.completed_at = datetime.utcnow()
            db.commit()
            return

        job.result_image = tryon_storage.save_result_image(result_bytes)
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


@router.post(
    "",
    response_model=TryOnJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a virtual try-on job for one of the user's own wardrobe garments",
    dependencies=[Depends(require_csrf)],
)
async def create_tryon_job(
    background_tasks: BackgroundTasks,
    garment_item_id: int = Form(...),
    cloth_type: str = Form(...),
    person_image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if cloth_type not in ALLOWED_CLOTH_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"cloth_type must be one of {sorted(ALLOWED_CLOTH_TYPES)}.",
        )

    garment = (
        db.query(ClothingItem)
        .filter(ClothingItem.id == garment_item_id, ClothingItem.user_id == current_user.id)
        .first()
    )
    if garment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wardrobe item not found.")
    if not garment.image:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This wardrobe item has no photo.")

    garment_path = image_storage.UPLOADS_DIR / garment.image.rsplit("/", 1)[-1]
    if not garment_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wardrobe item photo not found.")

    person_raw_bytes, _person_image = await read_and_validate_image(person_image)
    person_url = tryon_storage.save_person_image(person_raw_bytes, person_image.content_type)

    job = TryOnJob(
        user_id=current_user.id,
        garment_item_id=garment.id,
        person_image=person_url,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if tryon_worker.is_worker_configured():
        garment_bytes = garment_path.read_bytes()
        garment_content_type = "image/png" if garment_path.suffix == ".png" else "image/jpeg"
        background_tasks.add_task(_process_job, job.id, garment_bytes, garment_content_type, cloth_type)
    else:
        # No background task needed — there is nothing to poll for; tell
        # the caller immediately rather than leaving the job at "pending"
        # forever. This is the honest "feature currently unavailable"
        # path described in docs/virtual-tryon.md.
        job.status = "failed"
        job.error_message = "Virtual try-on is currently unavailable: no GPU worker is configured."
        job.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(job)

    return job


@router.get("", response_model=list[TryOnJobResponse], summary="List the authenticated user's try-on jobs")
def list_tryon_jobs(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(TryOnJob)
        .filter(TryOnJob.user_id == current_user.id)
        .order_by(TryOnJob.id.desc())
        .all()
    )


@router.get(
    "/{job_id}",
    response_model=TryOnJobResponse,
    summary="Get a try-on job's status (only if it belongs to the authenticated user)",
)
def get_tryon_job(job_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_owned_job_or_404(job_id, current_user.id, db)


@router.get(
    "/results/{filename}",
    summary="Serve a generated try-on result image — only to the user who owns that job",
)
def get_tryon_result_image(
    filename: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not filename or "/" in filename or "\\" in filename or filename in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")

    image_url = f"{tryon_storage.RESULT_IMAGE_URL_PREFIX}/{filename}"
    owned = (
        db.query(TryOnJob)
        .filter(TryOnJob.result_image == image_url, TryOnJob.user_id == current_user.id)
        .first()
    )
    if owned is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")

    file_path = tryon_storage.RESULT_IMAGES_DIR / filename
    if not file_path.is_file() or file_path.resolve().parent != tryon_storage.RESULT_IMAGES_DIR.resolve():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")

    return FileResponse(file_path)


@router.delete(
    "/{job_id}",
    summary="Delete a try-on job and its stored images (only if it belongs to the authenticated user)",
    dependencies=[Depends(require_csrf)],
)
def delete_tryon_job(job_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _get_owned_job_or_404(job_id, current_user.id, db)
    person_image, result_image = job.person_image, job.result_image

    db.delete(job)
    db.commit()

    tryon_storage.delete_person_image(person_image)
    tryon_storage.delete_result_image(result_image)

    return {"message": f"Try-on job {job_id} deleted"}
