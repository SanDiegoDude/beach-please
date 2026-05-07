"""FastAPI app entry point for Beach, Please."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import beaches, chat


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Beach, Please",
        description="A sassy AI-powered US beach concierge.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(beaches.router, prefix="/api", tags=["beaches"])
    app.include_router(chat.router, prefix="/api", tags=["chat"])

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "vibe": "beach, please"}

    return app


app = create_app()
