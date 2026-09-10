from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .ai.engine import ai_engine
from .config import settings
from .db import init_db
from .routers import (
    ai_router,
    auth_router,
    evidence_router,
    inspector_router,
    intel_router,
    investigations_router,
    reports_router,
)
from .services.embeddings import backend_in_use

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("prism")

app = FastAPI(
    title="PRISM API",
    version="1.0.0",
    description=(
        "PRISM — AI-powered food-safety early-warning and investigation platform. "
        "AI produces signals only; all enforcement decisions are made by humans."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-PRISM-SHA256", "X-PRISM-Integrity-Verified"],
)

for r in (
    auth_router.router,
    reports_router.router,
    evidence_router.router,
    ai_router.router,
    intel_router.router,
    inspector_router.router,
    investigations_router.router,
):
    app.include_router(r)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    log.info(
        "PRISM API ready | demo_mode=%s ai_provider=%s storage=%s db=%s",
        settings.demo_mode,
        ai_engine.mode,
        settings.storage_backend,
        settings.database_url.split("://")[0],
    )
    if settings.demo_mode:
        from .seed import seed_if_empty

        seed_if_empty()


@app.get("/")
def root():
    return {"name": "PRISM API", "version": "1.0.0", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "demo_mode": settings.demo_mode,
        "ai_provider": ai_engine.mode,
        "storage_backend": settings.storage_backend,
        "embedding_backend": backend_in_use(),
    }
