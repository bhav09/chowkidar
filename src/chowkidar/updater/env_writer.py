"""Safe .env file modification with backup, file locking, and atomic writes."""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

logger = logging.getLogger(__name__)


def update_env_value(
    file_path: Path,
    variable_name: str,
    new_value: str,
    dry_run: bool = False,
) -> dict:
    """Update a variable's value in a .env file.

    Uses file locking, creates backup, and performs atomic write.
    Returns a dict with the operation result.
    """
    file_path = Path(file_path).resolve()

    if not file_path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    if not file_path.suffix == "" and not file_path.name.startswith(".env"):
        if file_path.suffix not in (".env",):
            logger.warning("File doesn't look like an env file: %s", file_path)

    lock_path = file_path.parent / f".{file_path.name}.chowkidar.lock"
    lock = FileLock(str(lock_path), timeout=10)

    try:
        with lock:
            content = file_path.read_text()
            lines = content.splitlines(keepends=True)

            updated_lines: list[str] = []
            found = False
            old_value = None

            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    if key == variable_name:
                        old_value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                        if old_value == new_value:
                            return {
                                "status": "no_change",
                                "message": f"{variable_name} already set to {new_value}",
                            }
                        found = True
                        if dry_run:
                            updated_lines.append(line)
                        else:
                            if stripped.split("=", 1)[1].strip().startswith('"'):
                                updated_lines.append(f'{variable_name}="{new_value}"\n')
                            elif stripped.split("=", 1)[1].strip().startswith("'"):
                                updated_lines.append(f"{variable_name}='{new_value}'\n")
                            else:
                                updated_lines.append(f"{variable_name}={new_value}\n")
                        continue
                updated_lines.append(line)

            if not found:
                return {
                    "status": "error",
                    "message": f"Variable '{variable_name}' not found in {file_path}",
                }

            if dry_run:
                return {
                    "status": "dry_run",
                    "file": str(file_path),
                    "variable": variable_name,
                    "old_value": old_value,
                    "new_value": new_value,
                    "message": f"Would update {variable_name}: {old_value} → {new_value}",
                }

            backup_path = file_path.parent / f"{file_path.name}.chowkidar.bak"
            if not backup_path.exists():
                import shutil
                shutil.copy2(str(file_path), str(backup_path))
                logger.info("Backup created: %s", backup_path)

            fd, tmp_path = tempfile.mkstemp(
                dir=str(file_path.parent),
                prefix=f".{file_path.name}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w") as f:
                    f.writelines(updated_lines)
                os.replace(tmp_path, str(file_path))
            except Exception:
                if Path(tmp_path).exists():
                    os.unlink(tmp_path)
                raise

            logger.info(
                "Updated %s: %s = %s → %s", file_path, variable_name, old_value, new_value
            )

            return {
                "status": "updated",
                "file": str(file_path),
                "variable": variable_name,
                "old_value": old_value,
                "new_value": new_value,
                "backup": str(backup_path),
                "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            }

    except TimeoutError:
        return {
            "status": "error",
            "message": f"Could not acquire lock on {file_path} (another process may be writing)",
        }
    except Exception as e:
        return {"status": "error", "message": f"Update failed: {e}"}
    finally:
        lock_path.unlink(missing_ok=True)


def rollback_env(file_path: Path) -> dict:
    """Restore a .env file from its Chowkidar backup."""
    file_path = Path(file_path).resolve()
    backup_path = file_path.parent / f"{file_path.name}.chowkidar.bak"

    if not backup_path.exists():
        return {"status": "error", "message": f"No backup found at {backup_path}"}

    try:
        backup_path.replace(file_path)
        return {"status": "restored", "file": str(file_path), "from_backup": str(backup_path)}
    except Exception as e:
        return {"status": "error", "message": f"Rollback failed: {e}"}
