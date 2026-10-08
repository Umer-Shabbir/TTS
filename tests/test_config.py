import pytest
from pathlib import Path
import json
import config.settings as settings

def test_config_load_defaults(tmp_path, monkeypatch):
    # Mock CONFIG_FILE and CONFIG_DIR to use tmp_path
    cfg_dir = tmp_path / "config"
    cfg_file = cfg_dir / "settings.json"
    
    monkeypatch.setattr(settings, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(settings, "CONFIG_FILE", cfg_file)
    
    cfg = settings.load()
    
    # Check if defaults are loaded when no file exists
    assert cfg["voice"] == settings.DEFAULT_VOICE
    assert cfg["speed"] == 1.0
    assert cfg["chunk_limit"] == settings.CHUNK_CHAR_LIMIT
    assert "output_dir" in cfg

def test_config_save_and_load(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_file = cfg_dir / "settings.json"
    
    monkeypatch.setattr(settings, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(settings, "CONFIG_FILE", cfg_file)
    
    new_cfg = settings.DEFAULTS.copy()
    new_cfg["speed"] = 1.5
    new_cfg["auto_open_output"] = True
    new_cfg["voice"] = "Heart  ·  American Female"
    
    # Save the custom config
    settings.save(new_cfg)
    
    # Check if file was created
    assert cfg_file.exists()
    
    # Load back the config
    loaded_cfg = settings.load()
    
    # Check if values match
    assert loaded_cfg["speed"] == 1.5
    assert loaded_cfg["auto_open_output"] is True
    assert loaded_cfg["voice"] == "Heart  ·  American Female"
    
def test_config_load_corrupted(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_file = cfg_dir / "settings.json"
    
    monkeypatch.setattr(settings, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(settings, "CONFIG_FILE", cfg_file)
    
    # Write corrupted JSON
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text("{ this is not valid json", encoding="utf-8")
    
    # Should safely load defaults without crashing
    cfg = settings.load()
    assert cfg["voice"] == settings.DEFAULT_VOICE
    assert cfg["speed"] == 1.0
