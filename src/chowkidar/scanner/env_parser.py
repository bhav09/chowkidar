"""Parse .env files and extract model-related key-value pairs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from .patterns import find_model_strings, is_model_string, is_model_variable_name


@dataclass
class EnvModelEntry:
    """A model string found in an env file."""

    file_path: str
    variable_name: str
    model_value: str
    line_number: int | None = None


def parse_env_file(path: Path) -> list[EnvModelEntry]:
    """Parse a single .env file and return model-related entries."""
    entries: list[EnvModelEntry] = []
    values = dotenv_values(path)

    line_map = _build_line_map(path)

    for var_name, value in values.items():
        if value is None:
            continue
        if is_model_string(value) or is_model_variable_name(var_name):
            models = find_model_strings(value)
            if models:
                for model in models:
                    entries.append(
                        EnvModelEntry(
                            file_path=str(path),
                            variable_name=var_name,
                            model_value=model,
                            line_number=line_map.get(var_name),
                        )
                    )
    return entries


def _build_line_map(path: Path) -> dict[str, int]:
    """Map variable names to line numbers in the env file."""
    line_map: dict[str, int] = {}
    try:
        for i, line in enumerate(path.read_text().splitlines(), start=1):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                var_name = line.split("=", 1)[0].strip()
                line_map[var_name] = i
    except OSError:
        pass
    return line_map


_ENV_EXCLUDE_SUFFIXES = {".bak", ".lock", ".tmp", ".orig", ".swp", ".swo"}
_ENV_EXCLUDE_SUBSTRINGS = {"chowkidar.bak", "chowkidar.lock"}

_VALID_ENV_NAMES = {
    ".env", ".env.local", ".env.development", ".env.production",
    ".env.staging", ".env.test", ".env.example",
}


def _is_valid_env_file(f: Path) -> bool:
    """Check if a file is a legitimate .env file (not a backup, lock, or temp file)."""
    name = f.name
    if any(name.endswith(s) for s in _ENV_EXCLUDE_SUFFIXES):
        return False
    if any(sub in name for sub in _ENV_EXCLUDE_SUBSTRINGS):
        return False
    if name in _VALID_ENV_NAMES:
        return True
    if name == ".env" or (name.startswith(".env.") and name.count(".") == 2):
        return True
    return False


def discover_env_files(directory: Path) -> list[Path]:
    """Find all .env-style files in a directory (non-recursive at root, recursive in src/)."""
    env_files: list[Path] = []

    for pattern in _VALID_ENV_NAMES:
        candidate = directory / pattern
        if candidate.is_file():
            env_files.append(candidate)

    for f in directory.rglob(".env*"):
        if f.is_file() and f not in env_files and _is_valid_env_file(f):
            if ".git" not in f.parts and "node_modules" not in f.parts:
                env_files.append(f)

    return env_files
