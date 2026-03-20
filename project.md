# Chowkidar — Enhanced Task Brief (ETB)

# Chowkidar — Enhanced Task Brief (ETB)

## Pre-Execution Protocol: ETB Mandatory Fields for v0.2.0 (Testing, Optimization, Expansion & Release)

* **User Goal:** Comprehensively test the application (unit, integration, E2E), identify and fix bugs, optimize UX/execution time, add robust logical features, and bump versions across GitHub, PyPI, and VS Code Marketplace.
* **Mode:** [Production] As a Staff SDE, executing a major version bump (v0.2.0) requires exhaustive validation. The focus is on resilience, speed, zero-downtime, and comprehensive cross-platform distribution.
* **Code Grounding:** `tests/`, `src/chowkidar/`, `extension/`, `pyproject.toml`, `extension/package.json`
* **Dependency Check:** Python caching tools (`diskcache` or `functools.lru_cache`) might be necessary for optimization.
* **The "Safety Audit":**
  * *Production:* Ensure that new features (like caching or automated suggestions) do not introduce Race Conditions or bloat the sync time. Test the CLI concurrently. Verify `.vsix` build doesn't bundle unnecessary large assets.
* **Step-by-Step Plan:**
  1. **Comprehensive Validation:** Run `pytest` (unit/integration) and CLI subprocesses (E2E). Address any bugs found immediately.
  2. **Optimization:** Implement caching for the `sync` scraper and local registry to drastically reduce `chowkidar sync` execution time and minimize provider API hitting.
  3. **Feature Addition:** Introduce a "cost/speed aware" successor recommendation logic or parallelize the `scan` across large directories using `ThreadPoolExecutor` to dramatically improve UX on massive mono-repos.
  4. **Version Bumping:** Update `pyproject.toml` and `package.json` to version `0.2.0`.
  5. **Distribution:** Build and securely push to GitHub (git push), PyPI (`twine`), and package the new `.vsix` (`vsce`).

## Status: AWAITING APPROVAL

---

## Pre-Execution Protocol: ETB Mandatory Fields

* **User Goal:** Rebuild virtual environment, initialize Git repository, update README.md, test codebase, and publish package to PyPI.
* **Mode:** [Production] This is a public tool for developers operating on their local systems. Needs to run flawlessly without leaks, properly packaged.
* **Code Grounding:** `README.md`, `pyproject.toml`, `.gitignore`, `tests/`
* **Dependency Check:** Python standard lib + project dependencies defined in `pyproject.toml`. No new deps requested. Use `hatch` for build/publish.
* **The "Safety Audit":**
  * *Production:* Ensure the PyPI token is not printed in logs, commit history, or `.env` files. Ensure `.gitignore` ignores `.venv`, `.env`, build artifacts, and secrets.
* **Step-by-Step Plan:**
  1. Setup Git repo and `.gitignore` so no secrets or `.venv` details leak.
  2. Update `README.md` to document auto-updating editor's rules when notifications are ignored.
  3. Recreate `.venv` and install `[dev]` dependencies securely via `pip`.
  4. Run `pytest` to guarantee all existing tests pass before release.
  5. Build package (`hatch build`) and publish (`hatch publish` or `twine`) to PyPI.

---

## Problem Statement

LLM providers are releasing and sun-setting models at an accelerating pace. Developers hard-code model identifiers in `.env` files and configs, then get blindsided when a model is deprecated — causing production failures, degraded outputs, or silent billing changes. There is no local, privacy-respecting tool that watches for these deprecations and alerts the developer proactively.

## Objective

A **local-first Python package** that:

1. Scans project files for LLM model identifiers.
2. Maintains a local registry of model deprecation/sunset dates (scraped from provider sources).
3. Uses a **local SLM** (via Ollama) to parse unstructured deprecation announcements into structured data.
4. Alerts the user via native OS notifications at configurable thresholds.
5. **Writes IDE rules files** (Cursor `.mdc`, Claude Code `CLAUDE.md`, Copilot `.github/copilot-instructions.md`, etc.) to passively instruct AI assistants to update deprecated models — **zero config, works everywhere**.
6. Exposes an **MCP server** as the power-user layer for real-time queries and interactive updates.

**Everything stays on the local machine. Zero data exfiltration.**

---

## Architecture (Four Layers)

