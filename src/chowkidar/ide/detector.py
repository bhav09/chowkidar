"""Detect which AI-enabled editors are in use for a project."""

from __future__ import annotations

from pathlib import Path

EDITOR_INDICATORS: dict[str, list[str]] = {
    "cursor": [".cursor"],
    "claude_code": [".claude"],
    "copilot": [".github"],
    "windsurf": [".windsurf", ".windsurfrules"],
}


def detect_editors(project_path: Path) -> list[str]:
    """Detect which editors have config directories in the project.

    Always returns at least the editors whose directories exist.
    Also checks home directory for global editor configs.
    """
    found: list[str] = []

    for editor, indicators in EDITOR_INDICATORS.items():
        for indicator in indicators:
            if (project_path / indicator).exists():
                found.append(editor)
                break

    if not found:
        home = Path.home()
        if (home / ".cursor").exists():
            found.append("cursor")
        if (home / ".claude").exists():
            found.append("claude_code")

    return found


def ensure_editor_dirs(project_path: Path, editor: str) -> Path:
    """Create the necessary directories for an editor's rules."""
    if editor == "cursor":
        rules_dir = project_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        return rules_dir
    elif editor == "claude_code":
        rules_dir = project_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        return rules_dir
    elif editor == "copilot":
        github_dir = project_path / ".github"
        github_dir.mkdir(parents=True, exist_ok=True)
        return github_dir
    elif editor == "windsurf":
        return project_path
    else:
        return project_path
