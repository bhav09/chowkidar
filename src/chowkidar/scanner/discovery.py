"""Repository discovery module for Chowkidar."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_IGNORED_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    "target",
    "__pycache__",
    ".idea",
    ".vscode",
    ".cache",
    ".npm",
    ".cargo",
    ".rustup",
    "Library",
    "Applications",
    "Downloads",
    "miniconda3",
    "anaconda3",
}


def discover_repositories(
    roots: list[str | Path],
    max_depth: int = 4,
    ignore_patterns: set[str] | None = None,
) -> list[Path]:
    """Search roots for Git repositories up to max_depth.
    
    Prunes ignored directories and stops recursing once a Git repository root is found.
    """
    discovered: list[Path] = []
    ignored = ignore_patterns if ignore_patterns is not None else DEFAULT_IGNORED_DIRS

    for root_str in roots:
        root_path = Path(root_str).expanduser().resolve()
        if not root_path.exists() or not root_path.is_dir():
            logger.debug("Discovery root does not exist or is not a directory: %s", root_path)
            continue

        logger.info("Scanning for repositories in: %s (max_depth=%d)", root_path, max_depth)
        _search_dir(root_path, max_depth, 0, ignored, discovered)

    return sorted(list(set(discovered)))


def _search_dir(
    current_dir: Path,
    max_depth: int,
    current_depth: int,
    ignored: set[str],
    discovered: list[Path],
) -> None:
    """Recursively search a directory using DFS, with depth tracking and directory pruning."""
    if current_depth > max_depth:
        return

    try:
        # Check if current_dir is a Git repository
        git_dir = current_dir / ".git"
        if git_dir.exists() and git_dir.is_dir():
            discovered.append(current_dir)
            logger.debug("Discovered Git repository: %s", current_dir)
            return  # Prune search below git root

        # Otherwise, scan subdirectories
        for entry in current_dir.iterdir():
            if entry.is_dir():
                if entry.name in ignored:
                    continue
                # Skip symlinks to prevent infinite loops or escaping roots
                if entry.is_symlink():
                    continue
                _search_dir(entry, max_depth, current_depth + 1, ignored, discovered)
    except PermissionError:
        logger.debug("Permission denied: %s", current_dir)
    except OSError as e:
        logger.debug("OS error scanning directory %s: %s", current_dir, e)
