"""
Phase 4 authentication endpoints: register, login, logout, current user.

Cookie-based session auth: the frontend never manually attaches a token
the way a bearer-token API would — the browser attaches the HttpOnly
session cookie automatically on every same-site request, as long as the
frontend's fetch calls use `credentials: "include"` (see
vistiq-frontend/src/services/api.ts). For state-changing requests, the
frontend additionally reads the separate, non-HttpOnly CSRF cookie and
echoes it back as a header (see app/security/dependencies.py:require_csrf)
— that's the one piece of "attaching something manually" this design
needs, and it's handled once, centrally, in api.ts.

SameSite=Lax (not Strict, not None) is the deliberate choice: Strict would
also block the cookie on some legitimate same-site top-level navigations;
None would require Secure=true unconditionally, which breaks local HTTP
dev (see app/security/sessions.py's COOKIE_SECURE). Lax already blocks the
cross-site POST/fetch requests CSRF attacks rely on, while still working
correctly for this app's actual usage pattern.

Known, documented limitation: register/login are NOT behind require_csrf
below — there's no prior session to protect at that point (standard
practice), but it does leave a theoretical "login CSRF" (tricking a victim
into authenticating into an attacker-chosen account) unaddressed. Low
severity for a local PBL project.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserPublic
from app.security.dependencies import get_current_user, require_csrf
from app.security.passwords import hash_password, normalize_email, validate_password_strength, verify_password
from app.security.sessions import (
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    SESSION_TTL_DAYS,
    create_session,
    generate_csrf_token,
    invalidate_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_SESSION_MAX_AGE_SECONDS = SESSION_TTL_DAYS * 24 * 60 * 60


def _set_auth_cookies(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=_SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )
    # NOT HttpOnly — the frontend must be able to read this one to echo it
    # back as the X-CSRF-Token header (the whole point of double-submit).
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_csrf_token(),
        max_age=_SESSION_MAX_AGE_SECONDS,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)

    problems = validate_password_strength(payload.password)
    if problems:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=" ".join(problems))

    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists."
        )

    user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    # Auto-login after registration — one less round trip, and the new
    # session is freshly created either way (rotation applies here too).
    token, _expires_at = create_session(db, user.id)
    _set_auth_cookies(response, token)
    return user


@router.post("/login", response_model=UserPublic)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    user = db.query(User).filter(User.email == email).first()

    # Always the same generic error whether the account doesn't exist or
    # the password is wrong — never let a client distinguish which one it
    # was.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    # Session rotation: a fresh session row every login, never a reused one.
    token, _expires_at = create_session(db, user.id)
    _set_auth_cookies(response, token)
    return user


@router.post("/logout", dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    invalidate_session(db, raw_token)
    _clear_auth_cookies(response)
    return {"message": "Logged out."}


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return current_user
