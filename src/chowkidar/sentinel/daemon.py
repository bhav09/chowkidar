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
from ..deployment import DeploymentAssessment
from ..updater.structured_writer import update_model_reference
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

    def _write_status(self, status: str = "running") -> None:
        import json
        import os
        from datetime import datetime, timezone
        
        status_file = CHOWKIDAR_HOME / "daemon_status.json"
        
        started_at = None
        if status_file.exists() and status != "starting":
            try:
                old_data = json.loads(status_file.read_text(encoding="utf-8"))
                started_at = old_data.get("started_at")
            except Exception:
                pass
                
        if started_at is None:
            started_at = datetime.now(timezone.utc).isoformat()
            
        last_sync = self.registry.last_sync_time()
        
        last_scan = None
        try:
            projects = self.registry.get_watched_projects()
            if projects:
                row = self.registry.conn.execute(
                    "SELECT MAX(last_scanned_at) as t FROM watched_projects"
                ).fetchone()
                if row and row["t"]:
                    last_scan = row["t"]
        except Exception:
            pass

        data = {
            "pid": os.getpid(),
            "started_at": started_at,
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "last_scan_at": last_scan,
            "last_sync_at": last_sync,
            "status": status,
        }
        try:
            status_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to write daemon status: %s", e)

    def run(self) -> None:
        """Start the daemon loop (blocking)."""
        logger.info("Chowkidar daemon starting...")
        self._running = True
        self._write_status(status="starting")

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._run_cycle()

        scan_hours = self.config.get("scan_interval_hours", 4)
        sync_hours = self.config.get("sync_interval_hours", 24)
        discover_hours = self.config.get("discover_interval_hours", 24)

        schedule.every(scan_hours).hours.do(self._run_scan_check)
        schedule.every(sync_hours).hours.do(self._run_sync)
        if self.config.get("auto_discover_enabled", False):
            schedule.every(discover_hours).hours.do(self._run_discovery)

        logger.info("Daemon running. Scan every %dh, sync every %dh.", scan_hours, sync_hours)

        while self._running:
            schedule.run_pending()
            self._write_status(status="running")
            time.sleep(60)

        logger.info("Chowkidar daemon stopped.")
        self._write_status(status="stopped")

    def _handle_signal(self, signum: int, frame) -> None:
        logger.info("Received signal %d, shutting down...", signum)
        self._running = False
        self._write_status(status="stopped")

    def _run_cycle(self) -> None:
        """Run a full cycle: sync + discover + scan."""
        self._run_sync()
        self._run_discovery()
        self._run_scan_check()

    def _run_discovery(self) -> None:
        """Discover new Git repositories and register them automatically."""
        if not self.config.get("auto_discover_enabled", False):
            return

        logger.info("Starting automatic repository discovery...")
        try:
            from ..scanner.discovery import discover_repositories
            roots = self.config.get("discover_roots", ["~/Projects", "~/Code", "~/Developer"])
            depth = self.config.get("discover_max_depth", 4)
            discovered = discover_repositories(roots, max_depth=depth)
            
            watched = set(self.registry.get_watched_projects())
            added = 0
            for path in discovered:
                path_str = str(path)
                if path_str not in watched:
                    self.registry.watch_project(path_str)
                    logger.info("Auto-discovered and registered new watched project: %s", path_str)
                    added += 1
            if added > 0:
                logger.info("Auto-discovery registered %d new repositories.", added)
            else:
                logger.info("Auto-discovery completed. No new repositories found.")
        except Exception as e:
            logger.error("Auto-discovery failed: %s", e)

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

        from ..deployment import detect_deployment
        deployment_ass = detect_deployment(project_path)

        expiring_models: list[dict] = []
        max_threshold = "30d"

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

            if days_until > 30:
                continue

            threshold = self._determine_threshold(days_until)

            # Map threshold to precedence for overall project severity
            threshold_precedence = {"sunset": 6, "1d": 5, "7d": 4, "15d": 3, "30d": 2, "90d": 1}
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
                "source_type": model_info["source_type"],
            })

        if not expiring_models:
            return

        # Generate the context-aware advisor recommendations (utilizes local Gemma/heuristics + cache)
        advisory = get_project_advisory(project_path, expiring_models, self.registry, self.config)

        cooldown = self.config.get("notification_cooldown_hours", 24)
        notification_candidates = [
            model
            for model in expiring_models
            if not self.registry.is_recently_notified(
                project_path,
                model["canonical"],
                model["threshold"],
                cooldown,
                file_path=model["file"],
                variable_name=model["variable"],
            )
        ]

        if notification_candidates:
            # Generate and save HTML report for notification click callback
            report_dir = CHOWKIDAR_HOME / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            project_name = Path(project_path).name
            report_file = report_dir / f"report_{project_name}.html"
            click_target = None
            try:
                from ..report import generate_report
                html_content = generate_report([Path(project_path)], "html", self.registry)
                report_file.write_text(html_content, encoding="utf-8")
                click_target = str(report_file)
            except Exception as e:
                logger.error("Failed to generate and save report for %s: %s", project_path, e)

            max_threshold = self._max_threshold(notification_candidates)
            delivery = self._send_folder_notification(
                project_path, notification_candidates, advisory, max_threshold, click_target, deployment_ass
            )
            advisory_by_var = {adv["variable"]: adv for adv in advisory}
            for model in notification_candidates:
                adv = advisory_by_var.get(model["variable"], {})
                recommendation = adv.get("recommended_model_canonical") or adv.get("recommended_model")
                self.registry.log_notification(
                    project_path,
                    model["canonical"],
                    model["threshold"],
                    file_path=model["file"],
                    variable_name=model["variable"],
                    delivery_status="delivered" if delivery["desktop"] else "failed",
                    webhook_status=delivery["webhook"],
                    report_path=click_target,
                    recommendation=recommendation,
                    error=delivery.get("error"),
                )

        self._maybe_apply_one_day_updates(project_path, expiring_models, advisory)

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
        elif days_until == 1:
            return "1d"
        elif days_until <= 7:
            return "7d"
        elif days_until <= 15:
            return "15d"
        elif days_until <= 30:
            return "30d"
        else:
            return "90d"

    @staticmethod
    def _max_threshold(models: list[dict]) -> str:
        threshold_precedence = {"sunset": 6, "1d": 5, "7d": 4, "15d": 3, "30d": 2, "90d": 1}
        return max((m["threshold"] for m in models), key=lambda t: threshold_precedence.get(t, 0))

    @staticmethod
    def _send_folder_notification(
        project_path: str,
        expiring_models: list[dict],
        advisory: list[dict],
        max_threshold: str,
        click_target: str | None = None,
        deployment_ass: DeploymentAssessment | None = None,
    ) -> dict[str, str | bool | None]:
        project_name = Path(project_path).name
        count = len(expiring_models)

        # Map overall threshold to native OS notification urgency levels
        urgency_map = {"sunset": "critical", "1d": "critical", "7d": "critical", "15d": "normal", "30d": "normal", "90d": "low"}
        urgency = urgency_map.get(max_threshold, "normal")

        # Create structured, descriptive notification title
        title = f"Chowkidar: {project_name} has {count} expiring model(s)"
        if max_threshold == "sunset":
            title = f"ALERT: Sunset Models in {project_name} ({count} models)"

        if deployment_ass and deployment_ass.state in ("possible", "likely"):
            adapters = list({sig.adapter for sig in deployment_ass.signals})
            if adapters:
                adapters_str = ", ".join(adapters).upper()
                title += f" [Target: {adapters_str}]"

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

        if deployment_ass and deployment_ass.state in ("possible", "likely"):
            adapters = list({sig.adapter for sig in deployment_ass.signals})
            if adapters:
                adapters_str = ", ".join(adapters).upper()
                message += f" [Likely deployed: {adapters_str}]"

        message += ". Full local advisory rules generated for IDE assistant."

        # Send native OS notification toast
        error = None
        desktop_ok = False
        try:
            desktop_ok = notify(title, message, urgency, click_target=click_target)
        except Exception as exc:
            error = str(exc)

        # Notify via configured webhook URL
        webhook_status = "not_configured"
        webhook_url = ChowkidarDaemon._get_webhook_url()
        if webhook_url:
            webhook_fmt = "generic"
            try:
                from ..config import Config
                cfg = Config()
                webhook_fmt = cfg.get("webhook_format", "generic")
            except Exception:
                pass
            webhook_status = "delivered" if send_webhook(webhook_url, title, message, urgency, webhook_fmt) else "failed"
        return {"desktop": desktop_ok, "webhook": webhook_status, "error": error}

    @staticmethod
    def _get_webhook_url() -> str:
        try:
            from ..config import Config
            cfg = Config()
            return cfg.get("webhook_url", "") or ""
        except Exception:
            return ""

    def _maybe_apply_one_day_updates(
        self,
        project_path: str,
        expiring_models: list[dict],
        advisory: list[dict],
    ) -> None:
        if not self.config.get("auto_update", False):
            return

        advisory_by_var = {adv["variable"]: adv for adv in advisory}
        for model in expiring_models:
            if model["threshold"] != "1d":
                continue
            if model["source_type"] == "source":
                self.registry.log_action(
                    project_path,
                    "local_write",
                    "source",
                    "skipped",
                    target_path=model["file"],
                    variable_name=model["variable"],
                    model_id=model["canonical"],
                    message="Source-code references are notify-only.",
                )
                continue

            adv = advisory_by_var.get(model["variable"], {})
            if not adv.get("auto_write_allowed", False):
                self.registry.log_action(
                    project_path,
                    "local_write",
                    model["source_type"],
                    "blocked",
                    target_path=model["file"],
                    variable_name=model["variable"],
                    model_id=model["canonical"],
                    message="Recommendation requires manual review.",
                    metadata={"advisory": adv},
                )
                continue

            new_model = adv.get("recommended_model_canonical") or adv.get("recommended_model") or model.get("replacement")
            if not new_model:
                self.registry.log_action(
                    project_path,
                    "local_write",
                    model["source_type"],
                    "blocked",
                    target_path=model["file"],
                    variable_name=model["variable"],
                    model_id=model["canonical"],
                    message="No validated replacement model available.",
                )
                continue

            old_uses_provider_prefix = "/" in model["model"]
            new_value = new_model if old_uses_provider_prefix else str(new_model).split("/")[-1]
            result = update_model_reference(Path(model["file"]), model["variable"], new_value)
            self.registry.log_action(
                project_path,
                "local_write",
                result.get("target_type", model["source_type"]),
                result.get("status", "error"),
                target_path=model["file"],
                variable_name=model["variable"],
                model_id=model["canonical"],
                old_value=result.get("old_value"),
                new_value=result.get("new_value"),
                message=result.get("message"),
                metadata={k: v for k, v in result.items() if k not in {"old_value", "new_value", "message"}},
            )
