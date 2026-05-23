# Chowkidar Command Reference

This document provides a comprehensive reference of all CLI commands available in **Chowkidar**.

## Core Commands

### `chowkidar setup`
Initializes Chowkidar configuration, database, and system-specific local SLM components.
- **Usage**: `chowkidar setup [--skip-slm]`
- **Options**:
  - `--skip-slm`: Skips Ollama check and model download (runs on provider metadata alone).

### `chowkidar sync`
Fetches and updates the local SQLite deprecation registry from configured providers (OpenAI, Anthropic, Google, Mistral).
- **Usage**: `chowkidar sync`

### `chowkidar scan [PATH]`
Scans the specified directory path for LLM model references in code and configuration files.
- **Usage**: `chowkidar scan [PATH]` (defaults to current directory if omitted).

### `chowkidar check [PATH]`
Cross-references found model references against the local deprecation database and prints inline diagnostics and warnings.
- **Usage**: `chowkidar check [PATH] [--quiet]`
- **Options**:
  - `-q, --quiet`: Quiet mode for shell hook checks (returns a single-line summary).

---

## Daemon & Background Scanning

### `chowkidar status`
Displays the background daemon health, database freshness, list of watched projects, and active alerts.
- **Usage**: `chowkidar status`

### `chowkidar watch <PATH>`
Registers a project directory path with the background daemon database for continuous monitoring.
- **Usage**: `chowkidar watch <PATH>`

### `chowkidar unwatch <PATH>`
Unregisters a project directory path to stop periodic background scans.
- **Usage**: `chowkidar unwatch <PATH>`

### `chowkidar daemon`
Starts the periodic background monitoring loop in the foreground (runs every 4 hours).
- **Usage**: `chowkidar daemon`

### `chowkidar install-service`
Registers and installs the background daemon as an OS-native service (launchd on macOS, systemd on Linux, Task Scheduler on Windows).
- **Usage**: `chowkidar install-service`

### `chowkidar uninstall-service`
Stops and unregisters the native system service.
- **Usage**: `chowkidar uninstall-service`

### `chowkidar logs`
Streams or displays daemon execution logs.
- **Usage**: `chowkidar logs [--tail N]`

---

## Alert Silencing & Overrides

### `chowkidar pin <MODEL>`
Suppresses deprecation notifications for a specific model ID, keeping its existing value even past sunset.
- **Usage**: `chowkidar pin <MODEL> [--reason TEXT]`

### `chowkidar unpin <MODEL>`
Re-enables alert notifications for a previously pinned model ID.
- **Usage**: `chowkidar unpin <MODEL>`

### `chowkidar snooze <MODEL> --days N`
Temporarily mutes deprecation alerts for a model ID for a specified number of days.
- **Usage**: `chowkidar snooze <MODEL> --days N`

---

## Interactive Updates & Safe Fixes

### `chowkidar update [PATH]`
Interactively reviews and safely applies recommended model replacements to structured configuration files (`.env`, JSON, YAML, TOML, `docker-compose`).
- **Usage**: `chowkidar update [PATH] [--dry-run]`
- **Options**:
  - `--dry-run`: Preview updates without modifying files.

### `chowkidar fix [PATH]`
Safely automates migrations by modifying files and optionally creating git branches and pull requests.
- **Usage**: `chowkidar fix [PATH] [--branch] [--pr]`

---

## Reports & FinOps Analytics

### `chowkidar report [PATH]`
Generates rich, detailed deprecation reports in Markdown, JSON, or interactive HTML formats.
- **Usage**: `chowkidar report [PATH] [--format markdown|json|html]`

### `chowkidar cost [PATH]`
Runs pricing comparison calculations and reveals exact FinOps cost-savings of migrating to recommended successors.
- **Usage**: `chowkidar cost [PATH]`

### `chowkidar optimize [PATH]`
Scans and evaluates all models in use to identify cost-saving drop-in replacements with direct percentage savings.
- **Usage**: `chowkidar optimize [PATH]`

### `chowkidar diff <OLD> <NEW>`
Provides a direct comparison of context windows, pricing, and specific feature sets (vision, streaming, tool use, JSON mode) between two model IDs.
- **Usage**: `chowkidar diff <OLD> <NEW>`

### `chowkidar predict [PATH]`
Uses historical release and sunset data to estimate the deprecation probability and lifespan of models in use.
- **Usage**: `chowkidar predict [PATH]`

### `chowkidar dashboard`
Launches an interactive terminal-based TUI to visualize model deprecation risk across all watched repositories.
- **Usage**: `chowkidar dashboard`

---

## CI/CD & Hook Utilities

### `chowkidar gate [PATH]`
Integrates with CI/CD systems or git pre-commit hooks to block builds if critical or sunset-passed models are found.
- **Usage**: `chowkidar gate [PATH]`

### `chowkidar test-migration`
Executes dry-run completions on both old and new model candidates to compare prompt response outputs and prevent regressions.
- **Usage**: `chowkidar test-migration --old <MODEL> --new <MODEL> --prompts <FILE>`

### `chowkidar test-notify`
Fires a native mock OS desktop alert and dynamically builds a clickable report path to test action triggers.
- **Usage**: `chowkidar test-notify`

### `chowkidar rules write [PATH]`
Manually generates passthrough prompt rules (`.mdc`, `CLAUDE.md`, `.windsurfrules`) to pass deprecation context to AI coding assistants.
- **Usage**: `chowkidar rules write [PATH]`

### `chowkidar rules clean [PATH]`
Clears all generated rule files from the target directory path.
- **Usage**: `chowkidar rules clean [PATH]`

### `chowkidar hook install`
Installs a lightweight shell hook that displays quick model deprecation warning alerts on directory changes (`cd`).
- **Usage**: `chowkidar hook install`

### `chowkidar hook uninstall`
Uninstalls the shell warnings hook.
- **Usage**: `chowkidar hook uninstall`

---

## SLM (Small Local Model) Diagnostics

### `chowkidar slm status`
Inspects system RAM, free disk space, and Ollama connection status to check SLM readiness.
- **Usage**: `chowkidar slm status`

### `chowkidar slm choose`
Benchmarks local hardware resources and automatically pulls the optimal local model profile (`gemma3:1b`, `qwen2.5:0.5b`, etc.).
- **Usage**: `chowkidar slm choose`

### `chowkidar slm unload`
Unloads the active SLM model from memory, reclaiming RAM instantly for the system.
- **Usage**: `chowkidar slm unload`
