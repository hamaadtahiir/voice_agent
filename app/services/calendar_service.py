"""Google Calendar integration for availability checks and event management."""

import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import get_settings
from app.services.encryption import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Temporary storage for PKCE code verifiers, keyed by business_id (state param).
# Cleared after use in the callback.
_pkce_verifiers: dict[str, str] = {}


def _get_client_config() -> dict:
    """Return the Google OAuth client config dict."""
    settings = get_settings()
    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }


def get_google_credentials(business) -> Credentials | None:
    """Decrypt the stored OAuth token and return Google Credentials.

    If the access token is expired and a refresh token is available,
    the credentials are refreshed and the updated token is re-encrypted
    on the business object (caller must commit the session).
    """
    if not business.google_oauth_token:
        return None

    try:
        token_json = decrypt_value(business.google_oauth_token)
        token_data = json.loads(token_json)
    except Exception:
        logger.exception("Failed to decrypt Google OAuth token for business %s", business.id)
        return None

    settings = get_settings()
    creds = Credentials(
        token=token_data.get("access_token") or token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleAuthRequest())
            # Re-encrypt the refreshed token
            updated = {
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "expiry": creds.expiry.isoformat() if creds.expiry else None,
            }
            business.google_oauth_token = encrypt_value(json.dumps(updated))
        except Exception:
            logger.exception("Failed to refresh Google credentials for business %s", business.id)
            return None

    return creds


def initiate_oauth(business_id: str) -> str:
    """Return the Google OAuth authorization URL.

    ``business_id`` is embedded in the ``state`` parameter so the callback
    can associate the grant with the correct business.
    """
    settings = get_settings()
    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=business_id,
    )
    # Store the PKCE code_verifier so the callback can use it
    if flow.code_verifier:
        _pkce_verifiers[business_id] = flow.code_verifier
    return auth_url


async def handle_oauth_callback(code: str, business_id: str, db) -> None:
    """Exchange the authorization code for tokens and store them on the
    business record (encrypted).
    """
    from sqlalchemy import select
    from app.models.business import Business

    settings = get_settings()
    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )
    # Restore the PKCE code_verifier from the initiate step
    stored_verifier = _pkce_verifiers.pop(business_id, None)
    if stored_verifier:
        flow.code_verifier = stored_verifier
    flow.fetch_token(code=code)
    creds = flow.credentials

    token_data = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }
    encrypted_token = encrypt_value(json.dumps(token_data))

    result = await db.execute(
        select(Business).where(Business.id == business_id)
    )
    business = result.scalar_one_or_none()
    if business:
        business.google_oauth_token = encrypted_token
        if not business.google_calendar_id:
            business.google_calendar_id = "primary"
        await db.flush()


def _parse_business_hours(business_hours: dict | None, date_str: str, tz: ZoneInfo) -> tuple[datetime, datetime] | None:
    """Parse business hours for a given date, returning (open, close) datetimes
    in the business timezone, or None if the business is closed that day.
    """
    if not business_hours:
        # Default: 9 AM to 5 PM
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
        return (
            dt.replace(hour=9, minute=0, second=0),
            dt.replace(hour=17, minute=0, second=0),
        )

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = dt.strftime("%A").lower()

    day_hours = business_hours.get(day_name)
    if not day_hours:
        return None

    open_str = day_hours.get("open", "09:00")
    close_str = day_hours.get("close", "17:00")

    open_h, open_m = map(int, open_str.split(":"))
    close_h, close_m = map(int, close_str.split(":"))

    open_dt = dt.replace(hour=open_h, minute=open_m, second=0, tzinfo=tz)
    close_dt = dt.replace(hour=close_h, minute=close_m, second=0, tzinfo=tz)

    return (open_dt, close_dt)


