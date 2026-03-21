# Chowkidar

*(Dependabot for your LLMs)*

[![PyPI Version](https://img.shields.io/pypi/v/chowkidar.svg)](https://pypi.org/project/chowkidar/) [![PyPI Total Downloads](https://img.shields.io/pypi/dt/chowkidar.svg)](https://pypi.org/project/chowkidar/)

**Local-first LLM model deprecation watchdog.**

Chowkidar scans your project configs for LLM model strings, cross-references them against a local deprecation registry, and alerts you before models sunset — via desktop notifications and IDE rules that instruct AI assistants to update deprecated models automatically.

Everything runs on your machine. Zero data exfiltration.

## Quick Start

```bash
pip install chowkidar

# First-time setup (initializes config + database)
chowkidar setup --skip-slm

# Fetch deprecation data from providers
chowkidar sync

# Scan your project
chowkidar scan .

# Check for deprecated models
chowkidar check .
```

## Features

- **Multi-format scanning**: `.env`, YAML, TOML, JSON, Python, JavaScript, TypeScript
- **Provider coverage**: OpenAI, Anthropic, Google, Mistral (extensible plugin architecture)
- **IDE rules (zero-config)**: Auto-generates rules files for Cursor, Claude Code, VS Code/Copilot, Windsurf
- **MCP server**: Interactive tools for querying deprecation status from your IDE
- **Desktop notifications**: Threshold-based alerts (90d, 30d, 7d, sunset)
- **Background daemon**: Periodic scanning with OS-native service installation
- **Local SLM**: Optional Ollama integration for parsing unstructured deprecation announcements
- **Safe updates**: File locking, atomic writes, automatic backups, dry-run mode
- **Cross-platform**: macOS, Linux, Windows

## Commands

```
chowkidar setup [--skip-slm]     # Initialize config, DB, and optional SLM
chowkidar scan [PATH]            # Scan for model strings
chowkidar sync                   # Fetch deprecation data
chowkidar check [PATH]           # Check for deprecated models
chowkidar status                 # Show daemon status and watched projects
chowkidar watch <PATH>           # Register project for monitoring
chowkidar unwatch <PATH>         # Unregister project
chowkidar pin <MODEL> [--reason] # Suppress alerts for a model
chowkidar unpin <MODEL>          # Re-enable alerts
chowkidar snooze <MODEL> --days  # Temporarily suppress alerts
chowkidar daemon                 # Start background daemon
chowkidar install-service        # Install OS-native service
chowkidar mcp                    # Start MCP server (for IDE)
chowkidar config [KEY] [VALUE]   # View/set configuration
chowkidar update [--dry-run]     # Update deprecated models in .env
chowkidar rules write [PATH]     # Generate IDE rules files
chowkidar rules clean [PATH]     # Remove generated rules files
chowkidar slm status             # Check SLM availability
```

## IDE Integration

### Automatic Rules (Recommended)

Chowkidar writes rules files that AI assistants auto-discover — no configuration needed. If standard desktop notifications about model deprecation are ignored or snoozed, Chowkidar acts as your ultimate fallback: it auto-updates your editor's rules to ensure your AI model knows to update the deprecated model automatically.

| Editor | Rules File |
|---|---|
| Cursor | `.cursor/rules/chowkidar-alerts.mdc` |
| Claude Code | `.claude/rules/chowkidar-alerts.md` |
| VS Code/Copilot | `.github/copilot-instructions.md` |
| Windsurf | `.windsurfrules` |

Run `chowkidar rules write` or let the daemon do it automatically.

### MCP Server (Advanced)

Add to your IDE's MCP config:

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

## Configuration

Config file: `~/.chowkidar/config.toml`

| Key | Default | Description |
|---|---|---|
| `auto_update` | `false` | Allow automatic .env modifications |
| `write_rules` | `true` | Generate IDE rules files |
| `gitignore_rules` | `true` | Add rules files to .gitignore |
| `slm_enabled` | `false` | Use local SLM for parsing |
| `slm_model` | `gemma3:1b` | Ollama model for SLM |
| `scan_interval_hours` | `4` | How often to scan watched projects |
| `sync_interval_hours` | `24` | How often to fetch provider data |

## Security

- **Zero exfiltration**: No env content, API keys, or paths leave your machine
- **Read-only by default**: File modification requires explicit `auto_update = true`
- **Atomic writes**: All modifications use temp file + `os.replace`
- **Automatic backups**: `.env.chowkidar.bak` created before any change
- **File locking**: Prevents concurrent write corruption

## License

MIT
