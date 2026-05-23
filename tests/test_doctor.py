"""Tests for the doctor/bootstrap logic and daemon status checks."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from chowkidar.config import CHOWKIDAR_HOME, Config
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


@patch("chowkidar.scanner.discover_repositories")
@patch("chowkidar.sentinel.service.is_service_installed")
@patch("chowkidar.sentinel.service.install_service")
def test_doctor_command_logic(mock_install, mock_is_installed, mock_discover, tmp_path):
    from chowkidar.cli import doctor_cmd, _get_config
    
    mock_discover.return_value = [tmp_path / "discovered_repo"]
    mock_is_installed.return_value = False
    mock_install.return_value = (True, "Mock service installed successfully")
    
    config_file = tmp_path / "config.toml"
    config = Config(config_file)
    
    with patch("chowkidar.cli.CHOWKIDAR_HOME", tmp_path), \
         patch("chowkidar.cli._get_config", return_value=config), \
         patch("chowkidar.registry.db.Registry") as mock_registry_class, \
         patch("typer.confirm", return_value=True):
         
        mock_registry = MagicMock()
        mock_registry.get_watched_projects.return_value = []
        mock_registry_class.return_value = mock_registry
        
        # Call doctor command in non-interactive mode (automatically registers and installs)
        doctor_cmd(non_interactive=True)
        
        # Verify repository discovery was triggered
        mock_discover.assert_called_once()
        
        # Verify watch_project was registered
        mock_registry.watch_project.assert_any_call(str(tmp_path / "discovered_repo"))
        
        # Verify service installation was triggered
        mock_install.assert_called_once()
        
        # Verify auto_discover_enabled was updated to True
        assert config.get("auto_discover_enabled") is True
