"""Git operations for auto-fix: branch creation, commits, and PR opening."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, cwd=str(cwd), timeout=30,
        )
        output = result.stdout.strip() or result.stderr.strip()
        return result.returncode == 0, output
    except FileNotFoundError:
        return False, "git not found — install git first"
    except subprocess.TimeoutExpired:
        return False, "git command timed out"


def is_git_repo(project_path: Path) -> bool:
    ok, _ = _run_git(["rev-parse", "--is-inside-work-tree"], project_path)
    return ok


def has_clean_worktree(project_path: Path) -> bool:
    ok, output = _run_git(["status", "--porcelain"], project_path)
    return ok and output == ""


def create_branch(project_path: Path, branch_name: str) -> tuple[bool, str]:
    return _run_git(["checkout", "-b", branch_name], project_path)


def add_and_commit(project_path: Path, files: list[str], message: str) -> tuple[bool, str]:
    for f in files:
        ok, err = _run_git(["add", f], project_path)
        if not ok:
            return False, f"Failed to stage {f}: {err}"
    return _run_git(["commit", "-m", message], project_path)


def push_branch(project_path: Path) -> tuple[bool, str]:
    ok, branch_out = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], project_path)
    if not ok:
        return False, "Could not determine current branch"
    branch = branch_out.strip()
    return _run_git(["push", "-u", "origin", branch], project_path)


def create_pr(project_path: Path, title: str, body: str) -> tuple[bool, str]:
    """Create a GitHub PR using the gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "pr", "create", "--title", title, "--body", body],
            capture_output=True, text=True, cwd=str(project_path), timeout=30,
        )
        output = result.stdout.strip() or result.stderr.strip()
        return result.returncode == 0, output
    except FileNotFoundError:
        return False, "gh CLI not found — install GitHub CLI: https://cli.github.com"
    except subprocess.TimeoutExpired:
        return False, "gh pr create timed out"


def apply_fixes_and_pr(
    project_path: Path,
    updates: list[dict],
    do_push: bool = False,
    do_pr: bool = False,
) -> list[str]:
    """Apply model replacement fixes, optionally branch/push/PR.

    Returns list of status messages.
    """
    from .updater.env_writer import update_env_value

    messages: list[str] = []
    changed_files: list[str] = []

    branch_name = "chowkidar/fix-deprecated-models"

    if do_push or do_pr:
        if not is_git_repo(project_path):
            messages.append("ERROR: Not a git repository.")
            return messages

        ok, msg = create_branch(project_path, branch_name)
        if not ok and "already exists" not in msg:
            messages.append(f"ERROR creating branch: {msg}")
            return messages
        messages.append(f"Branch: {branch_name}")

    for u in updates:
        result = update_env_value(
            file_path=Path(u["file"]),
            variable_name=u["variable"],
            new_value=u["new_model"],
        )
        file_short = Path(u["file"]).name
        if result["status"] == "updated":
            messages.append(
                f"Updated {u['variable']}: {u['old_model']} → {u['new_model']} ({file_short})"
            )
            if u["file"] not in changed_files:
                changed_files.append(u["file"])
        else:
            messages.append(f"SKIP {u['variable']}: {result.get('message', 'failed')} ({file_short})")

    if not changed_files:
        messages.append("No files changed.")
        return messages

    if do_push or do_pr:
        model_list = ", ".join(u["old_model"] for u in updates[:5])
        commit_msg = f"chore: replace deprecated models ({model_list})"
        ok, msg = add_and_commit(project_path, changed_files, commit_msg)
        if ok:
            messages.append(f"Committed: {commit_msg}")
        else:
            messages.append(f"ERROR committing: {msg}")
            return messages

    if do_push or do_pr:
        ok, msg = push_branch(project_path)
        if ok:
            messages.append("Pushed to remote.")
        else:
            messages.append(f"ERROR pushing: {msg}")
            return messages

    if do_pr:
        pr_body = _build_pr_body(updates)
        ok, msg = create_pr(project_path, "fix: replace deprecated LLM models", pr_body)
        if ok:
            messages.append(f"PR created: {msg}")
        else:
            messages.append(f"ERROR creating PR: {msg}")

    return messages


def _build_pr_body(updates: list[dict]) -> str:
    lines = [
        "## Summary",
        "",
        "Chowkidar detected deprecated LLM models and auto-generated replacements.",
        "",
        "| Variable | Old Model | New Model | Confidence | Breaking? |",
        "|----------|-----------|-----------|------------|-----------|",
    ]
    for u in updates:
        breaking = "Yes" if u.get("breaking") else "No"
        lines.append(
            f"| {u['variable']} | {u['old_model']} | {u['new_model']} "
            f"| {u.get('confidence', 'medium')} | {breaking} |"
        )
    lines.extend([
        "",
        "---",
        "*Generated by [Chowkidar](https://github.com/bhavishya/chowkidar)*",
    ])
    return "\n".join(lines)
