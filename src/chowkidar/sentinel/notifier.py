"""Cross-platform desktop notification system."""

from __future__ import annotations

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

APP_NAME = "Chowkidar"


def notify(title: str, message: str, urgency: str = "normal") -> bool:
    """Send a desktop notification. Returns True if notification was sent.

    urgency: "low", "normal", "critical"
    """
    system = platform.system()

    try:
        if system == "Darwin":
            return _notify_macos(title, message, urgency)
        elif system == "Linux":
            return _notify_linux(title, message, urgency)
        elif system == "Windows":
            return _notify_windows(title, message, urgency)
        else:
            return _notify_plyer(title, message)
    except Exception as e:
        logger.warning("Native notification failed, trying plyer: %s", e)
        return _notify_plyer(title, message)


def _notify_macos(title: str, message: str, urgency: str) -> bool:
    """macOS notification via osascript (always available)."""
    script = (
        f'display notification "{_escape_applescript(message)}" '
        f'with title "{_escape_applescript(APP_NAME)}" '
        f'subtitle "{_escape_applescript(title)}"'
    )
    if urgency == "critical":
        script += ' sound name "Funk"'

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0


def _escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _notify_linux(title: str, message: str, urgency: str) -> bool:
    """Linux notification via notify-send."""
    urgency_map = {"low": "low", "normal": "normal", "critical": "critical"}
    notify_urgency = urgency_map.get(urgency, "normal")

    result = subprocess.run(
        [
            "notify-send",
            f"--urgency={notify_urgency}",
            f"--app-name={APP_NAME}",
            title,
            message,
        ],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0


def _notify_windows(title: str, message: str, urgency: str) -> bool:
    """Windows notification via PowerShell toast."""
    ns = "Windows.UI.Notifications"
    mgr = f"[{ns}.ToastNotificationManager]"
    ps_script = (
        f"[{ns}.ToastNotificationManager, {ns}, ContentType = WindowsRuntime] > $null; "
        f"$t = {mgr}::GetTemplateContent([{ns}.ToastTemplateType]::ToastText02); "
        f'$n = $t.GetElementsByTagName("text"); '
        f'$n.Item(0).AppendChild($t.CreateTextNode("{title}")) > $null; '
        f'$n.Item(1).AppendChild($t.CreateTextNode("{message}")) > $null; '
        f"$toast = [{ns}.ToastNotification]::new($t); "
        f'{mgr}::CreateToastNotifier("{APP_NAME}").Show($toast)'
    )
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return _notify_plyer(title, message)


def _notify_plyer(title: str, message: str) -> bool:
    """Fallback notification via plyer (cross-platform)."""
    try:
        from plyer import notification as plyer_notification

        plyer_notification.notify(
            title=f"{APP_NAME}: {title}",
            message=message,
            app_name=APP_NAME,
            timeout=10,
        )
        return True
    except Exception as e:
        logger.error("All notification methods failed: %s", e)
        return False
