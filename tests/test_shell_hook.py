"""Tests for the shell hook module."""

from chowkidar.shell_hook import BASH_HOOK, MARKER_END, MARKER_START, ZSH_HOOK


def test_hook_markers():
    assert MARKER_START in ZSH_HOOK
    assert MARKER_END in ZSH_HOOK
    assert MARKER_START in BASH_HOOK
    assert MARKER_END in BASH_HOOK


def test_zsh_hook_has_chpwd():
    assert "chpwd_functions" in ZSH_HOOK


def test_bash_hook_has_prompt_command():
    assert "PROMPT_COMMAND" in BASH_HOOK


def test_hooks_contain_chowkidar_check():
    assert "chowkidar check" in ZSH_HOOK
    assert "chowkidar check" in BASH_HOOK
