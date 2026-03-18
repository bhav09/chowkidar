"""User configuration management for Chowkidar.

Config lives at ~/.chowkidar/config.toml and controls behavior like
auto-update, rules writing, SLM model choice, scan intervals, etc.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[no-redef]

CHOWKIDAR_HOME = Path.home() / ".chowkidar"

DEFAULTS: dict[str, Any] = {
    "auto_update": False,
    "write_rules": True,
    "gitignore_rules": True,
    "slm_model": "gemma3:1b",
    "slm_enabled": False,
    "scan_interval_hours": 4,
    "sync_interval_hours": 24,
    "notification_cooldown_hours": 24,
    "log_level": "INFO",
    "providers": ["openai", "anthropic", "google", "mistral"],
    "webhook_url": "",
    "webhook_format": "generic",
}


class Config:
    """Manages ~/.chowkidar/config.toml."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (CHOWKIDAR_HOME / "config.toml")
        self._data: dict[str, Any] = dict(DEFAULTS)
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        with open(self.path, "rb") as f:
            stored = tomllib.load(f)
        self._data.update(stored)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for key, value in self._data.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            elif isinstance(value, (int, float)):
                lines.append(f"{key} = {value}")
            elif isinstance(value, list):
                items = ", ".join(f'"{v}"' for v in value)
                lines.append(f"{key} = [{items}]")
            else:
                lines.append(f'{key} = "{value}"')
        self.path.write_text("\n".join(lines) + "\n")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if key in DEFAULTS:
            expected_type = type(DEFAULTS[key])
            if expected_type is bool and isinstance(value, str):
                value = value.lower() in ("true", "1", "yes")
            elif expected_type is int and isinstance(value, str):
                value = int(value)
            elif expected_type is float and isinstance(value, str):
                value = float(value)
        self._data[key] = value

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    @staticmethod
    def ensure_home() -> Path:
        CHOWKIDAR_HOME.mkdir(parents=True, exist_ok=True)
        (CHOWKIDAR_HOME / "logs").mkdir(exist_ok=True)
        return CHOWKIDAR_HOME
