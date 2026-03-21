"""Chowkidar CLI — the main entry point for all commands.

Usage:
    chowkidar scan [PATH]
    chowkidar sync
    chowkidar check [PATH] [--quiet]
    chowkidar status
    chowkidar watch <PATH>
    chowkidar unwatch <PATH>
    chowkidar pin <MODEL> [--reason TEXT]
    chowkidar unpin <MODEL>
    chowkidar snooze <MODEL> --days N
    chowkidar setup [--skip-slm]
    chowkidar daemon
    chowkidar install-service
    chowkidar uninstall-service
    chowkidar logs [--tail N]
    chowkidar mcp
    chowkidar config [set KEY VALUE]
    chowkidar update [--dry-run] [PATH]
    chowkidar gate [PATH] [--severity] [--format]
    chowkidar cost [PATH]
    chowkidar diff <OLD_MODEL> <NEW_MODEL>
    chowkidar fix [PATH] [--branch] [--pr]
    chowkidar report [PATH] [--format] [--multi-project]
    chowkidar predict
    chowkidar dashboard
    chowkidar test-migration --old M --new M --prompts FILE
    chowkidar hook install|uninstall
    chowkidar slm status
    chowkidar rules write [PATH]
    chowkidar rules clean [PATH]
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .config import CHOWKIDAR_HOME, Config

app = typer.Typer(
    name="chowkidar",
    help="Local-first LLM model deprecation watchdog.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()

rules_app = typer.Typer(help="Manage IDE rules files.")
app.add_typer(rules_app, name="rules")

slm_app = typer.Typer(help="Local SLM management.")
app.add_typer(slm_app, name="slm")

hook_app = typer.Typer(help="Shell hook management.")
app.add_typer(hook_app, name="hook")


def _get_config() -> Config:
    Config.ensure_home()
    return Config()


# --- scan ---

@app.command()
def scan(
    path: Optional[str] = typer.Argument(None, help="Project directory to scan (default: CWD)"),
    system_wide: bool = typer.Option(False, "--system-wide", help="Scan the entire user home directory for .env files"),
) -> None:
    """Scan a project directory for LLM model strings."""
    from .scanner import scan_directory
    from .scanner.patterns import identify_provider

    target = Path(path).resolve() if path else Path.cwd()
    if not system_wide and not target.is_dir():
        console.print(f"[red]Not a directory: {target}[/red]")
        raise typer.Exit(1)

    if system_wide:
        console.print("[bold cyan]Initiating system-wide scan from User Home[/bold cyan]")
        console.print("[dim]Ignoring massive folders (node_modules, .git, venv) to optimize speed...[/dim]")

    with console.status("Scanning..."):
        result = scan_directory(target, system_wide=system_wide)

    if result.total_count == 0:
        console.print(Panel("[green]No model strings found.[/green]", title="Scan Result"))
        return

    table = Table(title=f"Models found in {target.name}")
    table.add_column("Variable", style="cyan")
    table.add_column("Model", style="yellow")
    table.add_column("Provider", style="magenta")
    table.add_column("File", style="dim")
    table.add_column("Type", style="dim")

    for m in result.all_models:
        provider = identify_provider(m["model"]) or "unknown"
        file_short = Path(m["file"]).name
        table.add_row(m["variable"], m["model"], provider, file_short, m["source_type"])

    console.print(table)
    console.print(f"\n[bold]{result.total_count}[/bold] model references across "
                  f"[bold]{len(result.unique_models)}[/bold] unique models.")


# --- sync ---

@app.command()
def sync() -> None:
    """Fetch latest deprecation data from all providers."""
    from .providers.anthropic_provider import AnthropicProvider
    from .providers.google_provider import GoogleProvider
    from .providers.mistral_provider import MistralProvider
    from .providers.openai_provider import OpenAIProvider
    from .registry.db import Registry

    config = _get_config()
    registry = Registry()
    registry.init_db()
    enabled = config.get("providers", ["openai", "anthropic", "google", "mistral"])

    async def _sync() -> None:
        providers = []
        if "openai" in enabled:
            providers.append(OpenAIProvider())
        if "anthropic" in enabled:
            providers.append(AnthropicProvider())
        if "google" in enabled:
            providers.append(GoogleProvider())
        if "mistral" in enabled:
            providers.append(MistralProvider())

        total = 0
        for provider in providers:
            try:
                with console.status(f"Syncing {provider.name}..."):
                    deprecations = await provider.fetch_deprecations()
                    for dep in deprecations:
                        registry.upsert_model(
                            model_id=dep.model_id,
                            provider=dep.provider,
                            sunset_date=dep.sunset_date,
                            replacement=dep.replacement,
                            replacement_confidence=dep.replacement_confidence,
                            breaking_changes=dep.breaking_changes,
                            source_url=dep.source_url,
                        )
                    total += len(deprecations)
                    console.print(f"  [green]✓[/green] {provider.name}: {len(deprecations)} models")
            except Exception as e:
                console.print(f"  [red]✗[/red] {provider.name}: {e}")

        console.print(f"\n[bold green]Synced {total} deprecation records.[/bold green]")

    asyncio.run(_sync())
    registry.close()


# --- check ---

@app.command()
def check(
    path: Optional[str] = typer.Argument(None, help="Project directory (default: CWD)"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Single-line output for shell hooks"),
) -> None:
    """Cross-reference project models with the deprecation registry."""
    from .registry.db import Registry
    from .scanner import scan_directory

    _get_config()
    target = Path(path).resolve() if path else Path.cwd()
    registry = Registry()
    registry.init_db()

    scan_result = scan_directory(target)

    if registry.is_muted(str(target)):
        if not quiet:
            console.print("[dim]Project is muted. Skipping deprecation checks.[/dim]")
        registry.close()
        return

    if scan_result.total_count == 0:
        if not quiet:
            console.print("[green]No model strings found in project.[/green]")
        registry.close()
        return

    deprecated_count = 0
    critical_count = 0

    for m in scan_result.all_models:
        canonical = m["canonical"]
        record = registry.get_model(canonical)
        if record and record.sunset_date:
            deprecated_count += 1
            try:
                sunset = datetime.fromisoformat(record.sunset_date)
                days_until = (sunset - datetime.now(timezone.utc).replace(tzinfo=None)).days
                if days_until <= 7:
                    critical_count += 1
            except ValueError:
                pass

    if quiet:
        if deprecated_count > 0:
            console.print(
                f"chowkidar: {deprecated_count} model(s) deprecated"
                + (f", {critical_count} critical" if critical_count else "")
                + " (run 'chowkidar check' for details)"
            )
        registry.close()
        return

    table = Table(title="Deprecation Check")
    table.add_column("Variable", style="cyan")
    table.add_column("Model", style="yellow")
    table.add_column("Status")
    table.add_column("Sunset Date")
    table.add_column("Days Left")
    table.add_column("Replacement")
    table.add_column("Confidence")

    for m in scan_result.all_models:
        canonical = m["canonical"]
        record = registry.get_model(canonical)

        if record is None:
            table.add_row(m["variable"], m["model"], "[dim]unknown[/dim]", "-", "-", "-", "-")
            continue

        if record.sunset_date is None:
            table.add_row(m["variable"], m["model"], "[green]active[/green]", "-", "-", "-", "-")
            continue

        try:
            sunset = datetime.fromisoformat(record.sunset_date)
            days_until = (sunset - datetime.now(timezone.utc).replace(tzinfo=None)).days
        except ValueError:
            days_until = None

        is_pinned = registry.is_pinned(canonical)
        pin_marker = " [dim][PINNED][/dim]" if is_pinned else ""

        if days_until is not None and days_until <= 0:
            status = f"[bold red]SUNSET{pin_marker}[/bold red]"
            days_str = f"[bold red]{days_until}[/bold red]"
        elif days_until is not None and days_until <= 7:
            status = f"[red]critical{pin_marker}[/red]"
            days_str = f"[red]{days_until}[/red]"
        elif days_until is not None and days_until <= 30:
            status = f"[yellow]warning{pin_marker}[/yellow]"
            days_str = f"[yellow]{days_until}[/yellow]"
        else:
            status = f"[dim]deprecating{pin_marker}[/dim]"
            days_str = str(days_until) if days_until else "?"

        replacement = record.replacement or "-"

        table.add_row(
            m["variable"], m["model"], status, record.sunset_date,
            days_str, replacement, record.replacement_confidence,
        )

    console.print(table)

    if deprecated_count > 0:
        console.print(f"\n[bold yellow]⚠ {deprecated_count} model(s) with deprecation notices.[/bold yellow]")
    else:
        console.print("\n[bold green]✓ All models are active.[/bold green]")

    registry.close()


# --- status ---

@app.command()
def status() -> None:
    """Show daemon status, registry freshness, and watched projects."""
    from .registry.db import Registry
    from .sentinel.service import is_service_installed

    config = _get_config()
    registry = Registry()
    registry.init_db()

    console.print(Panel("[bold]Chowkidar Status[/bold]", subtitle=f"v{__version__}"))

    last_sync = registry.last_sync_time()
    if last_sync:
        try:
            sync_dt = datetime.fromisoformat(last_sync)
            hours_ago = (datetime.now(timezone.utc).replace(tzinfo=None) - sync_dt).total_seconds() / 3600
            freshness = "[green]fresh[/green]" if hours_ago < 48 else "[yellow]stale[/yellow]"
            console.print(f"  Registry: {freshness} (last sync: {last_sync}, {hours_ago:.0f}h ago)")
        except ValueError:
            console.print(f"  Registry: last sync {last_sync}")
    else:
        console.print("  Registry: [red]never synced[/red] — run 'chowkidar sync'")

    service_installed = is_service_installed()
    console.print(f"  Service: {'[green]installed[/green]' if service_installed else '[dim]not installed[/dim]'}")

    projects = registry.get_watched_projects()
    if projects:
        console.print(f"  Watched projects: [bold]{len(projects)}[/bold]")
        for p in projects:
            console.print(f"    • {p}")
    else:
        console.print("  Watched projects: [dim]none[/dim] — run 'chowkidar watch <path>'")

    pinned = registry.get_pinned_models()
    if pinned:
        console.print(f"  Pinned models: {len(pinned)}")
        for model_id, reason in pinned:
            r = f" ({reason})" if reason else ""
            console.print(f"    • {model_id}{r}")

    all_models = registry.get_all_models()
    deprecated = [m for m in all_models if m.sunset_date]
    console.print(f"  Registry: {len(all_models)} models, {len(deprecated)} with deprecation dates")

    console.print(f"\n  Config: {config.path}")
    console.print(f"  Data:   {CHOWKIDAR_HOME}")

    registry.close()


# --- watch / unwatch ---

@app.command()
def watch(path: str = typer.Argument(..., help="Project directory to watch")) -> None:
    """Register a project for background monitoring."""
    from .registry.db import Registry

    target = Path(path).resolve()
    if not target.is_dir():
        console.print(f"[red]Not a directory: {target}[/red]")
        raise typer.Exit(1)

    registry = Registry()
    registry.init_db()
    registry.watch_project(str(target))
    registry.close()
    console.print(f"[green]✓[/green] Now watching: {target}")


@app.command()
def unwatch(path: str = typer.Argument(..., help="Project to stop watching")) -> None:
    """Unregister a project from background monitoring."""
    from .registry.db import Registry

    target = Path(path).resolve()
    registry = Registry()
    registry.init_db()
    registry.unwatch_project(str(target))
    registry.close()
    console.print(f"[green]✓[/green] Stopped watching: {target}")


# --- mute / unmute ---

@app.command()
def mute(path: str = typer.Argument(..., help="Project directory to mute notifications for")) -> None:
    """Silence deprecation notifications for a specific project permanently."""
    from .registry.db import Registry

    target = Path(path).resolve()
    registry = Registry()
    registry.init_db()
    registry.mute_project(str(target))
    console.print(f"[green]✓[/green] Muted auto-notifications for workspace: {target}")
    registry.close()


@app.command()
def unmute(path: str = typer.Argument(..., help="Project directory to unmute")) -> None:
    """Re-enable deprecation notifications for a specific project."""
    from .registry.db import Registry

    target = Path(path).resolve()
    registry = Registry()
    registry.init_db()
    registry.unmute_project(str(target))
    console.print(f"[green]✓[/green] Unmuted auto-notifications for workspace: {target}")
    registry.close()


# --- pin / unpin ---

@app.command()
def pin(
    model: str = typer.Argument(..., help="Model ID to pin"),
    reason: Optional[str] = typer.Option(None, "--reason", "-r", help="Reason for pinning"),
) -> None:
    """Suppress deprecation notifications for a model."""
    from .registry.db import Registry
    from .scanner.patterns import normalize_model_id

    registry = Registry()
    registry.init_db()
    canonical = normalize_model_id(model)
    registry.pin_model(canonical, reason)
    registry.close()
    console.print(f"[green]✓[/green] Pinned: {canonical}")
    if reason:
        console.print(f"  Reason: {reason}")


@app.command()
def unpin(model: str = typer.Argument(..., help="Model ID to unpin")) -> None:
    """Re-enable deprecation notifications for a model."""
    from .registry.db import Registry
    from .scanner.patterns import normalize_model_id

    registry = Registry()
    registry.init_db()
    canonical = normalize_model_id(model)
    registry.unpin_model(canonical)
    registry.close()
    console.print(f"[green]✓[/green] Unpinned: {canonical}")


# --- snooze ---

@app.command()
def snooze(
    model: str = typer.Argument(..., help="Model ID to snooze"),
    days: int = typer.Option(..., "--days", "-d", help="Number of days to snooze"),
) -> None:
    """Temporarily suppress notifications for a model."""
    from .registry.db import Registry
    from .scanner.patterns import normalize_model_id

    registry = Registry()
    registry.init_db()
    canonical = normalize_model_id(model)
    registry.set_snooze(canonical, days)
    registry.close()
    console.print(f"[green]✓[/green] Snoozed {canonical} for {days} days.")


# --- setup ---

@app.command()
def setup(
    skip_slm: bool = typer.Option(False, "--skip-slm", help="Skip SLM/Ollama setup"),
) -> None:
    """First-run setup: initialize config, database, and optionally install Ollama + SLM."""
    config = _get_config()
    config.save()
    console.print(f"[green]✓[/green] Config initialized: {config.path}")

    from .registry.db import Registry
    registry = Registry()
    registry.init_db()
    registry.close()
    console.print(f"[green]✓[/green] Database initialized: {CHOWKIDAR_HOME / 'registry.db'}")

    from .slm.setup import full_setup
    with console.status("Setting up SLM..."):
        success, message = full_setup(skip_slm=skip_slm)
    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[yellow]⚠[/yellow] {message}")

    console.print("\n[bold green]Setup complete![/bold green]")
    console.print("Next steps:")
    console.print("  1. chowkidar sync          — fetch deprecation data")
    console.print("  2. chowkidar scan .         — scan current project")
    console.print("  3. chowkidar watch .        — register for monitoring")
    console.print("  4. chowkidar install-service — enable background daemon")


# --- daemon ---

@app.command()
def daemon() -> None:
    """Start the background daemon (foreground mode)."""
    from .sentinel.daemon import ChowkidarDaemon

    config = _get_config()
    console.print("[bold]Chowkidar daemon starting...[/bold]")
    console.print(f"  Scan interval: {config.get('scan_interval_hours')}h")
    console.print(f"  Sync interval: {config.get('sync_interval_hours')}h")
    console.print("  Press Ctrl+C to stop.\n")

    d = ChowkidarDaemon(config)
    d.run()


# --- install-service / uninstall-service ---

@app.command(name="install-service")
def install_service_cmd() -> None:
    """Install Chowkidar as an OS-native background service."""
    from .sentinel.service import install_service

    success, message = install_service()
    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[red]✗[/red] {message}")
        raise typer.Exit(1)


@app.command(name="uninstall-service")
def uninstall_service_cmd() -> None:
    """Remove the OS-native background service."""
    from .sentinel.service import uninstall_service

    success, message = uninstall_service()
    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[red]✗[/red] {message}")
        raise typer.Exit(1)


# --- logs ---

@app.command()
def logs(
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show"),
) -> None:
    """View daemon logs."""
    log_file = CHOWKIDAR_HOME / "logs" / "daemon.log"
    if not log_file.exists():
        console.print("[dim]No logs yet. Start the daemon first.[/dim]")
        return

    lines = log_file.read_text().splitlines()
    for line in lines[-tail:]:
        console.print(line)


# --- mcp ---

@app.command()
def mcp() -> None:
    """Start the MCP server (stdio transport, called by IDE)."""
    from .mcp_server.server import run_server
    run_server()


# --- config ---

@app.command(name="config")
def config_cmd(
    key: Optional[str] = typer.Argument(None, help="Config key to get/set"),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
) -> None:
    """View or modify Chowkidar configuration."""
    config = _get_config()

    if key is None:
        table = Table(title="Chowkidar Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="yellow")
        for k, v in config.as_dict().items():
            table.add_row(k, str(v))
        console.print(table)
        console.print(f"\nConfig file: {config.path}")
        return

    if value is None:
        v = config.get(key)
        if v is not None:
            console.print(f"{key} = {v}")
        else:
            console.print(f"[red]Unknown key: {key}[/red]")
        return

    config.set(key, value)
    config.save()
    console.print(f"[green]✓[/green] {key} = {config.get(key)}")


# --- update ---

@app.command()
def update(
    path: Optional[str] = typer.Argument(None, help="Project directory (default: CWD)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing"),
) -> None:
    """Update deprecated model values in .env files."""
    from .registry.db import Registry
    from .scanner import scan_directory
    from .updater.env_writer import update_env_value

    config = _get_config()
    if not config.get("auto_update", False) and not dry_run:
        console.print("[yellow]Auto-update is disabled.[/yellow]")
        console.print("Enable with: chowkidar config auto_update true")
        console.print("Or use --dry-run to preview changes.")
        raise typer.Exit(1)

    target = Path(path).resolve() if path else Path.cwd()
    registry = Registry()
    registry.init_db()
    scan_result = scan_directory(target)

    updates: list[dict] = []
    for m in scan_result.all_models:
        if m["source_type"] != "env":
            continue
        canonical = m["canonical"]
        record = registry.get_model(canonical)
        if record and record.sunset_date and record.replacement:
            if not registry.is_pinned(canonical):
                updates.append({
                    "file": m["file"],
                    "variable": m["variable"],
                    "old_model": m["model"],
                    "new_model": record.replacement.split("/")[-1],
                    "confidence": record.replacement_confidence,
                    "breaking": record.breaking_changes,
                })

    if not updates:
        console.print("[green]No updates needed.[/green]")
        return

    table = Table(title="Proposed Updates" if dry_run else "Updates")
    table.add_column("Variable", style="cyan")
    table.add_column("Old Model", style="red")
    table.add_column("→")
    table.add_column("New Model", style="green")
    table.add_column("Confidence")
    table.add_column("Breaking?")

    for u in updates:
        table.add_row(
            u["variable"], u["old_model"], "→", u["new_model"],
            u["confidence"], "Yes" if u["breaking"] else "No",
        )

    console.print(table)

    if dry_run:
        console.print(f"\n[dim]{len(updates)} update(s) would be applied. Remove --dry-run to apply.[/dim]")
        return

    for u in updates:
        result = update_env_value(
            file_path=Path(u["file"]),
            variable_name=u["variable"],
            new_value=u["new_model"],
        )
        if result["status"] == "updated":
            console.print(f"  [green]✓[/green] {u['variable']}: {u['old_model']} → {u['new_model']}")
        else:
            console.print(f"  [red]✗[/red] {u['variable']}: {result.get('message', 'failed')}")

    registry.close()


# --- slm subcommands ---

@slm_app.command(name="status")
def slm_status() -> None:
    """Check if Ollama is running and the SLM model is available."""
    from .slm.client import SLMClient

    config = _get_config()
    client = SLMClient(config)
    success, message = client.test_connection()
    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[yellow]⚠[/yellow] {message}")

    console.print(f"  SLM enabled: {config.get('slm_enabled', False)}")
    console.print(f"  Model: {config.get('slm_model', 'gemma3:1b')}")


# --- rules subcommands ---

@rules_app.command(name="write")
def rules_write(
    path: Optional[str] = typer.Argument(None, help="Project directory (default: CWD)"),
) -> None:
    """Generate/refresh IDE rules files for a project."""
    from .ide.rules_writer import write_rules_for_project
    from .registry.db import Registry
    from .scanner import scan_directory

    config = _get_config()
    target = Path(path).resolve() if path else Path.cwd()
    registry = Registry()
    registry.init_db()

    with console.status("Scanning project..."):
        scan_result = scan_directory(target)

    deprecations: list[dict] = []
    for m in scan_result.all_models:
        canonical = m["canonical"]
        record = registry.get_model(canonical)
        if record and record.sunset_date:
            try:
                sunset = datetime.fromisoformat(record.sunset_date)
                days_until = (sunset - datetime.now(timezone.utc).replace(tzinfo=None)).days
            except ValueError:
                days_until = None

            deprecations.append({
                "variable": m["variable"],
                "file": m["file"],
                "model": m["model"],
                "canonical": canonical,
                "sunset_date": record.sunset_date,
                "replacement": record.replacement,
                "replacement_confidence": record.replacement_confidence,
                "breaking_changes": record.breaking_changes,
                "days_until": days_until,
            })

    if not deprecations:
        console.print("[green]No deprecated models found — no rules to write.[/green]")
        return

    written = write_rules_for_project(target, deprecations, config)
    for f in written:
        console.print(f"  [green]✓[/green] {f}")
    console.print(f"\n[bold]{len(written)} rules file(s) written.[/bold]")

    registry.close()


@rules_app.command(name="clean")
def rules_clean(
    path: Optional[str] = typer.Argument(None, help="Project directory (default: CWD)"),
) -> None:
    """Remove Chowkidar-generated rules files from a project."""
    from .ide.rules_writer import clean_rules

    target = Path(path).resolve() if path else Path.cwd()
    removed = clean_rules(target)
    if removed:
        for f in removed:
            console.print(f"  [green]✓[/green] Removed: {f}")
    else:
        console.print("[dim]No Chowkidar rules files found.[/dim]")


# --- gate ---

@app.command()
def gate(
    path: Optional[str] = typer.Argument(None, help="Project directory (default: CWD)"),
    severity: str = typer.Option("block-sunset", "--severity", "-s",
                                 help="block-sunset|block-7d|block-30d|block-all"),
    output_format: str = typer.Option("table", "--format", "-f",
                                      help="table|json|github-actions"),
) -> None:
    """CI/CD gate — exit 1 if deprecated models are found."""
    from .gate import run_gate

    target = Path(path).resolve() if path else Path.cwd()
    exit_code, _violations, formatted = run_gate(target, severity, output_format)
    console.print(formatted)
    raise typer.Exit(exit_code)


# --- cost ---

@app.command()
def cost(
    path: Optional[str] = typer.Argument(None, help="Project directory (default: CWD)"),
) -> None:
    """Show cost impact of model replacements."""
    from .pricing import compare_cost
    from .registry.db import Registry
    from .scanner import scan_directory

    target = Path(path).resolve() if path else Path.cwd()
    registry = Registry()
    registry.init_db()
    scan_result = scan_directory(target)

    table = Table(title="Cost Impact Analysis")
    table.add_column("Model", style="yellow")
    table.add_column("Replacement", style="green")
    table.add_column("Input $/1M", justify="right")
    table.add_column("Output $/1M", justify="right")
    table.add_column("New Input", justify="right")
    table.add_column("New Output", justify="right")
    table.add_column("Impact")

    found = False
    for m in scan_result.all_models:
        canonical = m["canonical"]
        record = registry.get_model(canonical)
        if not record or not record.sunset_date or not record.replacement:
            continue

        comparison = compare_cost(canonical, record.replacement)
        if comparison is None:
            table.add_row(m["model"], record.replacement, "?", "?", "?", "?", "[dim]no pricing data[/dim]")
            found = True
            continue

        found = True
        table.add_row(
            m["model"], record.replacement.split("/")[-1],
            f"${comparison.current_input:.2f}", f"${comparison.current_output:.2f}",
            f"${comparison.replacement_input:.2f}", f"${comparison.replacement_output:.2f}",
            comparison.summary,
        )

    if found:
        console.print(table)
    else:
        console.print("[green]No deprecated models with known replacements and pricing data.[/green]")
    registry.close()


# --- diff ---

@app.command(name="diff")
def diff_cmd(
    old_model: str = typer.Argument(..., help="Current model ID"),
    new_model: str = typer.Argument(..., help="Replacement model ID"),
) -> None:
    """Compare capabilities between two models."""
    from .capabilities import diff_capabilities
    from .scanner.patterns import normalize_model_id

    old_canonical = normalize_model_id(old_model)
    new_canonical = normalize_model_id(new_model)
    diffs = diff_capabilities(old_canonical, new_canonical)

    if not diffs:
        console.print("[yellow]No capability data available for one or both models.[/yellow]")
        return

    table = Table(title=f"Capability Diff: {old_model} → {new_model}")
    table.add_column("Capability")
    table.add_column(old_model, justify="right")
    table.add_column(new_model, justify="right")
    table.add_column("Change")

    change_styles = {
        "improved": "[green]improved[/green]",
        "degraded": "[red]degraded[/red]",
        "same": "[dim]same[/dim]",
        "gained": "[green]gained[/green]",
        "lost": "[red]LOST[/red]",
    }

    for d in diffs:
        table.add_row(d.label, d.old_value, d.new_value, change_styles.get(d.change_type, d.change_type))

    console.print(table)


# --- fix ---

@app.command()
def fix(
    path: Optional[str] = typer.Argument(None, help="Project directory (default: CWD)"),
    branch: bool = typer.Option(False, "--branch", help="Create a git branch and commit"),
    pr: bool = typer.Option(False, "--pr", help="Also push and create a PR"),
    include_source: bool = typer.Option(False, "--include-source", help="Also fix source code files"),
) -> None:
    """Apply model replacements, optionally branch/push/PR."""
    from .git_ops import apply_fixes_and_pr
    from .registry.db import Registry
    from .scanner import scan_directory

    target = Path(path).resolve() if path else Path.cwd()
    registry = Registry()
    registry.init_db()
    scan_result = scan_directory(target)

    updates: list[dict] = []
    for m in scan_result.all_models:
        if not include_source and m["source_type"] != "env":
            continue
        canonical = m["canonical"]
        record = registry.get_model(canonical)
        if record and record.sunset_date and record.replacement:
            if not registry.is_pinned(canonical):
                updates.append({
                    "file": m["file"],
                    "variable": m["variable"],
                    "old_model": m["model"],
                    "new_model": record.replacement.split("/")[-1],
                    "confidence": record.replacement_confidence,
                    "breaking": record.breaking_changes,
                })

    if not updates:
        console.print("[green]No fixable deprecations found.[/green]")
        registry.close()
        return

    messages = apply_fixes_and_pr(target, updates, do_push=(branch or pr), do_pr=pr)
    for msg in messages:
        if msg.startswith("ERROR"):
            console.print(f"[red]{msg}[/red]")
        else:
            console.print(f"[green]✓[/green] {msg}")

    registry.close()


# --- report ---

@app.command()
def report(
    path: Optional[str] = typer.Argument(None, help="Project directory (default: CWD)"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="markdown|json|html"),
    multi_project: bool = typer.Option(False, "--multi-project", help="Report all watched projects"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Write to file"),
) -> None:
    """Generate a deprecation report."""
    from .registry.db import Registry
    from .report import generate_report

    registry = Registry()
    registry.init_db()

    if multi_project:
        project_paths = [Path(p) for p in registry.get_watched_projects()]
        if not project_paths:
            console.print("[yellow]No watched projects. Run 'chowkidar watch <path>' first.[/yellow]")
            return
    else:
        project_paths = [Path(path).resolve() if path else Path.cwd()]

    report_text = generate_report(project_paths, output_format, registry)

    if output_file:
        Path(output_file).write_text(report_text)
        console.print(f"[green]✓[/green] Report written to {output_file}")
    else:
        console.print(report_text)

    registry.close()


# --- predict ---

@app.command()
def predict(
    path: Optional[str] = typer.Argument(None, help="Project directory to scan for models (default: CWD)"),
) -> None:
    """Predict deprecation dates for models in your project based on provider lifecycle data."""
    from .predictor import predict_all
    from .registry.db import ModelRecord, Registry
    from .scanner import scan_directory
    from .scanner.patterns import identify_provider

    target = Path(path).resolve() if path else Path.cwd()
    registry = Registry()
    registry.init_db()

    scan_result = scan_directory(target)
    synthetic_models: list[ModelRecord] = []
    seen: set[str] = set()

    for m in scan_result.all_models:
        canonical = m["canonical"]
        if canonical in seen:
            continue
        seen.add(canonical)

        record = registry.get_model(canonical)
        if record and record.sunset_date:
            continue

        provider = identify_provider(m["model"]) or m["canonical"].split("/")[0]
        synthetic_models.append(ModelRecord(
            id=canonical, provider=provider, aliases=[], sunset_date=None,
            replacement=None, replacement_confidence="low", breaking_changes=False,
            source_url=None, last_checked_at=None, created_at=None,
        ))

    predictions = predict_all(synthetic_models)

    if not predictions:
        console.print("[green]No models to predict — all have known sunset dates or are unrecognized.[/green]")
        registry.close()
        return

    table = Table(title="Deprecation Predictions")
    table.add_column("Model", style="yellow")
    table.add_column("Provider", style="magenta")
    table.add_column("Est. Sunset")
    table.add_column("Confidence")
    table.add_column("Basis", style="dim")

    for p in predictions:
        conf_style = {"high": "green", "medium": "yellow", "low": "dim"}.get(p.confidence, "dim")
        table.add_row(
            p.model_id, p.provider,
            p.estimated_sunset or "unknown",
            f"[{conf_style}]{p.confidence}[/{conf_style}]",
            p.basis,
        )

    console.print(table)
    console.print("\n[dim]These are estimates, not official dates. Check provider docs for authoritative info.[/dim]")
    registry.close()


# --- dashboard ---

@app.command()
def dashboard() -> None:
    """Show deprecation status across all watched projects."""
    from .dashboard import run_dashboard
    run_dashboard()


# --- test-migration ---

@app.command(name="test-migration")
def test_migration(
    old: str = typer.Option(..., "--old", help="Old model ID"),
    new: str = typer.Option(..., "--new", help="New model ID"),
    prompts: str = typer.Option(..., "--prompts", help="Path to test prompts JSONL file"),
) -> None:
    """Run shadow test comparing outputs between old and new models."""
    from .migration_tester import load_prompts, run_migration_test

    prompts_path = Path(prompts)
    if not prompts_path.exists():
        console.print(f"[red]Prompts file not found: {prompts}[/red]")
        raise typer.Exit(1)

    test_prompts = load_prompts(prompts_path)
    console.print(f"Running {len(test_prompts)} prompts through {old} and {new}...")

    with console.status("Testing..."):
        result = run_migration_test(old, new, test_prompts)

    table = Table(title=f"Migration Test: {old} → {new}")
    table.add_column("Prompt", width=40)
    table.add_column("Similarity", justify="right")
    table.add_column("Old Latency", justify="right")
    table.add_column("New Latency", justify="right")
    table.add_column("Format OK")

    for r in result.results:
        sim_style = "green" if r.similarity_score > 0.7 else ("yellow" if r.similarity_score > 0.4 else "red")
        table.add_row(
            r.prompt[:40], f"[{sim_style}]{r.similarity_score:.2f}[/{sim_style}]",
            f"{r.old_latency_ms:.0f}ms", f"{r.new_latency_ms:.0f}ms",
            "[green]Yes[/green]" if r.format_match else "[red]No[/red]",
        )

    console.print(table)
    conf_color = {"high": "green", "medium": "yellow", "low": "red"}.get(result.confidence, "dim")
    console.print(f"\nMigration confidence: [{conf_color}]{result.confidence}[/{conf_color}]")
    console.print(f"Average similarity: {result.avg_similarity:.2f}")
    console.print(f"Avg latency: {result.avg_old_latency:.0f}ms → {result.avg_new_latency:.0f}ms")


# --- hook subcommands ---

@hook_app.command(name="install")
def hook_install() -> None:
    """Install shell cd hook for deprecation warnings."""
    from .shell_hook import install_hook

    ok, msg = install_hook()
    if ok:
        console.print(f"[green]✓[/green] {msg}")
    else:
        console.print(f"[red]✗[/red] {msg}")
        raise typer.Exit(1)


@hook_app.command(name="uninstall")
def hook_uninstall() -> None:
    """Remove shell cd hook."""
    from .shell_hook import uninstall_hook

    ok, msg = uninstall_hook()
    if ok:
        console.print(f"[green]✓[/green] {msg}")
    else:
        console.print(f"[yellow]⚠[/yellow] {msg}")


# --- version ---

def version_callback(value: bool) -> None:
    if value:
        console.print(f"chowkidar {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Chowkidar — Local-first LLM model deprecation watchdog."""
    pass


if __name__ == "__main__":
    app()