### Layer 1 — The Scanner (Passive)
- Scans filesystem for `.env`, `.env.local`, `.env.*`, `docker-compose.yml`, `settings.py`, `constants.ts`, `.yaml`, `.toml`, `.json`, `pyproject.toml`.
- Uses format-aware parsers + regex to find model strings matching known patterns (e.g., `gpt-[0-9a-z.-]+`, `claude-[0-9a-z.-]+`, `gemini-[0-9a-z.-]+`, `mistral-[0-9a-z.-]+`).
- Maps variable names to their model string values.
- Normalizes model strings to canonical IDs (e.g., `gpt-4o-2024-08-06` → `openai/gpt-4o-2024-08-06`).

### Layer 2 — The Registry (Dynamic) + Local SLM
- Local SQLite database at `~/.chowkidar/registry.db`.
- **Shadow Scraper** runs every 24 hours (when online):
  - OpenAI: `/v1/models` endpoint (structured `deprecation_date` field).
  - Anthropic: Release notes / docs pages (semi-structured scraping).
  - Google: Vertex AI / AI Studio deprecation schedules.
  - Mistral: API docs / changelog.
- Each model record includes: `sunset_date`, `replacement`, `replacement_confidence`, `breaking_changes`, `source_url`.
- **Local SLM via Ollama** (see dedicated section below) parses unstructured "sunset announcement" blog posts into structured JSON when regex/heuristic parsing fails.

### Layer 3 — The Sentinel (Active)
- Background daemon process.
- Cross-references scanner results against registry every 4 hours.
- Fires OS-native notifications at thresholds:
  - **>90 days**: No action.
  - **30 days**: Low-priority desktop notification.
  - **7 days**: Urgent desktop notification + terminal warning.
  - **Sunset reached**: Blocking warning via IDE rules + MCP.
- Notification deduplication: tracks `(model, project, threshold)` to avoid spam.
- Snooze support: `chowkidar snooze <model> --days N`.

### Layer 4 — IDE Integration (Rules + MCP)
- **Primary mechanism**: Write/update IDE rules files so AI assistants are passively aware of deprecations.
- **Secondary mechanism**: MCP server for real-time queries and interactive tool calls.
- See dedicated sections below for both.

---

## Local SLM Integration (Ollama)

### Purpose
Parse unstructured provider blog posts, changelogs, and announcement pages into structured deprecation data when regex/heuristic parsing is insufficient.

### Installation Flow (`chowkidar setup`)
1. **Check for Ollama**: `which ollama` / check if `ollama` binary exists.
2. **If missing**: Prompt user and install automatically:
   - macOS: `brew install ollama` (or `curl -fsSL https://ollama.com/install.sh | sh`)
   - Linux: `curl -fsSL https://ollama.com/install.sh | sh`
   - Windows: Download installer via `httpx`
3. **Start Ollama service**: `ollama serve` (if not already running).
4. **Pull model**: `ollama pull gemma3:1b` (~815MB, one-time download).
5. **Verify**: Run a test prompt to confirm the model responds.

### Model Choice
- **Default**: `gemma3:1b` — small footprint (~815MB), good at structured extraction.
- **Alternative**: `qwen2.5:0.5b` (~400MB) for very constrained systems.
- **Configurable**: `chowkidar config set slm_model <model_name>`.

### Usage within Chowkidar
- The SLM is invoked **only** during `chowkidar sync` when the scraper encounters unstructured text (blog posts, changelogs) that can't be parsed by regex.
- Prompt template extracts: `{ "model": string, "sunset_date": "YYYY-MM-DD", "replacement": string, "confidence": "high|medium|low" }`.
- Results are validated against a JSON schema before insertion into the registry.
- **Graceful degradation**: If Ollama is not installed/running, the scraper skips unstructured sources and logs a warning. Chowkidar remains fully functional with structured API sources alone.

### CLI Commands
```
chowkidar setup              # Full setup: check/install Ollama + pull SLM
chowkidar setup --skip-slm   # Setup without SLM (structured sources only)
chowkidar config set slm_model <name>  # Change SLM model
chowkidar slm status         # Check if Ollama is running and model is available
```

### Privacy
- The SLM runs **entirely locally** via Ollama.
- Only **public blog post text** (already fetched by the scraper) is sent to the local model.
- No `.env` content, API keys, or project data is ever sent to the SLM.

