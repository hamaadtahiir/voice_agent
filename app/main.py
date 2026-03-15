"""FastAPI application factory and entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db.engine import init_db
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler: startup and shutdown logic."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("inbound_bot")

    # Initialise database tables in dev/debug mode (production uses Alembic)
    if settings.DEBUG:
        logger.info("DEBUG mode: creating database tables")
        await init_db()

    # Start the APScheduler background scheduler (reminders, re-engagement, etc.)
    start_scheduler()
    logger.info("Background scheduler started")

    yield

    # Shutdown
    stop_scheduler()
    logger.info("Background scheduler stopped")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Inbound Bot",
        description="AI-powered lead qualification and scheduling",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Static files for admin UI
    # ------------------------------------------------------------------
    static_dir = os.path.join(os.path.dirname(__file__), "admin_ui", "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # ------------------------------------------------------------------
    # Widget static assets (widget.js, widget.css)
    # ------------------------------------------------------------------
    widget_dir = os.path.join(os.path.dirname(__file__), "widget")
    if os.path.isdir(widget_dir):
        app.mount("/widget-assets", StaticFiles(directory=widget_dir), name="widget-assets")

    # ------------------------------------------------------------------
    # Upload directory
    # ------------------------------------------------------------------
    uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    # ------------------------------------------------------------------
    # API routers
    # ------------------------------------------------------------------
    from app.api import (
        admin,
        appointments,
        businesses,
        chat,
        dashboard,
        email_inbound,
        health,
        leads,
        vapi,
        whatsapp,
        widget,
    )

    app.include_router(health.router, tags=["Health"])
    app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
    app.include_router(businesses.router, prefix="/api/businesses", tags=["Businesses"])
    app.include_router(leads.router, prefix="/api/leads", tags=["Leads"])
    app.include_router(appointments.router, prefix="/api/appointments", tags=["Appointments"])
    app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
    app.include_router(chat.router, tags=["Chat"])
    app.include_router(whatsapp.router, tags=["WhatsApp"])
    app.include_router(vapi.router, tags=["Vapi"])
    app.include_router(email_inbound.router, tags=["Email"])
    app.include_router(widget.router, tags=["Widget"])

    # ------------------------------------------------------------------
    # Admin UI (Jinja2 template pages)
    # ------------------------------------------------------------------
    from app.admin_ui.routes import router as admin_ui_router

    app.include_router(admin_ui_router)

    return app


app = create_app()
