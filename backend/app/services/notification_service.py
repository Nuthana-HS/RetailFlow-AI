"""
RetailFlow AI — Notification Service

Orchestrates:
  1. Alert evaluation (which configs fired)
  2. Notification record creation (one per manager)
  3. Email delivery via SMTP (async, fire-and-forget)

Email Configuration (via environment variables):
    SMTP_HOST     — SMTP server host (default: smtp.gmail.com)
    SMTP_PORT     — SMTP port (default: 587, TLS)
    SMTP_USER     — Sender email address
    SMTP_PASSWORD — SMTP password or app-specific password
    SMTP_FROM     — Display sender (default: "RetailFlow AI <noreply@retailflow.ai>")

Graceful Degradation:
    If SMTP_HOST is not set, email delivery is silently skipped.
    In-app notifications are always created regardless of SMTP config.

Delivery Model:
    asyncio.create_task() — email send is fire-and-forget, non-blocking.
    The queue update response is returned BEFORE email delivery completes.
    This prevents SMTP latency from affecting the queue update hot path.
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queue import AlertConfig, AlertType
from app.repositories.notification_repository import NotificationRepository
from app.repositories.store_repository import StoreRepository

logger = structlog.get_logger(__name__)

_notification_repo = NotificationRepository()
_store_repo = StoreRepository()


# =============================================================================
# SMTP Configuration
# =============================================================================

def _get_smtp_config() -> dict[str, Any] | None:
    """
    Load SMTP config from environment.

    Returns None if SMTP_HOST is not set (email disabled).
    """
    host = os.getenv("SMTP_HOST")
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_addr": os.getenv("SMTP_FROM", "RetailFlow AI <noreply@retailflow.ai>"),
    }


# =============================================================================
# Message Builders
# =============================================================================

def _build_alert_title(
    alert_type: str,
    trigger_value: int,
    counter_number: int | None,
    store_name: str,
) -> str:
    """Build a short alert notification title."""
    location = f"Counter #{counter_number}" if counter_number else store_name

    if alert_type == AlertType.QUEUE_LENGTH:
        return f"🚨 Queue Alert: {location} has {trigger_value} customers waiting"
    else:
        minutes = trigger_value // 60
        return f"⏱ Wait Time Alert: {location} wait exceeds {minutes} min"


def _build_alert_message(
    alert_type: str,
    trigger_value: int,
    threshold: int,
    store_name: str,
    counter_number: int | None,
) -> str:
    """Build the full notification message with action suggestion."""
    location = f"Counter #{counter_number}" if counter_number else "the store"

    if alert_type == AlertType.QUEUE_LENGTH:
        return (
            f"The queue at {location} in {store_name} has reached {trigger_value} customers, "
            f"exceeding the configured alert threshold of {threshold}.\n\n"
            f"Recommended action: Open an additional counter or redirect customers."
        )
    else:
        minutes = trigger_value // 60
        thresh_min = threshold // 60
        return (
            f"The estimated wait time at {location} in {store_name} is {minutes} minutes, "
            f"exceeding the configured alert threshold of {thresh_min} minutes.\n\n"
            f"Recommended action: Increase service speed or open additional counters."
        )


def _build_email_html(title: str, message: str, store_name: str) -> str:
    """Build a simple HTML email body."""
    return f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
      <div style="background: #1a1a2e; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h2 style="margin: 0;">RetailFlow AI — Queue Alert</h2>
        <p style="margin: 5px 0 0; opacity: 0.7;">{store_name}</p>
      </div>
      <div style="background: #f9f9f9; padding: 20px; border: 1px solid #ddd; border-radius: 0 0 8px 8px;">
        <h3 style="color: #e63946;">{title}</h3>
        <p style="color: #333; line-height: 1.6;">{message.replace(chr(10), '<br>')}</p>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">
          This alert was configured in the RetailFlow AI dashboard.<br>
          To adjust alert thresholds, log in and go to Store Settings → Alerts.
        </p>
      </div>
    </body></html>
    """


# =============================================================================
# Email Delivery (synchronous, runs in thread executor)
# =============================================================================

