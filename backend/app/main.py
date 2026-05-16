from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api import router

app = FastAPI(
    title="VJob",
    description="AI-powered job intelligence agent for software engineers",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}