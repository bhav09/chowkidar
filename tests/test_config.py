"""Tests for the config module."""


from chowkidar.config import Config


class TestConfig:
    def test_defaults(self, tmp_path):
        config = Config(tmp_path / "config.toml")
        assert config.get("auto_update") is False
        assert config.get("write_rules") is True
        assert config.get("slm_model") == "gemma3:1b"

    def test_set_and_get(self, tmp_path):
        config = Config(tmp_path / "config.toml")
        config.set("auto_update", True)
        assert config.get("auto_update") is True

    def test_save_and_load(self, tmp_path):
        config_path = tmp_path / "config.toml"
        config = Config(config_path)
        config.set("auto_update", True)
        config.set("slm_model", "qwen2.5:0.5b")
        config.save()

        config2 = Config(config_path)
        assert config2.get("auto_update") is True
        assert config2.get("slm_model") == "qwen2.5:0.5b"

    def test_type_coercion(self, tmp_path):
        config = Config(tmp_path / "config.toml")
        config.set("auto_update", "true")
        assert config.get("auto_update") is True

        config.set("scan_interval_hours", "6")
        assert config.get("scan_interval_hours") == 6

    def test_as_dict(self, tmp_path):
        config = Config(tmp_path / "config.toml")
        d = config.as_dict()
        assert isinstance(d, dict)
        assert "auto_update" in d
