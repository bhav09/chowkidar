"""Webhook notification support — Slack, Discord, and generic webhooks."""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)


def send_webhook(
    url: str,
    title: str,
    message: str,
    urgency: str = "normal",
    webhook_format: str = "generic",
) -> bool:
    """Send a notification via webhook. Returns True on success."""
    try:
        if webhook_format == "slack":
            return _send_slack(url, title, message, urgency)
        elif webhook_format == "discord":
            return _send_discord(url, title, message, urgency)
        else:
            return _send_generic(url, title, message, urgency)
    except Exception as e:
        logger.error("Webhook send failed: %s", e)
        return False


def _send_slack(url: str, title: str, message: str, urgency: str) -> bool:
    color = {"critical": "#dc3545", "normal": "#ffc107", "low": "#6c757d"}.get(urgency, "#ffc107")
    payload = {
        "attachments": [{
            "color": color,
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"🔔 {title}"},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message},
                },
            ],
        }],
    }
    resp = httpx.post(url, json=payload, timeout=10)
    return resp.status_code == 200


def _send_discord(url: str, title: str, message: str, urgency: str) -> bool:
    color_int = {"critical": 0xDC3545, "normal": 0xFFC107, "low": 0x6C757D}.get(urgency, 0xFFC107)
    payload = {
        "embeds": [{
            "title": title,
            "description": message,
            "color": color_int,
            "footer": {"text": "Chowkidar — LLM Deprecation Watchdog"},
        }],
    }
    resp = httpx.post(url, json=payload, timeout=10)
    return resp.status_code in (200, 204)


def _send_generic(url: str, title: str, message: str, urgency: str) -> bool:
    payload = {
        "title": title,
        "message": message,
        "urgency": urgency,
        "source": "chowkidar",
    }
    resp = httpx.post(
        url,
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    return 200 <= resp.status_code < 300
