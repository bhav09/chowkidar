"""Tests for the webhook notification module."""

from unittest.mock import patch

import pytest

from chowkidar.sentinel.webhook import send_webhook


@pytest.fixture
def mock_httpx():
    with patch("chowkidar.sentinel.webhook.httpx") as m:
        m.post.return_value.status_code = 200
        yield m


def test_send_slack(mock_httpx):
    result = send_webhook("https://hooks.slack.com/test", "Test Title", "Test message", "normal", "slack")
    assert result is True
    mock_httpx.post.assert_called_once()
    call_kwargs = mock_httpx.post.call_args
    assert "attachments" in call_kwargs.kwargs.get("json", call_kwargs[1].get("json", {}))


def test_send_discord(mock_httpx):
    mock_httpx.post.return_value.status_code = 204
    result = send_webhook("https://discord.com/api/webhooks/test", "Title", "Msg", "critical", "discord")
    assert result is True


def test_send_generic(mock_httpx):
    result = send_webhook("https://example.com/hook", "Title", "Msg", "low", "generic")
    assert result is True


def test_send_fails_gracefully():
    with patch("chowkidar.sentinel.webhook.httpx") as m:
        m.post.side_effect = Exception("Connection refused")
        result = send_webhook("https://bad.url/hook", "Title", "Msg")
        assert result is False