---

## IDE Rules Integration (Primary — Zero-Config)

### Concept
Instead of requiring users to configure MCP, Chowkidar **writes rules files directly into the project** that AI assistants auto-discover. When the AI edits a file containing a deprecated model string, it already knows to update it.

### Rules File Formats (per editor)

#### Cursor (`.cursor/rules/chowkidar-alerts.mdc`)
```markdown
---
description: Chowkidar — LLM model deprecation alerts
globs: ["**/.env*", "**/config.*", "**/settings.*", "**/constants.*", "**/docker-compose.*"]
alwaysApply: false
---

## Model Deprecation Alerts (auto-generated by Chowkidar)

The following models used in this project are deprecated or sunsetting soon.
When editing any file containing these model strings, update them to the recommended replacements.

| Variable | Current Model | Sunset Date | Replacement | Confidence |
|---|---|---|---|---|
| LLM_MODEL_NAME (.env) | gpt-3.5-turbo | 2026-04-01 | gpt-4o-mini | high |
| ANTHROPIC_MODEL (.env) | claude-2.1 | 2026-05-15 | claude-sonnet-4-20250514 | high |

Last updated: 2026-03-09T14:30:00Z by Chowkidar.
```

#### Claude Code (`.claude/rules/chowkidar-alerts.md`)
```markdown
---
description: Chowkidar — LLM model deprecation alerts
globs: ["**/.env*", "**/config.*", "**/settings.*"]
---

## Model Deprecation Alerts (auto-generated by Chowkidar)

(Same table content as above)
```

#### VS Code / GitHub Copilot (`.github/copilot-instructions.md`)
- Appends a `## Chowkidar Model Alerts` section to the existing file (or creates it).
- Uses `<!-- chowkidar:start -->` / `<!-- chowkidar:end -->` markers to update only its own section.

#### Windsurf (`.windsurfrules`)
- Appends a Chowkidar section with markers, similar to Copilot.

#### Antigravity
- Writes to Antigravity's rules file format (TBD based on their spec).

### Behavior
- **Auto-generated**: Daemon writes/updates rules files whenever it detects deprecations in a watched project.
- **Non-destructive**: Uses marker comments (`<!-- chowkidar:start/end -->`) to manage its own section without touching user-written rules.
- **Opt-out**: `chowkidar config set write_rules false` disables rules file generation.
- **`.gitignore`-friendly**: By default, adds the rules files to `.gitignore` (configurable). These are local developer alerts, not project config.

### Why Rules-First?
| Aspect | Rules Files | MCP Server |
|---|---|---|
| Setup effort | **Zero** — auto-discovered | User must edit MCP config |
| Server process | **None** — just a file | Must be running |
| Editor coverage | **All AI editors** | Only MCP-compatible |
| Real-time queries | No (updated by daemon) | **Yes** |
| Can call tools | No — instructs the AI | **Yes** |
| Complexity | **Trivial** | Moderate |

Rules handle the "passively instruct the AI to update models" use case perfectly. MCP adds interactive power for advanced users.

---

## MCP Server (IDE Integration — Power-User Layer)

### Transport
- `stdio` — IDE spawns the process, communicates over stdin/stdout.

### Tools Exposed
| Tool | Description | Default |
|---|---|---|
| `list_deprecated_models()` | Returns models in current project near/past sunset | Always available |
| `get_model_status(model_id)` | Returns deprecation info for a specific model | Always available |
| `update_model_env(file, var, new_model)` | Overwrites env var with recommended successor | **Requires `AUTO_UPDATE=true`** |

### IDE Support
- Cursor: Add to `~/.cursor/mcp.json`
- Claude Code: Add to `~/.claude/claude_desktop_config.json`
- VS Code: Via MCP extension config
- Antigravity: Via MCP config

### Context Injection
When connected, the MCP server provides context like:
> "Note: You are using `gpt-3.5-turbo` in this project. This model sunsets in 5 days. Recommended replacement: `gpt-4o-mini` (high confidence, no breaking changes)."

---

## CLI Commands

