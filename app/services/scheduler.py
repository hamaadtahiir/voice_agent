"""APScheduler background jobs for reminders and re-engagement."""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.db.engine import async_session_factory

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def check_appointment_reminders() -> None:
    """Run every 15 minutes. Find appointments needing 24-hour or 1-hour
    reminders and send them.
    """
    from app.models.appointment import Appointment
    from app.models.business import Business
    from app.models.lead import Lead
    from app.services.notifications import send_appointment_reminder

    now = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        try:
            # 24-hour reminders: appointments between 23 and 25 hours from now
            window_24h_start = now + timedelta(hours=23)
            window_24h_end = now + timedelta(hours=25)

            result = await db.execute(
                select(Appointment).where(
                    Appointment.status.in_(["scheduled", "confirmed"]),
                    Appointment.reminder_24h_sent == False,  # noqa: E712
                    Appointment.scheduled_at >= window_24h_start,
                    Appointment.scheduled_at <= window_24h_end,
                )
            )
            appointments_24h = result.scalars().all()

            for appt in appointments_24h:
                lead_result = await db.execute(
                    select(Lead).where(Lead.id == appt.lead_id)
                )
                lead = lead_result.scalar_one_or_none()
                biz_result = await db.execute(
                    select(Business).where(Business.id == appt.business_id)
                )
                business = biz_result.scalar_one_or_none()

                if lead and business:
                    sent = await send_appointment_reminder(lead, appt, business, "24h")
                    if sent:
                        appt.reminder_24h_sent = True
                        logger.info("Sent 24h reminder for appointment %s", appt.id)

            # 1-hour reminders: appointments between 50 and 70 minutes from now
            window_1h_start = now + timedelta(minutes=50)
            window_1h_end = now + timedelta(minutes=70)

            result = await db.execute(
                select(Appointment).where(
                    Appointment.status.in_(["scheduled", "confirmed"]),
                    Appointment.reminder_1h_sent == False,  # noqa: E712
                    Appointment.scheduled_at >= window_1h_start,
                    Appointment.scheduled_at <= window_1h_end,
                )
            )
            appointments_1h = result.scalars().all()

            for appt in appointments_1h:
                lead_result = await db.execute(
                    select(Lead).where(Lead.id == appt.lead_id)
                )
                lead = lead_result.scalar_one_or_none()
                biz_result = await db.execute(
                    select(Business).where(Business.id == appt.business_id)
                )
                business = biz_result.scalar_one_or_none()

                if lead and business:
                    sent = await send_appointment_reminder(lead, appt, business, "1h")
                    if sent:
                        appt.reminder_1h_sent = True
                        logger.info("Sent 1h reminder for appointment %s", appt.id)

            await db.commit()

        except Exception:
            logger.exception("Error in check_appointment_reminders")
            await db.rollback()


async def check_dropoff_reengagement() -> None:
    """Run every 5 minutes. Find leads that have gone quiet during
    qualification and send re-engagement messages.

    Criteria:
    - status = 'qualifying'
    - last_message_at > 15 minutes ago
    - re_engagement_count < 2
    """
    from app.models.business import Business
    from app.models.lead import Lead
    from app.services.notifications import send_sms

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=15)

    async with async_session_factory() as db:
        try:
            result = await db.execute(
                select(Lead).where(
                    Lead.status == "qualifying",
                    Lead.last_message_at != None,  # noqa: E711
                    Lead.last_message_at < cutoff,
                    Lead.re_engagement_count < 2,
                )
            )
            leads = result.scalars().all()

            for lead in leads:
                # Skip if we already sent a re-engagement recently (within 15 min)
                if lead.re_engagement_sent_at and lead.re_engagement_sent_at > cutoff:
                    continue

                biz_result = await db.execute(
                    select(Business).where(Business.id == lead.business_id)
                )
                business = biz_result.scalar_one_or_none()
                if not business:
                    continue

                lead_name = lead.name or "there"
                business_name = business.name

                if lead.re_engagement_count == 0:
                    msg = (
                        f"Hi {lead_name}! Just checking in - were you still "
                        f"interested in getting help from {business_name}? "
                        f"We're here whenever you're ready!"
                    )
                else:
                    msg = (
                        f"Hi {lead_name}, we noticed you might still need help. "
                        f"Feel free to reach out to {business_name} any time - "
                        f"we'd love to assist you!"
                    )

                sent = False
                if lead.phone:
                    sent = await send_sms(lead.phone, msg)

                if sent:
                    lead.re_engagement_count += 1
                    lead.re_engagement_sent_at = now
                    lead.drop_off_at = lead.drop_off_at or now
                    logger.info(
                        "Sent re-engagement #%d to lead %s",
                        lead.re_engagement_count,
                        lead.id,
                    )

            await db.commit()

        except Exception:
            logger.exception("Error in check_dropoff_reengagement")
            await db.rollback()


def start_scheduler() -> None:
    """Add all background jobs and start the APScheduler."""
    scheduler.add_job(
        check_appointment_reminders,
        "interval",
        minutes=15,
        id="appointment_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        check_dropoff_reengagement,
        "interval",
        minutes=5,
        id="dropoff_reengagement",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Background scheduler started")


def stop_scheduler() -> None:
    """Shut down the APScheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
