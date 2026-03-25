"""OS-native background service installer (launchd, systemd, Windows Task Scheduler)."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def install_service() -> tuple[bool, str]:
    """Install Chowkidar as an OS-native background service."""
    system = platform.system()
    if system == "Darwin":
        return _install_launchd()
    elif system == "Linux":
        return _install_systemd()
    elif system == "Windows":
        return _install_windows_task()
    else:
        return False, f"Unsupported platform: {system}"


def uninstall_service() -> tuple[bool, str]:
    """Remove the OS-native background service."""
    system = platform.system()
    if system == "Darwin":
        return _uninstall_launchd()
    elif system == "Linux":
        return _uninstall_systemd()
    elif system == "Windows":
        return _uninstall_windows_task()
    else:
        return False, f"Unsupported platform: {system}"


def is_service_installed() -> bool:
    system = platform.system()
    if system == "Darwin":
        plist_path = Path.home() / "Library/LaunchAgents/com.chowkidar.daemon.plist"
        return plist_path.exists()
    elif system == "Linux":
        unit_path = Path.home() / ".config/systemd/user/chowkidar.service"
        return unit_path.exists()
    elif system == "Windows":
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", "Chowkidar"],
            capture_output=True, text=True,
        )
        return result.returncode == 0
    return False


# --- macOS (launchd) ---

def _get_chowkidar_bin() -> str:
    path = shutil.which("chowkidar")
    if path:
        return path
    return str(Path(sys.executable).parent / "chowkidar")


def _install_launchd() -> tuple[bool, str]:
    plist_path = Path.home() / "Library/LaunchAgents/com.chowkidar.daemon.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    chowkidar_bin = _get_chowkidar_bin()
    log_dir = Path.home() / ".chowkidar/logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.chowkidar.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>{chowkidar_bin}</string>
        <string>daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir}/daemon.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/daemon.stderr.log</string>
    <key>ProcessType</key>
    <string>Background</string>
    <key>LowPriorityIO</key>
    <true/>
</dict>
</plist>"""

    plist_path.write_text(plist_content)

    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True, f"Service installed at {plist_path}"
    return False, f"Failed to load plist: {result.stderr}"


def _uninstall_launchd() -> tuple[bool, str]:
    plist_path = Path.home() / "Library/LaunchAgents/com.chowkidar.daemon.plist"
    if not plist_path.exists():
        return True, "Service not installed"

    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
    plist_path.unlink(missing_ok=True)
    return True, "Service uninstalled"


# --- Linux (systemd) ---

def _install_systemd() -> tuple[bool, str]:
    unit_dir = Path.home() / ".config/systemd/user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = unit_dir / "chowkidar.service"
    chowkidar_bin = _get_chowkidar_bin()

    unit_content = f"""[Unit]
Description=Chowkidar LLM Model Deprecation Watchdog
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={chowkidar_bin} daemon
Restart=on-failure
RestartSec=30
Environment=PATH={Path(sys.executable).parent}:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
"""

    unit_path.write_text(unit_content)

    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    result = subprocess.run(
        ["systemctl", "--user", "enable", "--now", "chowkidar.service"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True, f"Service installed at {unit_path}"
    return False, f"Failed to enable service: {result.stderr}"


def _uninstall_systemd() -> tuple[bool, str]:
    unit_path = Path.home() / ".config/systemd/user/chowkidar.service"
    if not unit_path.exists():
        return True, "Service not installed"

    subprocess.run(
        ["systemctl", "--user", "disable", "--now", "chowkidar.service"],
        capture_output=True,
    )
    unit_path.unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    return True, "Service uninstalled"


# --- Windows (Task Scheduler) ---

def _install_windows_task() -> tuple[bool, str]:
    chowkidar_bin = _get_chowkidar_bin()

    result = subprocess.run(
        [
            "schtasks", "/Create",
            "/TN", "Chowkidar",
            "/TR", f'"{chowkidar_bin}" daemon',
            "/SC", "ONLOGON",
            "/RL", "LIMITED",
            "/F",
        ],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        subprocess.run(["schtasks", "/Run", "/TN", "Chowkidar"], capture_output=True)
        return True, "Windows Task Scheduler task created"
    return False, f"Failed to create task: {result.stderr}"


def _uninstall_windows_task() -> tuple[bool, str]:
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", "Chowkidar", "/F"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True, "Windows task removed"
    return False, f"Failed to remove task: {result.stderr}"
