"""Background daemon that periodically scans, syncs, checks, and notifies."""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

import schedule

from ..config import CHOWKIDAR_HOME, Config
from ..ide.rules_writer import write_rules_for_project
from ..providers.anthropic_provider import AnthropicProvider
from ..providers.google_provider import GoogleProvider
from ..providers.mistral_provider import MistralProvider
from ..providers.openai_provider import OpenAIProvider
from ..registry.db import Registry
from ..scanner import scan_directory
from .notifier import notify
from .webhook import send_webhook

logger = logging.getLogger(__name__)


class ChowkidarDaemon:
    """Main daemon loop: scan -> sync -> check -> notify -> write rules."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.registry = Registry()
        self.registry.init_db()
        self._running = False
        self._setup_logging()

    def _setup_logging(self) -> None:
        log_dir = CHOWKIDAR_HOME / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "daemon.log", maxBytes=5 * 1024 * 1024, backupCount=3,
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        root_logger = logging.getLogger("chowkidar")
        root_logger.addHandler(handler)
        root_logger.setLevel(self.config.get("log_level", "INFO"))

    def run(self) -> None:
        """Start the daemon loop (blocking)."""
        logger.info("Chowkidar daemon starting...")
        self._running = True

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._run_cycle()

        scan_hours = self.config.get("scan_interval_hours", 4)
        sync_hours = self.config.get("sync_interval_hours", 24)

        schedule.every(scan_hours).hours.do(self._run_scan_check)
        schedule.every(sync_hours).hours.do(self._run_sync)

        logger.info("Daemon running. Scan every %dh, sync every %dh.", scan_hours, sync_hours)

        while self._running:
            schedule.run_pending()
            time.sleep(60)

        logger.info("Chowkidar daemon stopped.")

    def _handle_signal(self, signum: int, frame) -> None:
        logger.info("Received signal %d, shutting down...", signum)
        self._running = False

    def _run_cycle(self) -> None:
        """Run a full cycle: sync + scan + check."""
        self._run_sync()
        self._run_scan_check()

    def _run_sync(self) -> None:
        """Fetch latest deprecation data from all providers."""
        logger.info("Starting provider sync...")
        try:
            asyncio.run(self._async_sync())
            logger.info("Provider sync complete.")
        except Exception as e:
            logger.error("Provider sync failed: %s", e)

    async def _async_sync(self) -> None:
        providers = []
        enabled = self.config.get("providers", ["openai", "anthropic", "google", "mistral"])

        if "openai" in enabled:
            providers.append(OpenAIProvider())
        if "anthropic" in enabled:
            providers.append(AnthropicProvider())
        if "google" in enabled:
            providers.append(GoogleProvider())
        if "mistral" in enabled:
            providers.append(MistralProvider())

        for provider in providers:
            try:
                deprecations = await provider.fetch_deprecations()
                for dep in deprecations:
                    self.registry.upsert_model(
                        model_id=dep.model_id,
                        provider=dep.provider,
                        sunset_date=dep.sunset_date,
                        replacement=dep.replacement,
                        replacement_confidence=dep.replacement_confidence,
                        breaking_changes=dep.breaking_changes,
                        source_url=dep.source_url,
                    )
                logger.info("Synced %d deprecations from %s", len(deprecations), provider.name)
            except Exception as e:
                logger.error("Failed to sync %s: %s", provider.name, e)

    def _run_scan_check(self) -> None:
        """Scan all watched projects, check for deprecations, notify."""
        projects = self.registry.get_watched_projects()
        if not projects:
            logger.info("No watched projects.")
            return

        for project_path in projects:
            try:
                self._check_project(project_path)
                self.registry.update_watch_timestamp(project_path)
            except Exception as e:
                logger.error("Error checking project %s: %s", project_path, e)

    def _check_project(self, project_path: str) -> None:
        """Scan a project and fire notifications for deprecated models."""
        logger.info("Scanning project: %s", project_path)
        scan_result = scan_directory(project_path)

        if scan_result.total_count == 0:
            return

        self.registry.save_scan_results(project_path, scan_result.all_models)

        deprecations_found: list[dict] = []

        for model_info in scan_result.all_models:
            canonical = model_info["canonical"]

            if self.registry.is_pinned(canonical):
                continue
            if self.registry.is_snoozed(canonical):
                continue

            model_record = self.registry.get_model(canonical)
            if model_record is None or model_record.sunset_date is None:
                continue

            try:
                sunset = datetime.fromisoformat(model_record.sunset_date)
            except ValueError:
                continue

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            days_until = (sunset - now).days

            if days_until > 90:
                continue

            threshold = self._determine_threshold(days_until)
            cooldown = self.config.get("notification_cooldown_hours", 24)

            if not self.registry.is_recently_notified(project_path, canonical, threshold, cooldown):
                self._send_notification(model_info, model_record, days_until, threshold, project_path)
                self.registry.log_notification(project_path, canonical, threshold)

            deprecations_found.append({
                "variable": model_info["variable"],
                "file": model_info["file"],
                "model": model_info["model"],
                "canonical": canonical,
                "sunset_date": model_record.sunset_date,
                "replacement": model_record.replacement,
                "replacement_confidence": model_record.replacement_confidence,
                "breaking_changes": model_record.breaking_changes,
                "days_until": days_until,
            })

        if deprecations_found and self.config.get("write_rules", True):
            try:
                write_rules_for_project(Path(project_path), deprecations_found, self.config)
            except Exception as e:
                logger.error("Failed to write IDE rules for %s: %s", project_path, e)

    @staticmethod
    def _determine_threshold(days_until: int) -> str:
        if days_until <= 0:
            return "sunset"
        elif days_until <= 7:
            return "7d"
        elif days_until <= 30:
            return "30d"
        else:
            return "90d"

    @staticmethod
    def _send_notification(
        model_info: dict, model_record, days_until: int, threshold: str, project_path: str,
    ) -> None:
        project_name = Path(project_path).name
        model_name = model_info["model"]
        variable = model_info["variable"]

        if threshold == "sunset":
            urgency = "critical"
            title = f"MODEL SUNSET: {model_name}"
            message = (
                f"'{model_name}' in {project_name} ({variable}) has reached its sunset date! "
                f"Replace with: {model_record.replacement or 'check provider docs'}"
            )
        elif threshold == "7d":
            urgency = "critical"
            title = f"Model sunset in {days_until}d: {model_name}"
            message = (
                f"'{model_name}' in {project_name} ({variable}) sunsets in {days_until} days. "
                f"Replace with: {model_record.replacement or 'check provider docs'}"
            )
        elif threshold == "30d":
            urgency = "normal"
            title = f"Model sunsetting: {model_name}"
            message = (
                f"'{model_name}' in {project_name} ({variable}) sunsets in {days_until} days. "
                f"Consider switching to: {model_record.replacement or 'a newer model'}"
            )
        else:
            urgency = "low"
            title = f"Model deprecation notice: {model_name}"
            message = f"'{model_name}' in {project_name} will sunset in {days_until} days."

        notify(title, message, urgency)

        webhook_url = ChowkidarDaemon._get_webhook_url()
        if webhook_url:
            webhook_fmt = "generic"
            try:
                from ..config import Config
                cfg = Config()
                webhook_fmt = cfg.get("webhook_format", "generic")
            except Exception:
                pass
            send_webhook(webhook_url, title, message, urgency, webhook_fmt)

    @staticmethod
    def _get_webhook_url() -> str:
        try:
            from ..config import Config
            cfg = Config()
            return cfg.get("webhook_url", "") or ""
        except Exception:
            return ""