```
chowkidar setup                 # Full first-run setup: check/install Ollama + pull SLM
chowkidar setup --skip-slm      # Setup without SLM (structured sources only)
chowkidar scan [PATH]           # Scan a project directory for model strings
chowkidar sync                  # Fetch latest deprecation data from providers
chowkidar check [PATH]          # Cross-reference scan results with registry
chowkidar status                # Show daemon status, registry freshness, watched projects
chowkidar watch <PATH>          # Register a project for background monitoring
chowkidar unwatch <PATH>        # Unregister a project
chowkidar pin <model> [--reason]# Suppress notifications for a model
chowkidar unpin <model>         # Re-enable notifications
chowkidar snooze <model> --days # Temporarily suppress notifications
chowkidar daemon                # Start background daemon (foreground mode)
chowkidar install-service       # Install OS-native background service
chowkidar uninstall-service     # Remove OS-native background service
chowkidar logs [--tail N]       # View daemon logs
chowkidar mcp                   # Start MCP server (stdio mode, called by IDE)
chowkidar config                # View/edit configuration
chowkidar config set <key> <val># Set a config value (e.g., slm_model, write_rules, auto_update)
chowkidar update --dry-run      # Preview env changes without writing
chowkidar update                # Apply env changes (with backup)
chowkidar slm status            # Check if Ollama is running and SLM model is available
chowkidar rules write [PATH]    # Manually write/refresh IDE rules files for a project
chowkidar rules clean [PATH]    # Remove Chowkidar-generated rules files from a project
```

---

## Database Schema

```sql
CREATE TABLE models (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    aliases TEXT,                  -- JSON array
    sunset_date TEXT,              -- ISO 8601 or NULL
    replacement TEXT,              -- successor model id
    replacement_confidence TEXT,   -- "high" | "medium" | "low"
    breaking_changes BOOLEAN DEFAULT 0,
    source_url TEXT,
    last_checked_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE scan_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_path TEXT NOT NULL,
    file_path TEXT NOT NULL,
    variable_name TEXT,
    model_value TEXT NOT NULL,
    model_id TEXT,
    last_scanned_at TEXT
);

CREATE TABLE notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_path TEXT NOT NULL,
    model_id TEXT NOT NULL,
    threshold TEXT NOT NULL,
    notified_at TEXT DEFAULT (datetime('now')),
    snoozed_until TEXT
);

CREATE TABLE pinned_models (
    model_id TEXT PRIMARY KEY,
    reason TEXT,
    pinned_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE watched_projects (
    project_path TEXT PRIMARY KEY,
    added_at TEXT DEFAULT (datetime('now')),
    last_scanned_at TEXT
);
```

---

## Technical Stack

| Component | Library | Purpose |
|---|---|---|
| CLI | `typer` + `rich` | Commands, formatted output |
| Env parsing | `python-dotenv` | `.env` file read/write |
| Config parsing | `tomli`, `pyyaml` | `.toml`, `.yaml` support |
| HTTP client | `httpx` | Async provider scraping |
| Retry logic | `tenacity` | Exponential backoff for scraping |
| Database | `sqlite3` (stdlib) | Local registry |
| Local SLM | `ollama` (Python SDK) | Interface with Ollama for SLM inference |
| Notifications | `plyer` | Cross-platform desktop alerts |
| MCP server | `mcp` SDK | IDE integration (stdio) |
| Background | `schedule` | Periodic scan/sync loop |
| File safety | `filelock` | Concurrent `.env` access protection |
| Logging | `structlog` or stdlib | Structured logs with rotation |
| Testing | `pytest` + `respx` | Unit tests, HTTP mocking |

---

## Security & Privacy Constraints (Non-Negotiable)

1. **Zero exfiltration**: No `.env` content, API keys, or project paths sent externally.
2. **Local registry**: Deprecation data is downloaded TO the user, never uploaded FROM.
3. **Read-only defaults**: File modification requires explicit `AUTO_UPDATE=true` in `~/.chowkidar/config.toml`.
4. **Atomic writes**: All file modifications use write-to-temp + `os.replace` pattern.
5. **Automatic backups**: `.env.bak` created before any modification.
6. **File locking**: `filelock` prevents concurrent write corruption.

---

## Engineering Cases (Edge Cases & Concerns)

### Model String Normalization
- Different naming conventions across providers and proxy tools (LiteLLM, OpenRouter).
- Aliases like `gpt-4o`, `gpt-4o-2024-08-06`, `openai/gpt-4o` must resolve to the same canonical entry.

