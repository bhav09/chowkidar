"""Tests for the notification utility and consolidated folder summaries."""

from unittest.mock import patch
from chowkidar.sentinel.notifier import notify
from chowkidar.sentinel.daemon import ChowkidarDaemon


def test_desktop_notification_success():
    # Sending notifications should return True/False or fallback gracefully to plyer
    # Let's test that notify doesn't crash and returns a boolean value
    success = notify("Test Title", "Test Message", "normal")
    assert isinstance(success, bool)


@patch("chowkidar.sentinel.daemon.notify")
def test_send_folder_notification_formatting(mock_notify):
    expiring_models = [
        {"model": "gpt-3.5-turbo-0301", "variable": "OPENAI_MODEL", "days_until": 0, "replacement": "openai/gpt-4o-mini"},
        {"model": "claude-2.1", "variable": "ANTHROPIC_MODEL", "days_until": 14, "replacement": "anthropic/claude-3-haiku-20240307"},
        {"model": "gemini-1.0-pro", "variable": "GEMINI_MODEL", "days_until": 30, "replacement": "google/gemini-1.5-flash"},
    ]
    advisory = [
        {"variable": "OPENAI_MODEL", "recommended_model": "gpt-4o-mini", "purpose": "chat completion"},
        {"variable": "ANTHROPIC_MODEL", "recommended_model": "claude-3-haiku-20240307", "purpose": "chat completion"},
        {"variable": "GEMINI_MODEL", "recommended_model": "gemini-1.5-flash", "purpose": "chat completion"},
    ]

    ChowkidarDaemon._send_folder_notification(
        project_path="/Users/user/project-abc",
        expiring_models=expiring_models,
        advisory=advisory,
        max_threshold="sunset"
    )

    mock_notify.assert_called_once()
    args, kwargs = mock_notify.call_args
    
    title = args[0]
    message = args[1]
    urgency = args[2]

    assert "project-abc" in title
    assert "3 expiring" in title or "ALERT" in title
    assert "gpt-3.5-turbo-0301 (expired) -> gpt-4o-mini" in message
    assert "claude-2.1 (14d) -> claude-3-haiku-20240307" in message
    assert "gemini-1.0-pro (30d) -> gemini-1.5-flash" in message
    assert urgency == "critical"