async def get_available_slots(
    business,
    date_str: str,
    duration_minutes: int = 60,
) -> list[dict]:
    """Query Google Calendar FreeBusy API and return available slots within
    business hours for the given date.

    Each slot is a dict: {"start": "10:00 AM", "end": "11:00 AM",
    "start_iso": "2024-01-15T10:00:00-05:00"}.
    """
    tz = ZoneInfo(business.timezone or "America/New_York")
    hours = _parse_business_hours(business.business_hours, date_str, tz)
    if hours is None:
        return []

    day_open, day_close = hours
    calendar_id = business.google_calendar_id or "primary"

    creds = get_google_credentials(business)
    busy_periods: list[tuple[datetime, datetime]] = []

    if creds:
        try:
            service = build("calendar", "v3", credentials=creds)
            body = {
                "timeMin": day_open.isoformat(),
                "timeMax": day_close.isoformat(),
                "items": [{"id": calendar_id}],
                "timeZone": str(tz),
            }
            result = service.freebusy().query(body=body).execute()
            busy_list = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])
            for period in busy_list:
                start = datetime.fromisoformat(period["start"])
                end = datetime.fromisoformat(period["end"])
                busy_periods.append((start, end))
        except Exception:
            logger.exception("Failed to query Google Calendar FreeBusy for business %s", business.id)

    # Generate slots
    slots: list[dict] = []
    slot_start = day_open
    slot_duration = timedelta(minutes=duration_minutes)

    while slot_start + slot_duration <= day_close:
        slot_end = slot_start + slot_duration
        is_busy = any(
            not (slot_end <= busy_start or slot_start >= busy_end)
            for busy_start, busy_end in busy_periods
        )
        if not is_busy:
            slots.append({
                "start": slot_start.strftime("%-I:%M %p"),
                "end": slot_end.strftime("%-I:%M %p"),
                "start_iso": slot_start.isoformat(),
            })
        slot_start += timedelta(minutes=30)  # 30-minute increments

    return slots


async def create_calendar_event(
    business,
    lead,
    appointment_data: dict,
) -> dict:
    """Create a Google Calendar event for the appointment.

    Returns {"event_id": str, "event_link": str} or empty dict on failure.
    """
    creds = get_google_credentials(business)
    if not creds:
        logger.warning("No Google credentials for business %s; skipping calendar event", business.id)
        return {}

    tz_str = business.timezone or "America/New_York"
    calendar_id = business.google_calendar_id or "primary"

    scheduled_at = appointment_data.get("scheduled_at")
    if isinstance(scheduled_at, str):
        scheduled_at = datetime.fromisoformat(scheduled_at)

    duration = appointment_data.get("duration_minutes", business.appointment_duration_default or 60)
    end_time = scheduled_at + timedelta(minutes=duration)

    service_name = appointment_data.get("service_name", "Appointment")
    lead_name = lead.name or "Customer"
    lead_email = lead.email
    lead_phone = lead.phone or ""

    event_body = {
        "summary": f"{service_name} - {lead_name}",
        "description": (
            f"Service: {service_name}\n"
            f"Customer: {lead_name}\n"
            f"Phone: {lead_phone}\n"
            f"Email: {lead_email or 'N/A'}\n"
            f"Notes: {appointment_data.get('notes', '')}"
        ),
        "start": {
            "dateTime": scheduled_at.isoformat(),
            "timeZone": tz_str,
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": tz_str,
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 60},
                {"method": "popup", "minutes": 1440},
            ],
        },
    }

    if lead_email:
        event_body["attendees"] = [{"email": lead_email}]

    try:
        service = build("calendar", "v3", credentials=creds)
        event = service.events().insert(
            calendarId=calendar_id,
            body=event_body,
            sendUpdates="all" if lead_email else "none",
        ).execute()

        return {
            "event_id": event.get("id", ""),
            "event_link": event.get("htmlLink", ""),
        }
    except Exception:
        logger.exception("Failed to create calendar event for business %s", business.id)
        return {}


async def cancel_calendar_event(business, event_id: str) -> bool:
    """Cancel (delete) a Google Calendar event. Returns True on success."""
    creds = get_google_credentials(business)
    if not creds:
        return False

    calendar_id = business.google_calendar_id or "primary"

    try:
        service = build("calendar", "v3", credentials=creds)
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return True
    except Exception:
        logger.exception("Failed to cancel calendar event %s for business %s", event_id, business.id)
        return False
