from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.connection import init_db
from app.routes.auth import router as auth_router
from app.routes.clothing_analysis import router as clothing_analysis_router
from app.routes.recommendation import router as recommendation_router
from app.routes.tryon import router as tryon_router
from app.routes.wardrobe import router as wardrobe_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="VISTIQ API",
    description="Backend API for the VISTIQ AI wardrobe recommendation system.",
    version="0.1.0",
    lifespan=lifespan,
)

# Local Vite dev server origins only — tighten/extend this list as real
# deployment origins are introduced in a later stage.
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "VISTIQ API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


app.include_router(auth_router)
app.include_router(wardrobe_router)
app.include_router(recommendation_router)
app.include_router(clothing_analysis_router)
app.include_router(tryon_router)

# Phase 4: uploaded wardrobe photos are served through an authenticated,
# ownership-checked route (app/routes/wardrobe.py:get_wardrobe_image()),
# registered above as part of wardrobe_router — NOT a public StaticFiles
# mount. A blanket mount would let anyone who guesses/intercepts a
# filename view another user's private photo; see that route's docstring.
