"""Admin UI page routes serving Jinja2 templates.

All pages (except /admin/login) are rendered as full HTML pages that load data
client-side via ``authFetch`` (from admin.js), using the JWT stored in the
``admin_token`` cookie.  When an ``HX-Request`` header is present the handler
returns only the partial HTML fragment (``{% block content %}`` only) instead of
the full page layout, enabling htmx-driven navigation.

Authentication for admin pages is handled client-side: admin.js checks for the
``admin_token`` cookie on DOMContentLoaded and redirects to /admin/login if
missing.  The templates therefore do *not* need server-side auth guards -- the
JSON API endpoints that supply data already enforce auth.
"""

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

router = APIRouter()

_template_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_template_dir)


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------

@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Render the admin login page."""
    return templates.TemplateResponse("login.html", {"request": request})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request):
    """Render the admin dashboard page.  Data is loaded client-side via JS."""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request},
    )


# ---------------------------------------------------------------------------
# Businesses
# ---------------------------------------------------------------------------

@router.get("/admin/businesses", response_class=HTMLResponse)
async def admin_businesses_page(request: Request):
    """List all businesses (data loaded client-side)."""
    return templates.TemplateResponse(
        "businesses/list.html",
        {"request": request},
    )


@router.get("/admin/businesses/new", response_class=HTMLResponse)
async def admin_new_business_page(request: Request):
    """New business form."""
    return templates.TemplateResponse(
        "businesses/form.html",
        {"request": request, "business_id": None},
    )


@router.get("/admin/businesses/{business_id}/edit", response_class=HTMLResponse)
async def admin_edit_business_page(request: Request, business_id: uuid.UUID):
    """Business edit page."""
    return templates.TemplateResponse(
        "businesses/form.html",
        {"request": request, "business_id": str(business_id)},
    )


@router.get("/admin/businesses/{business_id}", response_class=HTMLResponse)
async def admin_business_detail_page(request: Request, business_id: uuid.UUID):
    """Business detail page (redirects to edit form)."""
    return templates.TemplateResponse(
        "businesses/form.html",
        {"request": request, "business_id": str(business_id)},
    )


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

@router.get("/admin/leads", response_class=HTMLResponse)
async def admin_leads_page(request: Request):
    """List leads (data loaded client-side)."""
    return templates.TemplateResponse(
        "leads/list.html",
        {"request": request},
    )


@router.get("/admin/leads/{lead_id}", response_class=HTMLResponse)
async def admin_lead_detail_page(request: Request, lead_id: uuid.UUID):
    """Lead detail with conversation transcript (data loaded client-side)."""
    return templates.TemplateResponse(
        "leads/detail.html",
        {"request": request, "lead_id": str(lead_id)},
    )


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

@router.get("/admin/appointments", response_class=HTMLResponse)
async def admin_appointments_page(request: Request):
    """List appointments (data loaded client-side)."""
    return templates.TemplateResponse(
        "appointments/list.html",
        {"request": request},
    )
