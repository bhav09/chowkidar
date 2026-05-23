"""Cross-platform desktop notification system with native click callbacks and action buttons."""

from __future__ import annotations

import logging
import platform
import subprocess
import threading
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)

APP_NAME = "Chowkidar"


def notify(title: str, message: str, urgency: str = "normal", click_target: str | None = None) -> bool:
    """Send a desktop notification. Returns True if notification was successfully queued or sent.

    urgency: "low", "normal", "critical"
    click_target: optional file path to an HTML report that should be opened when clicked.
    """
    system = platform.system()

    try:
        if system == "Darwin":
            return _notify_macos(title, message, urgency, click_target)
        elif system == "Linux":
            return _notify_linux(title, message, urgency, click_target)
        elif system == "Windows":
            return _notify_windows(title, message, urgency, click_target)
        else:
            return _notify_plyer(title, message)
    except Exception as e:
        logger.warning("Native notification failed, trying plyer: %s", e)
        return _notify_plyer(title, message)


def _notify_macos(title: str, message: str, urgency: str, click_target: str | None) -> bool:
    """macOS notification via AppleScript display alert / notification."""
    if click_target:
        def show_alert() -> None:
            t_esc = _escape_applescript(title)
            m_esc = _escape_applescript(message)
            # Use display alert to provide beautiful, actionable buttons on macOS
            script = (
                f'display alert "{t_esc}" message "{m_esc}" '
                f'buttons {{"Close", "Open Report"}} default button "Open Report"'
            )
            try:
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
                if "Open Report" in res.stdout:
                    _open_report_flow(click_target)
            except Exception as e:
                logger.error("macOS alert click handler failed: %s", e)

        threading.Thread(target=show_alert, daemon=True).start()
        return True
    else:
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


def _notify_linux(title: str, message: str, urgency: str, click_target: str | None) -> bool:
    """Linux notification via notify-send."""
    urgency_map = {"low": "low", "normal": "normal", "critical": "critical"}
    notify_urgency = urgency_map.get(urgency, "normal")

    if click_target:
        def show_linux_notify() -> None:
            cmd = [
                "notify-send",
                f"--urgency={notify_urgency}",
                f"--app-name={APP_NAME}",
                "--action=open=Open Report",
                title,
                message,
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if "open" in res.stdout:
                    _open_report_flow(click_target)
            except Exception as e:
                logger.error("Linux notify-send click handler failed: %s", e)

        threading.Thread(target=show_linux_notify, daemon=True).start()
        return True
    else:
        cmd = [
            "notify-send",
            f"--urgency={notify_urgency}",
            f"--app-name={APP_NAME}",
            title,
            message,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0


def _notify_windows(title: str, message: str, urgency: str, click_target: str | None) -> bool:
    """Windows notification via PowerShell toast."""
    ns = "Windows.UI.Notifications"
    mgr = f"[{ns}.ToastNotificationManager]"

    launch_url = ""
    if click_target:
        try:
            from ..report_server import start_report_server
            # Pre-start report server to get port and build launch URL
            port = start_report_server("", Path(click_target))
            escaped_path = urllib.parse.quote(str(Path(click_target).resolve()))
            launch_url = f"http://127.0.0.1:{port}/?path={escaped_path}"
        except Exception as e:
            logger.error("Failed to start report server for Windows toast: %s", e)

    title_esc = (
        title.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
    message_esc = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )

    launch_attr = f' launch="{launch_url}"' if launch_url else ""
    xml_str = (
        f'<toast{launch_attr}>'
        f'<visual>'
        f'<binding template="ToastText02">'
        f'<text id="1">{title_esc}</text>'
        f'<text id="2">{message_esc}</text>'
        f'</binding>'
        f'</visual>'
        f'</toast>'
    )

    ps_script = (
        f"[Windows.UI.Notifications.ToastNotificationManager, {ns}, ContentType = WindowsRuntime] > $null; "
        f"$xml = [Windows.Data.Xml.Dom.XmlDocument]::new(); "
        f'$xml.LoadXml(\'{xml_str}\'); '
        f"$toast = [{ns}.ToastNotification]::new($xml); "
        f'{mgr}::CreateToastNotifier("{APP_NAME}").Show($toast)'
    )
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True, timeout=15,
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


def _open_report_flow(click_target: str) -> None:
    """Helper to start the report server and open the report in the default browser."""
    import webbrowser

    from ..report_server import start_report_server
    try:
        target_path = Path(click_target).resolve()
        port = start_report_server("", target_path)
        webbrowser.open(f"http://127.0.0.1:{port}/?path={urllib.parse.quote(str(target_path))}")
    except Exception as e:
        logger.error("Failed to open report flow: %s", e)
