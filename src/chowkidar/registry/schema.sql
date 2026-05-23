CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    aliases TEXT DEFAULT '[]',
    sunset_date TEXT,
    replacement TEXT,
    replacement_confidence TEXT DEFAULT 'medium',
    breaking_changes INTEGER DEFAULT 0,
    source_url TEXT,
    current_snapshot TEXT,
    privacy_tier TEXT DEFAULT 'unknown',
    last_checked_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scan_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_path TEXT NOT NULL,
    file_path TEXT NOT NULL,
    variable_name TEXT,
    model_value TEXT NOT NULL,
    model_id TEXT,
    source_type TEXT DEFAULT 'env',
    last_scanned_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_path TEXT NOT NULL,
    model_id TEXT NOT NULL,
    threshold TEXT NOT NULL,
    notified_at TEXT DEFAULT (datetime('now')),
    snoozed_until TEXT,
    file_path TEXT,
    variable_name TEXT,
    channel TEXT DEFAULT 'desktop',
    delivery_status TEXT DEFAULT 'delivered',
    webhook_status TEXT,
    report_path TEXT,
    recommendation TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS pinned_models (
    model_id TEXT PRIMARY KEY,
    reason TEXT,
    pinned_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS watched_projects (
    project_path TEXT PRIMARY KEY,
    added_at TEXT DEFAULT (datetime('now')),
    last_scanned_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_project ON scan_results(project_path);
CREATE INDEX IF NOT EXISTS idx_scan_model ON scan_results(model_id);
CREATE INDEX IF NOT EXISTS idx_notif_project_model ON notification_log(project_path, model_id);
CREATE INDEX IF NOT EXISTS idx_notif_reference ON notification_log(project_path, file_path, variable_name, model_id, threshold);
CREATE TABLE IF NOT EXISTS action_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_path TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_path TEXT,
    variable_name TEXT,
    model_id TEXT,
    old_value TEXT,
    new_value TEXT,
    status TEXT NOT NULL,
    message TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_action_project ON action_audit(project_path);
CREATE INDEX IF NOT EXISTS idx_action_model ON action_audit(model_id);
CREATE TABLE IF NOT EXISTS model_pricing (
    model_id TEXT PRIMARY KEY,
    input_cost_per_1m REAL,
    output_cost_per_1m REAL,
    context_window INTEGER,
    max_output_tokens INTEGER,
    last_updated TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS model_capabilities (
    model_id TEXT PRIMARY KEY,
    context_window INTEGER,
    max_output_tokens INTEGER,
    supports_vision INTEGER DEFAULT 0,
    supports_tools INTEGER DEFAULT 0,
    supports_json_mode INTEGER DEFAULT 0,
    supports_streaming INTEGER DEFAULT 1,
    last_updated TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS migration_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT NOT NULL,
    note_type TEXT NOT NULL,
    content TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_models_provider ON models(provider);
CREATE INDEX IF NOT EXISTS idx_models_sunset ON models(sunset_date);
CREATE INDEX IF NOT EXISTS idx_migration_notes_model ON migration_notes(model_id);
