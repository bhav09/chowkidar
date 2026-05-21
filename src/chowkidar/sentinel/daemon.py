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

from ..advisor import get_project_advisory
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
        """Scan a project and fire a consolidated folder-level notification for deprecated models."""
        logger.info("Scanning project: %s", project_path)
        scan_result = scan_directory(project_path)

        if scan_result.total_count == 0:
            return

        self.registry.save_scan_results(project_path, scan_result.all_models)

        expiring_models: list[dict] = []
        max_days = -999999
        max_threshold = "90d"

        # Determine which scanned models are actually expiring and calculate days/thresholds
        for model_info in scan_result.all_models:
            canonical = model_info["canonical"]

            if self.registry.is_pinned(canonical) or self.registry.is_snoozed(canonical):
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
            
            # Map threshold to precedence for overall project severity
            threshold_precedence = {"sunset": 4, "7d": 3, "30d": 2, "90d": 1}
            if threshold_precedence.get(threshold, 0) > threshold_precedence.get(max_threshold, 0):
                max_threshold = threshold

            expiring_models.append({
                "variable": model_info["variable"],
                "file": model_info["file"],
                "model": model_info["model"],
                "canonical": canonical,
                "sunset_date": model_record.sunset_date,
                "replacement": model_record.replacement,
                "replacement_confidence": model_record.replacement_confidence,
                "breaking_changes": model_record.breaking_changes,
                "days_until": days_until,
                "threshold": threshold,
            })

        if not expiring_models:
            return

        # Generate the context-aware advisor recommendations (utilizes local Gemma/heuristics + cache)
        advisory = get_project_advisory(project_path, expiring_models, self.registry, self.config)

        #Consolidated notification cooldown logic per project folder at the highest threshold
        cooldown = self.config.get("notification_cooldown_hours", 24)
        if not self.registry.is_recently_notified(project_path, "folder_summary", max_threshold, cooldown):
            self._send_folder_notification(project_path, expiring_models, advisory, max_threshold)
            self.registry.log_notification(project_path, "folder_summary", max_threshold)

        # Write IDE rules file utilizing the enriched advisor recommendations
        if self.config.get("write_rules", True):
            try:
                # Merge advisory suggestions into deprecations list for rule generation
                advisory_by_var = {adv["variable"]: adv for adv in advisory}
                enriched_deprecations = []
                for dep in expiring_models:
                    adv = advisory_by_var.get(dep["variable"], {})
                    enriched_dep = dict(dep)
                    enriched_dep["purpose"] = adv.get("purpose")
                    enriched_dep["recommended_model"] = adv.get("recommended_model")
                    enriched_dep["reason"] = adv.get("reason")
                    enriched_dep["risk"] = adv.get("risk")
                    enriched_deprecations.append(enriched_dep)

                write_rules_for_project(Path(project_path), enriched_deprecations, self.config)
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
    def _send_folder_notification(
        project_path: str, expiring_models: list[dict], advisory: list[dict], max_threshold: str
    ) -> None:
        project_name = Path(project_path).name
        count = len(expiring_models)

        # Map overall threshold to native OS notification urgency levels
        urgency_map = {"sunset": "critical", "7d": "critical", "30d": "normal", "90d": "low"}
        urgency = urgency_map.get(max_threshold, "normal")

        # Create structured, descriptive notification title
        title = f"Chowkidar: {project_name} has {count} expiring model(s)"
        if max_threshold == "sunset":
            title = f"ALERT: Sunset Models in {project_name} ({count} models)"

        # Sort expiring models by urgency (expired / lowest days_until first)
        sorted_expiring = sorted(expiring_models, key=lambda x: x["days_until"])
        
        # Build concise model summary items for OS toast limits
        message_parts = []
        advisory_by_var = {adv["variable"]: adv for adv in advisory}

        for m in sorted_expiring[:3]:  # display top 3 models max in OS toast
            days = m["days_until"]
            model_name = m["model"]
            var_name = m["variable"]
            adv = advisory_by_var.get(var_name, {})
            rec = adv.get("recommended_model") or m["replacement"] or "check docs"
            
            if days <= 0:
                time_str = "expired"
            else:
                time_str = f"{days}d"
            
            message_parts.append(f"{model_name} ({time_str}) -> {rec.split('/')[-1]}")

        message = ", ".join(message_parts)
        if count > 3:
            message += f" (+ {count - 3} more)"
            
        message += ". Full local advisory rules generated for IDE assistant."

        # Send native OS notification toast
        notify(title, message, urgency)

        # Notify via configured webhook URL
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
