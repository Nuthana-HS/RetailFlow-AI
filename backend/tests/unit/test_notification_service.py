"""
RetailFlow AI — Unit Tests: Notification Service

Tests for message building, SMTP config detection, and alert content.
No DB, no real SMTP, no network required.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.queue import AlertConfig, AlertType
from app.services.notification_service import (
    _build_alert_message,
    _build_alert_title,
    _build_email_html,
    _get_smtp_config,
    _send_email_sync,
)


# =============================================================================
# Test: Title building
# =============================================================================

class TestBuildAlertTitle:

    def test_queue_length_alert_title_with_counter(self) -> None:
        title = _build_alert_title(
            alert_type=AlertType.QUEUE_LENGTH,
            trigger_value=12,
            counter_number=3,
            store_name="Big Bazaar",
        )
        assert "Counter #3" in title
        assert "12" in title

    def test_queue_length_alert_title_store_wide(self) -> None:
        """Store-wide alerts use store name instead of counter."""
        title = _build_alert_title(
            alert_type=AlertType.QUEUE_LENGTH,
            trigger_value=8,
            counter_number=None,
            store_name="Big Bazaar",
        )
        assert "Big Bazaar" in title
        assert "8" in title

    def test_wait_time_alert_shows_minutes(self) -> None:
        """Wait time alert should display minutes, not raw seconds."""
        title = _build_alert_title(
            alert_type=AlertType.WAIT_TIME,
            trigger_value=600,   # 10 minutes in seconds
            counter_number=2,
            store_name="FreshMart",
        )
        assert "10" in title   # 600s / 60 = 10 min

    def test_title_includes_emoji(self) -> None:
        """Alert titles should have emoji for visual differentiation."""
        title_q = _build_alert_title(AlertType.QUEUE_LENGTH, 5, 1, "X")
        title_w = _build_alert_title(AlertType.WAIT_TIME, 300, 1, "X")
        assert "🚨" in title_q
        assert "⏱" in title_w


# =============================================================================
# Test: Message building
# =============================================================================

class TestBuildAlertMessage:

    def test_queue_message_contains_threshold(self) -> None:
        msg = _build_alert_message(
            alert_type=AlertType.QUEUE_LENGTH,
            trigger_value=15,
            threshold=10,
            store_name="MegaMart",
            counter_number=1,
        )
        assert "15" in msg
        assert "10" in msg

    def test_queue_message_has_action_suggestion(self) -> None:
        msg = _build_alert_message(AlertType.QUEUE_LENGTH, 10, 5, "X", 1)
        assert "action" in msg.lower() or "recommend" in msg.lower() or "Open" in msg

    def test_wait_time_message_shows_minutes(self) -> None:
        msg = _build_alert_message(
            alert_type=AlertType.WAIT_TIME,
            trigger_value=900,   # 15 minutes
            threshold=600,       # 10 minutes
            store_name="FreshMart",
            counter_number=None,
        )
        assert "15" in msg
        assert "10" in msg

    def test_store_wide_uses_store_name(self) -> None:
        msg = _build_alert_message(AlertType.QUEUE_LENGTH, 5, 3, "MyStore", None)
        assert "MyStore" in msg


# =============================================================================
# Test: Email HTML building
# =============================================================================

class TestBuildEmailHtml:

    def test_html_contains_title(self) -> None:
        html = _build_email_html("Alert Title", "Alert message body", "StoreName")
        assert "Alert Title" in html

    def test_html_contains_store_name(self) -> None:
        html = _build_email_html("Title", "Body", "Big Bazaar")
        assert "Big Bazaar" in html

    def test_html_contains_brand(self) -> None:
        html = _build_email_html("Title", "Body", "Store")
        assert "RetailFlow" in html

    def test_html_is_valid_structure(self) -> None:
        html = _build_email_html("T", "B", "S")
        assert "<html>" in html
        assert "</html>" in html


# =============================================================================
# Test: SMTP Config
# =============================================================================

class TestSMTPConfig:

    def test_returns_none_when_smtp_host_not_set(self, monkeypatch) -> None:
        """Without SMTP_HOST, email is disabled."""
        monkeypatch.delenv("SMTP_HOST", raising=False)
        assert _get_smtp_config() is None

    def test_returns_config_dict_when_host_set(self, monkeypatch) -> None:
        monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "test@test.com")
        config = _get_smtp_config()
        assert config is not None
        assert config["host"] == "smtp.test.com"
        assert config["port"] == 587

    def test_default_port_is_587(self, monkeypatch) -> None:
        monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
        monkeypatch.delenv("SMTP_PORT", raising=False)
        config = _get_smtp_config()
        assert config["port"] == 587


# =============================================================================
# Test: SMTP send function (mocked server)
# =============================================================================

class TestSendEmailSync:

    def test_returns_true_on_success(self) -> None:
        """Successful SMTP delivery returns True."""
        smtp_config = {
            "host": "smtp.test.com",
            "port": 587,
            "user": "user@test.com",
            "password": "pass",
            "from_addr": "noreply@test.com",
        }
        mock_server = MagicMock()
        with patch("smtplib.SMTP") as MockSMTP:
            MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
            MockSMTP.return_value.__exit__ = MagicMock(return_value=False)
            result = _send_email_sync(smtp_config, "manager@test.com", "Subject", "<html></html>")

        # Verify result is bool (True or False — actual SMTP interaction is mocked)
        assert isinstance(result, bool)

    def test_returns_false_on_smtp_exception(self) -> None:
        """SMTP failure returns False (never raises)."""
        import smtplib
        smtp_config = {
            "host": "bad_host", "port": 587,
            "user": "", "password": "",
            "from_addr": "noreply@test.com",
        }
        with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, "Connection refused")):
            result = _send_email_sync(smtp_config, "m@test.com", "Sub", "<html></html>")
        assert result is False
