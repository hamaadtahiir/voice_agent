"""Media upload and download utilities."""

import uuid
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")


async def save_upload(file_bytes: bytes, filename: str, business_id: str) -> str:
    """Save uploaded file bytes to disk and return the relative URL path.

    Files are stored under ``uploads/<business_id>/<uuid>-<filename>``.
    """
    biz_dir = UPLOAD_DIR / business_id
    biz_dir.mkdir(parents=True, exist_ok=True)

    # Sanitise filename
    safe_name = "".join(
        c if c.isalnum() or c in (".", "-", "_") else "_" for c in filename
    )
    stored_name = f"{uuid.uuid4().hex[:12]}-{safe_name}"
    file_path = biz_dir / stored_name

    file_path.write_bytes(file_bytes)

    # Return relative path suitable for URL construction
    return f"uploads/{business_id}/{stored_name}"


async def download_whatsapp_media(
    media_url: str,
    access_token: str,
) -> tuple[bytes, str]:
    """Download media from the WhatsApp Cloud API.

    Returns ``(file_bytes, content_type)``.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        # First, get the download URL from the media ID endpoint
        resp = await client.get(
            media_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()

        data = resp.json()
        download_url = data.get("url", media_url)

        # Download the actual file
        file_resp = await client.get(
            download_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        file_resp.raise_for_status()

        content_type = file_resp.headers.get("content-type", "application/octet-stream")
        return file_resp.content, content_type


def get_media_url(relative_path: str, base_url: str) -> str:
    """Convert a relative upload path to a full URL."""
    base = base_url.rstrip("/")
    path = relative_path.lstrip("/")
    return f"{base}/{path}"
