"""Writes and manages IDE rules files for all detected editors."""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import Config
from .detector import detect_editors, ensure_editor_dirs
from .templates.claude_code import generate_claude_rules
from .templates.copilot import generate_copilot_section, inject_into_copilot_file
from .templates.cursor import generate_cursor_rules
from .templates.windsurf import generate_windsurf_section, inject_into_windsurf_file

logger = logging.getLogger(__name__)

RULES_FILES: dict[str, str] = {
    "cursor": ".cursor/rules/chowkidar-alerts.mdc",
    "claude_code": ".claude/rules/chowkidar-alerts.md",
    "copilot": ".github/copilot-instructions.md",
    "windsurf": ".windsurfrules",
}


def write_rules_for_project(
    project_path: Path,
    deprecations: list[dict],
    config: Config | None = None,
) -> list[str]:
    """Write rules files for all detected editors in a project.

    Returns list of files written/updated.
    """
    config = config or Config()
    if not config.get("write_rules", True):
        return []

    if not deprecations:
        return []

    editors = detect_editors(project_path)
    if not editors:
        editors = ["cursor", "claude_code"]

    written: list[str] = []

    for editor in editors:
        try:
            file_written = _write_editor_rules(project_path, editor, deprecations, config)
            if file_written:
                written.append(file_written)
        except Exception as e:
            logger.error("Failed to write rules for %s: %s", editor, e)

    if config.get("gitignore_rules", True):
        _update_gitignore(project_path, written)

    return written


def _write_editor_rules(
    project_path: Path, editor: str, deprecations: list[dict], config: Config,
) -> str | None:
    """Write rules for a specific editor. Returns the file path written, or None."""
    ensure_editor_dirs(project_path, editor)

    if editor == "cursor":
        content = generate_cursor_rules(deprecations)
        file_path = project_path / RULES_FILES["cursor"]
        file_path.write_text(content)
        logger.info("Wrote Cursor rules: %s", file_path)
        return str(file_path.relative_to(project_path))

    elif editor == "claude_code":
        content = generate_claude_rules(deprecations)
        file_path = project_path / RULES_FILES["claude_code"]
        file_path.write_text(content)
        logger.info("Wrote Claude Code rules: %s", file_path)
        return str(file_path.relative_to(project_path))

    elif editor == "copilot":
        file_path = project_path / RULES_FILES["copilot"]
        section = generate_copilot_section(deprecations)
        if file_path.exists():
            existing = file_path.read_text()
            content = inject_into_copilot_file(existing, section)
        else:
            content = section + "\n"
        file_path.write_text(content)
        logger.info("Updated Copilot instructions: %s", file_path)
        return str(file_path.relative_to(project_path))

    elif editor == "windsurf":
        file_path = project_path / RULES_FILES["windsurf"]
        section = generate_windsurf_section(deprecations)
        if file_path.exists():
            existing = file_path.read_text()
            content = inject_into_windsurf_file(existing, section)
        else:
            content = section + "\n"
        file_path.write_text(content)
        logger.info("Updated Windsurf rules: %s", file_path)
        return str(file_path.relative_to(project_path))

    return None


def clean_rules(project_path: Path) -> list[str]:
    """Remove all Chowkidar-generated rules files from a project."""
    removed: list[str] = []

    for editor, rel_path in RULES_FILES.items():
        file_path = project_path / rel_path
        if not file_path.exists():
            continue

        if editor in ("cursor", "claude_code"):
            file_path.unlink()
            removed.append(rel_path)
        elif editor in ("copilot", "windsurf"):
            content = file_path.read_text()
            marker_mod = {
                "copilot": ("<!-- chowkidar:start -->", "<!-- chowkidar:end -->"),
                "windsurf": ("# --- chowkidar:start ---", "# --- chowkidar:end ---"),
            }
            start_marker, end_marker = marker_mod[editor]
            if start_marker in content:
                before = content.split(start_marker)[0].rstrip()
                after_parts = content.split(end_marker)
                after = after_parts[1].lstrip() if len(after_parts) > 1 else ""
                cleaned = (before + "\n\n" + after).strip()
                if cleaned:
                    file_path.write_text(cleaned + "\n")
                else:
                    file_path.unlink()
                removed.append(rel_path)

    return removed


def _update_gitignore(project_path: Path, rules_files: list[str]) -> None:
    """Add Chowkidar rules files to .gitignore if not already there."""
    gitignore = project_path / ".gitignore"
    existing_lines: set[str] = set()

    if gitignore.exists():
        existing_lines = set(gitignore.read_text().splitlines())

    new_entries: list[str] = []
    for rel_path in rules_files:
        if rel_path not in existing_lines and f"/{rel_path}" not in existing_lines:
            new_entries.append(rel_path)

    if new_entries:
        with open(gitignore, "a") as f:
            if existing_lines and "" not in existing_lines:
                f.write("\n")
            f.write("# Chowkidar auto-generated IDE rules\n")
            for entry in new_entries:
                f.write(f"{entry}\n")
