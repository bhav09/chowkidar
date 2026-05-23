"""Structured local config writers for model references."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from filelock import FileLock

from .env_writer import update_env_value

_PATH_PART_RE = re.compile(r"([^\.\[\]]+)|\[(\d+)\]")


def update_model_reference(
    file_path: Path,
    key_path: str,
    new_value: str,
    *,
    dry_run: bool = False,
) -> dict:
    """Update a model reference in a supported structured config file."""
    file_path = Path(file_path).resolve()
    target_type = detect_target_type(file_path)
    if target_type == "env":
        return update_env_value(file_path, key_path, new_value, dry_run=dry_run)
    if target_type in {"yaml", "docker-compose"}:
        return _update_yaml_value(file_path, key_path, new_value, target_type, dry_run)
    if target_type == "json":
        return _update_json_value(file_path, key_path, new_value, dry_run)
    if target_type == "toml":
        return _update_toml_value(file_path, key_path, new_value, dry_run)
    return {"status": "error", "message": f"Unsupported structured file type: {file_path}"}


def detect_target_type(file_path: Path) -> str:
    name = file_path.name.lower()
    suffix = file_path.suffix.lower()
    if name.startswith(".env") or suffix == ".env":
        return "env"
    if name in {"docker-compose.yml", "docker-compose.yaml"}:
        return "docker-compose"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".json":
        return "json"
    if suffix == ".toml":
        return "toml"
    return "unsupported"


def _update_json_value(file_path: Path, key_path: str, new_value: str, dry_run: bool) -> dict:
    try:
        data = json.loads(file_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "error", "message": f"Could not parse JSON: {exc}"}

    return _update_nested_data(
        file_path,
        key_path,
        new_value,
        data,
        target_type="json",
        serializer=lambda d: json.dumps(d, indent=2) + "\n",
        dry_run=dry_run,
    )


def _update_yaml_value(
    file_path: Path,
    key_path: str,
    new_value: str,
    target_type: str,
    dry_run: bool,
) -> dict:
    try:
        data = yaml.safe_load(file_path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        return {"status": "error", "message": f"Could not parse YAML: {exc}"}

    return _update_nested_data(
        file_path,
        key_path,
        new_value,
        data,
        target_type=target_type,
        serializer=lambda d: yaml.safe_dump(d, sort_keys=False),
        dry_run=dry_run,
    )


def _update_nested_data(
    file_path: Path,
    key_path: str,
    new_value: str,
    data: Any,
    *,
    target_type: str,
    serializer,
    dry_run: bool,
) -> dict:
    parts = _parse_key_path(key_path)
    if not parts:
        return {"status": "error", "message": f"Unsupported or ambiguous key path: {key_path}"}

    try:
        parent, final_key = _resolve_parent(data, parts)
        old_value = parent[final_key]
    except (KeyError, IndexError, TypeError) as exc:
        return {"status": "error", "message": f"Could not resolve key path '{key_path}': {exc}"}

    if old_value == new_value:
        return {"status": "no_change", "message": f"{key_path} already set to {new_value}"}

    if dry_run:
        return _result("dry_run", file_path, key_path, old_value, new_value, target_type)

    parent[final_key] = new_value
    return _write_with_backup(file_path, serializer(data), key_path, old_value, new_value, target_type)


def _update_toml_value(file_path: Path, key_path: str, new_value: str, dry_run: bool) -> dict:
    """Conservatively update simple TOML string assignments while preserving most formatting."""
    try:
        content = file_path.read_text()
    except OSError as exc:
        return {"status": "error", "message": f"Could not read TOML: {exc}"}

    section_parts = key_path.split(".")
    key = section_parts[-1]
    section = ".".join(section_parts[:-1])
    current_section = ""
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*)(['\"]?)([^'\"]+)(['\"]?)(\s*(?:#.*)?)$")
    lines = content.splitlines(keepends=True)
    matches: list[tuple[int, str]] = []

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped.strip("[]")
            continue
        if section and current_section != section:
            continue
        match = pattern.match(line.rstrip("\n"))
        if match:
            matches.append((idx, match.group(3).strip()))

    if len(matches) != 1:
        return {"status": "error", "message": f"Ambiguous or missing TOML key path: {key_path}"}

    idx, old_value = matches[0]
    if old_value == new_value:
        return {"status": "no_change", "message": f"{key_path} already set to {new_value}"}
    if dry_run:
        return _result("dry_run", file_path, key_path, old_value, new_value, "toml")

    original = lines[idx].rstrip("\n")
    updated = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}{new_value}{m.group(4)}{m.group(5)}", original)
    lines[idx] = updated + ("\n" if lines[idx].endswith("\n") else "")
    return _write_with_backup(file_path, "".join(lines), key_path, old_value, new_value, "toml")


def _parse_key_path(key_path: str) -> list[str | int]:
    if key_path.startswith("L"):
        return []
    parts: list[str | int] = []
    for raw_part in key_path.split("."):
        for match in _PATH_PART_RE.finditer(raw_part):
            name, index = match.groups()
            parts.append(int(index) if index is not None else name)
    return parts


def _resolve_parent(data: Any, parts: list[str | int]) -> tuple[Any, str | int]:
    current = data
    for part in parts[:-1]:
        current = current[part]
    return current, parts[-1]


def _write_with_backup(
    file_path: Path,
    content: str,
    key_path: str,
    old_value: Any,
    new_value: str,
    target_type: str,
) -> dict:
    lock_path = file_path.parent / f".{file_path.name}.chowkidar.lock"
    lock = FileLock(str(lock_path), timeout=10)
    try:
        with lock:
            backup_path = file_path.parent / f"{file_path.name}.chowkidar.bak"
            if not backup_path.exists():
                shutil.copy2(str(file_path), str(backup_path))

            fd, tmp_path = tempfile.mkstemp(
                dir=str(file_path.parent),
                prefix=f".{file_path.name}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(content)
                os.replace(tmp_path, str(file_path))
            except Exception:
                if Path(tmp_path).exists():
                    os.unlink(tmp_path)
                raise
    except TimeoutError:
        return {"status": "error", "message": f"Could not acquire lock on {file_path}"}
    except Exception as exc:
        return {"status": "error", "message": f"Update failed: {exc}"}
    finally:
        lock_path.unlink(missing_ok=True)

    result = _result("updated", file_path, key_path, old_value, new_value, target_type)
    result["backup"] = str(backup_path)
    result["timestamp"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    return result


def _result(
    status: str,
    file_path: Path,
    key_path: str,
    old_value: Any,
    new_value: str,
    target_type: str,
) -> dict:
    return {
        "status": status,
        "file": str(file_path),
        "variable": key_path,
        "old_value": str(old_value),
        "new_value": new_value,
        "target_type": target_type,
        "message": f"Would update {key_path}: {old_value} -> {new_value}"
        if status == "dry_run"
        else f"Updated {key_path}: {old_value} -> {new_value}",
    }
