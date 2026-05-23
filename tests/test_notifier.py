"""Tests for the notification utility, editor launcher, report server, and consolidated folder summaries."""

from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest
from chowkidar.sentinel.notifier import notify, _notify_macos, _notify_linux, _notify_windows
from chowkidar.sentinel.daemon import ChowkidarDaemon
from chowkidar.editor import open_in_editor
from chowkidar.report_server import start_report_server


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
        max_threshold="sunset",
        click_target="/tmp/report.html"
    )

    mock_notify.assert_called_once()
    args, kwargs = mock_notify.call_args
    
    title = args[0]
    message = args[1]
    urgency = args[2]
    click_target = kwargs.get("click_target")

    assert "project-abc" in title
    assert "3 expiring" in title or "ALERT" in title
    assert "gpt-3.5-turbo-0301 (expired) -> gpt-4o-mini" in message
    assert "claude-2.1 (14d) -> claude-3-haiku-20240307" in message
    assert "gemini-1.0-pro (30d) -> gemini-1.5-flash" in message
    assert urgency == "critical"
    assert click_target == "/tmp/report.html"


@patch("subprocess.run")
def test_notify_macos_no_click(mock_run):
    mock_run.return_value.returncode = 0
    success = _notify_macos("Title", "Message", "normal", None)
    assert success is True
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "osascript" in args
    assert "display notification" in args[2]


@patch("subprocess.run")
def test_notify_macos_with_click(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "button returned:Open Report"
    
    with patch("chowkidar.sentinel.notifier._open_report_flow") as mock_flow:
        success = _notify_macos("Title", "Message", "normal", "/tmp/report.html")
        assert success is True
        
        # Click handler runs in a background thread; wait for it or trigger manually
        import time
        # Small wait for thread to complete subprocess run
        retries = 10
        while retries > 0 and not mock_run.called:
            time.sleep(0.05)
            retries -= 1
            
        assert mock_run.called
        args = mock_run.call_args[0][0]
        assert "osascript" in args
        assert "display alert" in args[2]


@patch("subprocess.run")
def test_notify_linux_with_click(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "open"
    
    with patch("chowkidar.sentinel.notifier._open_report_flow") as mock_flow:
        success = _notify_linux("Title", "Message", "normal", "/tmp/report.html")
        assert success is True
        
        import time
        retries = 10
        while retries > 0 and not mock_run.called:
            time.sleep(0.05)
            retries -= 1
            
        assert mock_run.called
        args = mock_run.call_args[0][0]
        assert "notify-send" in args
        assert "--action=open=Open Report" in args


@patch("subprocess.run")
def test_notify_windows_with_click(mock_run):
    mock_run.return_value.returncode = 0
    
    with patch("chowkidar.report_server.start_report_server", return_value=12345):
        success = _notify_windows("Title", "Message", "normal", "/tmp/report.html")
        assert success is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "powershell" in args
        assert 'launch="http://127.0.0.1:12345/?path=' in args[2]


@patch("subprocess.run")
def test_open_in_editor(mock_run):
    mock_run.return_value.returncode = 0
    
    # Force cursor/code check to use a fake path that exists to avoid CWD fallback
    with patch("pathlib.Path.exists", return_value=True):
        with patch("shutil.which", side_effect=lambda x: "/bin/" + x if x == "cursor" else None):
            opened = open_in_editor("/project/.env")
            assert opened is True
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "cursor" in args


@patch("subprocess.run")
def test_open_in_editor_fallback(mock_run):
    mock_run.return_value.returncode = 0
    
    with patch("pathlib.Path.exists", return_value=True):
        with patch("shutil.which", return_value=None):
            with patch("platform.system", return_value="Darwin"):
                opened = open_in_editor("/project/.env")
                assert opened is True
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert "open" in args