### Offline Resilience
- Registry shows `last_synced_at` in CLI output.
- Warning if registry is >48 hours stale.
- Daemon retries sync on reconnection (check connectivity before sync attempt).

### Multi-Project Support
- `chowkidar watch` registers project paths.
- Daemon iterates all watched projects during scan cycles.

### Intentional Pinning
- `chowkidar pin` suppresses alerts for models users intentionally keep.
- Pinned models still appear in `scan` output but marked as `[PINNED]`.

### Replacement Confidence
- `high`: Direct successor, same capabilities, provider-recommended.
- `medium`: Similar capabilities, minor behavior differences.
- `low`: Significant capability/pricing changes, manual review recommended.

### Notification Deduplication
- Track `(model, project, threshold)` tuples in `notification_log`.
- Don't re-notify for same threshold within 24 hours.

### Provider Plugin Architecture
- Abstract `ProviderAdapter` protocol for adding new providers.
- Each provider implements `fetch_models()` and `fetch_deprecations()`.
- Community can contribute new adapters.

### Rollback
- `chowkidar update` creates `.env.chowkidar.bak` before modification.
- Future: `chowkidar rollback` to restore from backup.

### Cross-Platform Daemon
- MVP: `chowkidar daemon` runs in foreground (user manages lifecycle).
- Later: `chowkidar install-service` generates launchd plist (macOS) / systemd unit (Linux).

### Local SLM Edge Cases
- **Ollama not installed**: `chowkidar setup` handles installation. If user declines, SLM features degrade gracefully.
- **Ollama installed but not running**: Auto-start via `ollama serve` as a subprocess, or prompt user.
- **Model not pulled**: `chowkidar setup` pulls it. If missing at runtime, skip SLM parsing with a warning.
- **Insufficient disk/RAM**: Detect available resources before pulling. Suggest smaller model (`qwen2.5:0.5b`) or `--skip-slm`.
- **SLM hallucination**: All SLM outputs are validated against a strict JSON schema + sanity checks (e.g., sunset_date must be a valid future date, model name must match known provider patterns). Rejected outputs are logged and discarded.
- **Concurrent Ollama usage**: User might be running other Ollama workloads. Chowkidar uses low-priority requests and respects Ollama's queue.

### IDE Rules Edge Cases
- **Multiple editors on same project**: Write rules for ALL detected editors (check for `.cursor/`, `.claude/`, `.github/` directories).
- **User has existing rules files**: Never overwrite — use marker comments (`<!-- chowkidar:start -->` / `<!-- chowkidar:end -->`) to manage only Chowkidar's section.
- **Rules file format changes**: If an editor updates their rules format, Chowkidar must adapt. Template-based generation makes this easier.
- **User opts out**: `chowkidar config set write_rules false` disables all rules file generation. `chowkidar rules clean` removes existing ones.
- **Stale rules**: Rules files include a `Last updated` timestamp. The daemon refreshes them on every check cycle.

---

## Development Phases

| Phase | Scope | Key Deliverable |
|---|---|---|
| **1** | CLI + Scanner | `chowkidar scan` — parse `.env`/configs, extract model strings, output table |
| **2** | Registry + Sync | SQLite DB + `chowkidar sync` — fetch deprecation data from OpenAI API + Anthropic |
| **3** | Comparison Engine | `chowkidar check` — cross-reference scan vs registry, output warnings |
| **4** | IDE Rules Writer | `chowkidar rules write` — generate/update rules files for Cursor, Claude Code, Copilot, Windsurf |
| **5** | Daemon + Notifications | `chowkidar daemon` — background loop, OS notifications + auto-refresh rules files |
| **6** | Local SLM Setup | `chowkidar setup` — Ollama check/install, model pull, unstructured blog parsing in sync |
| **7** | MCP Server | `chowkidar mcp` — stdio MCP server with `list_deprecated_models` + `update_model_env` |
| **8** | Auto-Update + Safety | Opt-in `.env` modification with backup, dry-run, file locking |
| **9** | Provider Plugins + Polish | Adapter pattern, Google/Mistral support, `install-service` for OS daemons |

---

## Project Structure (Proposed)

