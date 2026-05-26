# Chowkidar

[![PyPI Version](https://img.shields.io/badge/pypi-v0.7.7-blue)](https://pypi.org/project/chowkidar/0.7.7/)
[![GitHub Release](https://img.shields.io/badge/release-v0.7.7-blue)](https://github.com/bhav09/chowkidar/releases/latest)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/chowkidar?period=total&units=INTERNATIONAL_SYSTEM&left_color=GREY&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/chowkidar)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Chowkidar** is a secure, local-first LLM model deprecation watchdog. It scans your codebase and configuration files for LLM model references, cross-references them with a locally cached deprecation database, and alerts you before models sunset.

Everything runs on your machine. Zero data exfiltration.

## Core Features

- **Multi-Format Scanner & Structured Writers**
  Scans and parses model strings in `.env`, JSON, YAML, TOML, `docker-compose`, and source code. At the 1-day threshold, safely auto-updates structured configuration files with atomic writes, backups, and file locking.

- **Notification-First Governance & Per-Reference Audit Log**
  Alerts via native OS toasts and webhooks (Slack/Discord/generic) at 30 days, 15 days, 7 days, and 1 day before expiration. Every notification and update attempt is logged in a detailed audit ledger.

- **Deployment Signal Detector**
  Analyzes repo evidence (CI, Docker, Kubernetes, Vercel, Terraform) to flag likely deployed environments, preventing blind or risky local writes.

- **Cloud Environment Adapters (Planned)**
  Explicit, contract-ready adapter interface designed for dry-running, updating, and verifying remote secret/config stores on Vercel, Kubernetes, AWS Secrets/SSM, GCP Secret Manager, and Azure Key Vault (currently running in disabled stub mode pending credential integration).

- **Unified Risk & Capability Analysis**
  Guarantees migrations won't degrade your system by verifying context windows, output tokens, vision, tool usage, JSON mode, streaming, and cost impacts.

- **AI-Assistant Rules & MCP Server**
  Generates zero-config rule instructions (`.mdc`, `CLAUDE.md`, etc.) to guide Cursor, Claude Code, Copilot, and Windsurf, alongside an interactive MCP server.

## Installation & Project Setup

```bash
# 1. Install chowkidar in your project directory
pip install chowkidar

# 2. Run the idempotent project-scoped setup
chowkidar setup
```

### Project-Scoped Monitoring

The `chowkidar setup` command provides a zero-friction setup that configures everything for your project:
1. **Config & Database**: Creates your config and database files under `.chowkidar/` inside your project root.
2. **Initial Scan & Sync**: Syncs provider deprecation tables and performs an immediate first-time scan on the repository to initialize alerts. (Note: IDE rule files are generated and updated automatically by the background daemon during monitoring cycles, or manually via `chowkidar rules write`).

You can customize behavior inside `.chowkidar/config.toml` or via the CLI:
```bash
# Change directory scan depth
chowkidar config discover_max_depth 5
```

## Top 10 CLI Commands

Below are the 10 most relevant commands for daily use.

### 1. `chowkidar setup`
Project-scoped configuration, database initialization, provider sync, and initial repository scan.

### 2. `chowkidar sync`
Fetches and updates the local deprecation registry from providers.

### 3. `chowkidar scan`
Locates all LLM model references within your code and configuration files.

### 4. `chowkidar check`
Cross-references detected model strings against the deprecation registry.

### 5. `chowkidar status`
Displays watched projects, sync freshness, and background daemon health.

### 6. `chowkidar watch`
Registers a project path with the background daemon for periodic scans.

### 7. `chowkidar daemon`
Starts the background monitoring loop (sends alerts at 30, 15, 7, and 1 day before expiry).

### 8. `chowkidar update`
Previews (via `--dry-run`) or applies safe updates of deprecated model strings in structured configuration files (such as `.env`, JSON, YAML, TOML, and `docker-compose.yml`).

### 9. `chowkidar mcp`
Launches the stdio MCP server for active IDE-level AI assistant queries.

### 10. `chowkidar report`
Generates comprehensive Markdown, JSON, or interactive HTML reports.

See [COMMANDS.md](COMMANDS.md) for the complete reference containing all available CLI commands.

## Editor Integration

### Passive AI Rules (Zero-Config)
AI editors auto-discover instructions in your project workspace. Chowkidar outputs non-destructive rule tables:
- **Cursor**: `.cursor/rules/chowkidar-alerts.mdc`
- **Claude Code**: `.claude/rules/chowkidar-alerts.md`
- **VS Code / Copilot**: `.github/copilot-instructions.md`
- **Windsurf**: `.windsurfrules`

### MCP Server (Active)
Configure the stdio MCP server in your IDE's configuration file:
```json
{
  "mcpServers": {
    "chowkidar": {
      "command": "chowkidar",
      "args": ["mcp"]
    }
  }
}
```

## Security & Local Safety

- **Privacy First**: No code, project paths, keys, or configurations are ever sent to external APIs.
- **Safe Writes**: Modifying configuration files requires setting `auto_update = true` in your config. Every update atomic-writes via a temp file and saves a `.chowkidar.bak` file for automatic rollback.
- **Concurrent-Safe**: Uses system-level `filelock` to protect files from concurrent daemon/CLI writes.

## License

MIT
