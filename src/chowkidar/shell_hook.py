"""Shell hook installer — triggers deprecation warnings on cd."""

from __future__ import annotations

import platform
import shutil
from pathlib import Path

MARKER_START = "# >>> chowkidar cd hook >>>"
MARKER_END = "# <<< chowkidar cd hook <<<"

ZSH_HOOK = f"""{MARKER_START}
chowkidar_cd_hook() {{ command chowkidar check --quiet "$PWD" 2>/dev/null; }}
chpwd_functions+=(chowkidar_cd_hook)
{MARKER_END}"""

BASH_HOOK = f"""{MARKER_START}
_chowkidar_cd_hook() {{ command chowkidar check --quiet "$PWD" 2>/dev/null; }}
if [[ ! "$PROMPT_COMMAND" == *_chowkidar_cd_hook* ]]; then
    PROMPT_COMMAND="_chowkidar_cd_hook;${{PROMPT_COMMAND}}"
fi
{MARKER_END}"""


def _get_rc_files() -> list[Path]:
    home = Path.home()
    candidates = []
    shell = _detect_shell()
    if shell == "zsh":
        candidates.append(home / ".zshrc")
    elif shell == "bash":
        if platform.system() == "Darwin":
            candidates.append(home / ".bash_profile")
        candidates.append(home / ".bashrc")
    else:
        candidates.append(home / ".zshrc")
        candidates.append(home / ".bashrc")
    return candidates


def _detect_shell() -> str:
    import os
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return "zsh"
    if "bash" in shell:
        return "bash"
    if shutil.which("zsh"):
        return "zsh"
    return "bash"


def install_hook() -> tuple[bool, str]:
    """Install the cd hook into the user's shell RC file."""
    shell = _detect_shell()
    hook_text = ZSH_HOOK if shell == "zsh" else BASH_HOOK
    rc_files = _get_rc_files()

    for rc_path in rc_files:
        if rc_path.exists():
            content = rc_path.read_text()
            if MARKER_START in content:
                return True, f"Hook already installed in {rc_path}"
            rc_path.write_text(content.rstrip() + "\n\n" + hook_text + "\n")
            return True, f"Hook installed in {rc_path}. Restart your shell or run: source {rc_path}"

    rc_path = rc_files[0]
    rc_path.write_text(hook_text + "\n")
    return True, f"Created {rc_path} with cd hook."


def uninstall_hook() -> tuple[bool, str]:
    """Remove the cd hook from shell RC files."""
    removed_from: list[str] = []
    rc_candidates = [
        Path.home() / ".zshrc",
        Path.home() / ".bashrc",
        Path.home() / ".bash_profile",
    ]

    for rc_path in rc_candidates:
        if not rc_path.exists():
            continue
        content = rc_path.read_text()
        if MARKER_START not in content:
            continue
        lines = content.split("\n")
        new_lines: list[str] = []
        inside_block = False
        for line in lines:
            if line.strip() == MARKER_START:
                inside_block = True
                continue
            if line.strip() == MARKER_END:
                inside_block = False
                continue
            if not inside_block:
                new_lines.append(line)
        rc_path.write_text("\n".join(new_lines))
        removed_from.append(str(rc_path))

    if removed_from:
        return True, f"Hook removed from: {', '.join(removed_from)}"
    return False, "No Chowkidar hook found in shell RC files."
