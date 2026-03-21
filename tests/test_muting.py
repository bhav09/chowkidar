import pytest
from pathlib import Path
from chowkidar.registry.db import Registry
from chowkidar.scanner.env_parser import discover_system_env_files, _is_valid_env_file

def test_registry_muting(tmp_path: Path):
    registry = Registry(db_path=tmp_path / "test_registry.db")
    registry.init_db()

    project = str(tmp_path / "foo")
    
    # Not muted originally
    assert not registry.is_muted(project)
    
    # Mute
    registry.mute_project(project)
    assert registry.is_muted(project)
    
    # Unmute
    registry.unmute_project(project)
    assert not registry.is_muted(project)
    
    registry.close()

def test_valid_env_names():
    assert _is_valid_env_file(Path(".env"))
    assert _is_valid_env_file(Path(".env.local"))
    assert not _is_valid_env_file(Path(".env.bak"))
    assert not _is_valid_env_file(Path(".env.tmp"))
