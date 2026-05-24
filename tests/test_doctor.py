"""Tests for the setup logic and daemon status checks."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from chowkidar.config import Config
from chowkidar.sentinel.daemon import ChowkidarDaemon
from chowkidar.registry.db import Registry


def test_daemon_write_status(tmp_path):
    config = Config(tmp_path / "config.toml")
    
    with patch("chowkidar.sentinel.daemon.CHOWKIDAR_HOME", tmp_path), \
         patch("chowkidar.sentinel.daemon.Registry") as mock_registry_class:
        
        mock_registry = MagicMock()
        mock_registry.last_sync_time.return_value = "2026-05-23T12:00:00Z"
        mock_registry.get_watched_projects.return_value = ["/mock/project"]
        # Mock SQLite connection execute for last_scanned_at
        mock_conn = MagicMock()
        mock_row = MagicMock()
        mock_row.__getitem__.return_value = "2026-05-23T15:00:00Z"
        mock_conn.execute.return_value.fetchone.return_value = mock_row
        mock_registry.conn = mock_conn
        
        mock_registry_class.return_value = mock_registry
        
        daemon = ChowkidarDaemon(config)
        daemon._write_status(status="running")
        
        status_file = tmp_path / "daemon_status.json"
        assert status_file.exists()
        
        data = json.loads(status_file.read_text(encoding="utf-8"))
        assert data["status"] == "running"
        assert data["last_sync_at"] == "2026-05-23T12:00:00Z"
        assert data["last_scan_at"] == "2026-05-23T15:00:00Z"
        assert "pid" in data
        assert "started_at" in data
        assert "last_heartbeat" in data


@patch("chowkidar.slm.setup.full_setup")
def test_setup_command_logic(mock_full_setup, tmp_path):
    from chowkidar.cli import setup
    
    mock_full_setup.return_value = (True, "SLM setup skipped")
    
    config_file = tmp_path / ".chowkidar" / "config.toml"
    config = Config(config_file)
    
    with patch("chowkidar.cli.CHOWKIDAR_HOME", tmp_path / ".chowkidar"), \
         patch("chowkidar.cli._get_config", return_value=config), \
         patch("chowkidar.registry.db.Registry") as mock_registry_class, \
         patch("chowkidar.cli.typer.confirm", return_value=False), \
         patch("chowkidar.scanner.scan_directory") as mock_scan_directory:
         
        mock_registry = MagicMock()
        mock_registry.last_sync_time.return_value = None
        mock_registry_class.return_value = mock_registry
        
        mock_scan_res = MagicMock()
        mock_scan_res.all_models = []
        mock_scan_directory.return_value = mock_scan_res
        
        # Call setup command in non-interactive mode
        setup(skip_slm=True, non_interactive=True)
        
        # Verify database and watch project registration
        mock_registry.init_db.assert_called_once()
        mock_registry.watch_project.assert_called_once_with(str(tmp_path))
        
        # Verify scanning was triggered
        mock_scan_directory.assert_called_once_with(tmp_path)
        mock_registry.save_scan_results.assert_called_once()
        mock_registry.update_watch_timestamp.assert_called_once()
