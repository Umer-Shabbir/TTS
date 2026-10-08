import pytest
import os
from pathlib import Path
from config.settings import load, save, DEFAULTS

def test_load_defaults(tmp_path, monkeypatch):
    # Map CONFIG_DIR to tmp_path
    monkeypatch.setattr("config.settings.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("config.settings.CONFIG_FILE", tmp_path / "settings.json")

    cfg = load()
    # It should return default settings when config file missing
    assert cfg["voice"] == DEFAULTS["voice"]
    assert cfg["speed"] == DEFAULTS["speed"]

def test_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("config.settings.CONFIG_FILE", tmp_path / "settings.json")

    cfg = load()
    cfg["voice"] = "Custom Voice"
    cfg["speed"] = 1.5

    save(cfg)

    assert (tmp_path / "settings.json").exists()

    cfg_loaded = load()
    assert cfg_loaded["voice"] == "Custom Voice"
    assert cfg_loaded["speed"] == 1.5