def _send_email_sync(
    smtp_config: dict,
    to_email: str,
    subject: str,
    html_body: str,
) -> bool:
    """
    Send one email synchronously via SMTP.

    Runs in a thread pool executor to avoid blocking the asyncio loop.

    Returns:
        True if sent successfully, False on any SMTP error.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_config["from_addr"]
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as server:
            server.ehlo()
            server.starttls()
            if smtp_config["user"]:
                server.login(smtp_config["user"], smtp_config["password"])
            server.sendmail(smtp_config["from_addr"], [to_email], msg.as_string())

        logger.debug(f"Email sent to {to_email}: {subject}")
        return True

    except smtplib.SMTPException as exc:
        logger.warning(f"SMTP delivery failed to {to_email}: {exc}")
        return False
    except Exception as exc:
        logger.error(f"Email send error: {exc}")
        return False


# =============================================================================
# Notification Service
# =============================================================================

class NotificationService:
    """
    Creates in-app notifications and sends email alerts when thresholds fire.

    Called by QueueService._check_alerts() after each queue update.
    """

    async def handle_triggered_alert(
        self,
        db: AsyncSession,
        config: AlertConfig,
        store_id,
        counter_id,
        counter_number: int | None,
        trigger_value: int,
    ) -> list:
        """
        Handle a triggered alert config:
          1. Fetch all managers of the store (they all receive the notification)
          2. Build notification content
          3. Insert Notification records (one per manager)
          4. Fire-and-forget email delivery

        Args:
            config: The AlertConfig that fired.
            store_id: UUID of the store.
            counter_id: UUID of the counter (or None for store-wide).
            counter_number: Display number (e.g. "Counter #2").
            trigger_value: The metric value that crossed the threshold.

        Returns:
            List of created Notification records.
        """
        # Get store info and managers
        store = await _store_repo.get_by_id(db, store_id)
        if store is None:
            logger.warning(f"Store {store_id} not found during alert handling")
            return []

        managers = await _store_repo.get_managers_for_store(db, store_id)
        if not managers:
            logger.info(f"No managers found for store {store_id} — skipping notification")
            return []

        # Build content
        title = _build_alert_title(
            alert_type=config.alert_type,
            trigger_value=trigger_value,
            counter_number=counter_number,
            store_name=store.name,
        )
        message = _build_alert_message(
            alert_type=config.alert_type,
            trigger_value=trigger_value,
            threshold=config.threshold,
            store_name=store.name,
            counter_number=counter_number,
        )

        # Create notification records (one per manager)
        notifications_data = [
            {
                "alert_config_id": config.id,
                "store_id": store_id,
                "counter_id": counter_id,
                "user_id": manager.id,
                "title": title,
                "message": message,
                "trigger_value": trigger_value,
                "threshold": config.threshold,
                "alert_type": str(config.alert_type),
                "is_read": False,
                "email_sent": False,
                "email_failed": False,
            }
            for manager in managers
        ]

        created = await _notification_repo.create_bulk(db, notifications_data)

        logger.info(
            "Notifications created",
            store_id=str(store_id),
            alert_config_id=str(config.id),
            n_recipients=len(managers),
        )

        # Fire-and-forget email (non-blocking — doesn't delay queue update response)
        smtp_config = _get_smtp_config()
        if smtp_config:
            asyncio.create_task(
                self._deliver_emails(
                    smtp_config=smtp_config,
                    managers=managers,
                    title=title,
                    message=message,
                    store_name=store.name,
                    notification_ids=[n.id for n in created],
                    db=db,
                )
            )

        return created

    async def _deliver_emails(
        self,
        smtp_config: dict,
        managers: list,
        title: str,
        message: str,
        store_name: str,
        notification_ids: list,
        db: AsyncSession,
    ) -> None:
        """
        Send email alerts to all managers (fire-and-forget coroutine).

        Runs concurrently for all managers using asyncio.gather.
        Failed sends are logged but do not raise (delivery is best-effort).
        """
        loop = asyncio.get_event_loop()
        html = _build_email_html(title, message, store_name)
        subject = f"[RetailFlow AI] {title}"

        async def send_one(manager) -> bool:
            return await loop.run_in_executor(
                None, _send_email_sync, smtp_config, manager.email, subject, html
            )

        results = await asyncio.gather(
            *[send_one(m) for m in managers],
            return_exceptions=True,
        )

        # Log delivery summary
        sent = sum(1 for r in results if r is True)
        failed = len(results) - sent
        logger.info(
            f"Email delivery: {sent} sent, {failed} failed",
            store=store_name,
        )


# Module-level singleton
notification_service = NotificationService()