```
chowkidar/
├── pyproject.toml
├── README.md
├── src/
│   └── chowkidar/
│       ├── __init__.py
│       ├── cli.py                  # Typer CLI entry point
│       ├── scanner/
│       │   ├── __init__.py
│       │   ├── env_parser.py       # .env file parsing
│       │   ├── config_parser.py    # yaml/toml/json parsing
│       │   └── patterns.py         # Model string regex patterns
│       ├── registry/
│       │   ├── __init__.py
│       │   ├── db.py               # SQLite operations
│       │   └── schema.sql          # DB schema
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py             # ProviderAdapter protocol
│       │   ├── openai.py           # OpenAI scraper
│       │   ├── anthropic.py        # Anthropic scraper
│       │   ├── google.py           # Google scraper
│       │   └── mistral.py          # Mistral scraper
│       ├── slm/
│       │   ├── __init__.py
│       │   ├── setup.py            # Ollama check/install/pull logic
│       │   ├── client.py           # Ollama Python SDK wrapper
│       │   └── prompts.py          # Prompt templates for structured extraction
│       ├── sentinel/
│       │   ├── __init__.py
│       │   ├── daemon.py           # Background daemon loop
│       │   ├── notifier.py         # OS notification logic
│       │   └── service.py          # OS service installer
│       ├── ide/
│       │   ├── __init__.py
│       │   ├── rules_writer.py     # Write/update rules files per editor
│       │   ├── detector.py         # Detect which editors are in use
│       │   └── templates/          # Jinja2/string templates for each editor format
│       │       ├── cursor.py
│       │       ├── claude_code.py
│       │       ├── copilot.py
│       │       └── windsurf.py
│       ├── mcp_server/
│       │   ├── __init__.py
│       │   └── server.py           # MCP server implementation
│       ├── updater/
│       │   ├── __init__.py
│       │   └── env_writer.py       # Safe .env modification
│       └── config.py               # User config management
├── tests/
│   ├── fixtures/                   # Sample API responses, blog posts
│   ├── test_scanner.py
│   ├── test_registry.py
│   ├── test_providers.py
│   ├── test_slm.py
│   ├── test_ide_rules.py
│   ├── test_sentinel.py
│   └── test_mcp.py
└── project.md                      # This file
```

---

## Trade-offs

| Decision | Choice | Trade-off |
|---|---|---|
| SQLite vs JSON flat file | SQLite | Slightly heavier but enables proper querying, indexing, and concurrent access |
| Rules-first vs MCP-first | Rules-first | Zero config, universal editor support, but static (daemon refreshes periodically). MCP is secondary for power users |
| Ollama SLM vs no SLM | Ollama (opt-in) | Adds ~815MB disk + install complexity, but enables parsing unstructured deprecation announcements. Graceful degradation without it |
| `gemma3:1b` vs larger models | `gemma3:1b` | Good enough for structured extraction, runs on any machine. Larger models waste resources for this task |
| stdio MCP vs HTTP MCP | stdio | Simpler, more secure (no port exposure), but one process per IDE connection |
| `plyer` vs native APIs | `plyer` | Cross-platform convenience vs less native look/feel |
| Foreground daemon (MVP) vs OS service | Foreground first | Faster to ship, but user must manage process manually |
| Regex scanning vs AST parsing | Regex first | Catches most cases fast, but may produce false positives in comments/strings |
| Scraping docs vs official APIs | Both | APIs are reliable but incomplete; scraping is fragile but catches announcements faster |
| Rules in `.gitignore` vs committed | `.gitignore` by default | Rules are local dev alerts, not project config. Configurable for teams that want shared alerts |

---

## Open Questions

1. Should Chowkidar support scanning **git history** for model strings (to catch models used in other branches)?
2. Should there be a **web dashboard** (local Flask/Streamlit) or is CLI + notifications sufficient for MVP?
3. How should we handle **proxy services** (OpenRouter, LiteLLM, AWS Bedrock) where the model string format differs from the provider's native format?
4. Should rules files be **committed to git** (team-wide alerts) or **gitignored** (personal alerts only) by default?
5. For the SLM, should Chowkidar also support **llama.cpp** directly (via `llama-cpp-python`) as an alternative to Ollama, to avoid the Ollama dependency?
6. Should `chowkidar setup` auto-run on first `pip install chowkidar` via a post-install hook, or require explicit `chowkidar setup`?

---

> **Next step**: User approves this ETB, then we begin Phase 1 implementation.
