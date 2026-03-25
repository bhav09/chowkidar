"""Tests for the git operations module."""


from chowkidar.git_ops import _build_pr_body, is_git_repo


def test_is_git_repo_false(tmp_path):
    assert is_git_repo(tmp_path) is False


def test_build_pr_body():
    updates = [
        {"variable": "MODEL", "old_model": "gpt-3.5-turbo", "new_model": "gpt-4o-mini",
         "confidence": "high", "breaking": False},
    ]
    body = _build_pr_body(updates)
    assert "gpt-3.5-turbo" in body
    assert "gpt-4o-mini" in body
    assert "Summary" in body
    assert "Chowkidar" in body


def test_build_pr_body_breaking():
    updates = [
        {"variable": "M", "old_model": "a", "new_model": "b", "confidence": "medium", "breaking": True},
    ]
    body = _build_pr_body(updates)
    assert "Yes" in body
