import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import core.model_manager as model_manager

def test_models_cached_false():
    with patch('core.model_manager.MODEL_FILE', Path('nonexistent1')), \
         patch('core.model_manager.VOICES_FILE', Path('nonexistent2')):
        assert model_manager.models_cached() is False

def test_ensure_piper_voice_downloaded_missing_cfg():
    success, model_path, config_path = model_manager.ensure_piper_voice_downloaded({})
    assert success is False

@patch('core.model_manager._download_file')
def test_ensure_piper_voice_downloaded_downloads(mock_download_file, tmp_path):
    # Setup mock to return True (success)
    mock_download_file.return_value = True
    
    cfg = {
        "id": "test_voice",
        "url_onnx": "http://test/voice.onnx",
        "url_json": "http://test/voice.onnx.json"
    }
    
    with patch('core.model_manager.MODEL_DIR', tmp_path):
        success, model_path, config_path = model_manager.ensure_piper_voice_downloaded(cfg)
        
        assert success is True
        assert model_path.name == "test_voice.onnx"
        assert config_path.name == "test_voice.onnx.json"
        
        # Should have called download twice (for json and onnx)
        assert mock_download_file.call_count == 2
