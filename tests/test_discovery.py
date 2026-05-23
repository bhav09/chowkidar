"""Tests for the repository discovery module."""

from pathlib import Path
from chowkidar.scanner.discovery import discover_repositories, DEFAULT_IGNORED_DIRS


def test_discover_repositories(tmp_path):
    # Setup mock folder structure
    # tmp_path
    #  ├── projects
    #  │    ├── repo1 (has .git)
    #  │    │    └── subfolder (should be pruned)
    #  │    ├── repo2 (has .git)
    #  │    ├── node_modules (should be ignored)
    #  │    │    └── nested_repo (has .git, should be skipped because of ignore list)
    #  │    └── deep_folder
    #  │         └── repo3 (has .git, at depth 2)
    #  └── other_dir
    
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    
    # repo1
    repo1 = projects_dir / "repo1"
    repo1.mkdir()
    (repo1 / ".git").mkdir()
    (repo1 / "subfolder").mkdir()
    (repo1 / "subfolder" / ".git").mkdir()  # should not be scanned because repo1 prunes
    
    # repo2
    repo2 = projects_dir / "repo2"
    repo2.mkdir()
    (repo2 / ".git").mkdir()
    
    # node_modules
    nm_dir = projects_dir / "node_modules"
    nm_dir.mkdir()
    (nm_dir / "nested_repo").mkdir()
    (nm_dir / "nested_repo" / ".git").mkdir()
    
    # deep folder repo3
    deep = projects_dir / "deep_folder"
    deep.mkdir()
    repo3 = deep / "repo3"
    repo3.mkdir()
    (repo3 / ".git").mkdir()
    
    # Run discovery starting from projects_dir (depth=2)
    discovered = discover_repositories([projects_dir], max_depth=2)
    
    # Convert discovered Paths to names for easier assert
    names = {p.name for p in discovered}
    
    assert "repo1" in names
    assert "repo2" in names
    assert "repo3" in names
    assert "subfolder" not in names  # Pruned
    assert "nested_repo" not in names  # Ignored via node_modules ignore rule
    assert len(discovered) == 3


def test_discover_repositories_depth_limit(tmp_path):
    # tmp_path
    #  └── d1
    #       └── d2
    #            └── repo_deep (has .git, depth=3 from tmp_path)
    
    d1 = tmp_path / "d1"
    d1.mkdir()
    d2 = d1 / "d2"
    d2.mkdir()
    
    repo_deep = d2 / "repo_deep"
    repo_deep.mkdir()
    (repo_deep / ".git").mkdir()
    
    # Search with max_depth=2 (too shallow)
    discovered_shallow = discover_repositories([tmp_path], max_depth=2)
    assert len(discovered_shallow) == 0
    
    # Search with max_depth=3 (enough depth)
    discovered_deep = discover_repositories([tmp_path], max_depth=3)
    assert len(discovered_deep) == 1
    assert discovered_deep[0].name == "repo_deep"
