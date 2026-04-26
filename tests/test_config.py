from kobo_cloud_sync import config


def test_save_settings_updates_runtime_and_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MARKDOWN_DIR=data/markdown\nKOBO_COUNTRY=us\n")
    monkeypatch.setattr(config, "ENV_FILE", env_file)

    settings = config.save_settings("HK", "EN")

    assert settings == {"KOBO_COUNTRY": "hk", "KOBO_LANGUAGE": "en"}
    assert config.KOBO_COUNTRY == "hk"
    assert config.KOBO_LANGUAGE == "en"
    assert "KOBO_COUNTRY=hk\n" in env_file.read_text()
    assert "KOBO_LANGUAGE=en\n" in env_file.read_text()
    assert "MARKDOWN_DIR=data/markdown\n" in env_file.read_text()
