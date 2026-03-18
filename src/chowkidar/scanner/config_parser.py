"""Parse YAML, TOML, JSON, and source files for model strings."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .patterns import find_model_strings

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class ConfigModelEntry:
    """A model string found in a config file."""

    file_path: str
    key_path: str
    model_value: str
    line_number: int | None = None


def parse_yaml_file(path: Path) -> list[ConfigModelEntry]:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    return _walk_dict(data, str(path), "")


def parse_toml_file(path: Path) -> list[ConfigModelEntry]:
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (Exception,):
        return []
    return _walk_dict(data, str(path), "")


def parse_json_file(path: Path) -> list[ConfigModelEntry]:
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    return _walk_dict(data, str(path), "")


def _walk_dict(data: dict[str, Any], file_path: str, prefix: str) -> list[ConfigModelEntry]:
    """Recursively walk a dict and find model strings in string values."""
    entries: list[ConfigModelEntry] = []
    for key, value in data.items():
        current_path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, str):
            models = find_model_strings(value)
            for model in models:
                entries.append(
                    ConfigModelEntry(file_path=file_path, key_path=current_path, model_value=model)
                )
        elif isinstance(value, dict):
            entries.extend(_walk_dict(value, file_path, current_path))
        elif isinstance(value, list):
            entries.extend(_walk_list(value, file_path, current_path))
    return entries


def _walk_list(data: list[Any], file_path: str, prefix: str) -> list[ConfigModelEntry]:
    entries: list[ConfigModelEntry] = []
    for i, value in enumerate(data):
        current_path = f"{prefix}[{i}]"
        if isinstance(value, str):
            models = find_model_strings(value)
            for model in models:
                entries.append(
                    ConfigModelEntry(file_path=file_path, key_path=current_path, model_value=model)
                )
        elif isinstance(value, dict):
            entries.extend(_walk_dict(value, file_path, current_path))
        elif isinstance(value, list):
            entries.extend(_walk_list(value, file_path, current_path))
    return entries


_SOURCE_STRING_PATTERN = re.compile(r"""(?:["'])([^"']+)(?:["'])""")

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".egg-info", ".chowkidar",
}


def parse_source_file(path: Path) -> list[ConfigModelEntry]:
    """Scan a source file (py, js, ts, etc.) for string literals containing model names."""
    entries: list[ConfigModelEntry] = []
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except OSError:
        return []

    for line_num, line in enumerate(lines, start=1):
        for string_match in _SOURCE_STRING_PATTERN.finditer(line):
            candidate = string_match.group(1)
            models = find_model_strings(candidate)
            for model in models:
                entries.append(
                    ConfigModelEntry(
                        file_path=str(path),
                        key_path=f"L{line_num}",
                        model_value=model,
                        line_number=line_num,
                    )
                )
    return entries


def discover_config_files(directory: Path) -> dict[str, list[Path]]:
    """Discover config and source files grouped by type."""
    found: dict[str, list[Path]] = {"yaml": [], "toml": [], "json": [], "source": []}

    yaml_names = {"config.yml", "config.yaml", "settings.yml", "settings.yaml",
                  "docker-compose.yml", "docker-compose.yaml"}
    toml_names = {"pyproject.toml", "config.toml", "settings.toml"}
    json_names = {"config.json", "settings.json", "package.json", "tsconfig.json"}
    source_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".mjs"}

    for f in directory.rglob("*"):
        if any(skip in f.parts for skip in SKIP_DIRS):
            continue
        if not f.is_file():
            continue

        name_lower = f.name.lower()
        if name_lower in yaml_names or f.suffix in {".yml", ".yaml"}:
            found["yaml"].append(f)
        elif name_lower in toml_names:
            found["toml"].append(f)
        elif name_lower in json_names:
            found["json"].append(f)
        elif f.suffix in source_exts:
            found["source"].append(f)

    return found
