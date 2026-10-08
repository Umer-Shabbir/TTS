import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import json

mock_tts_backend = MagicMock()
class MockTTSEngine:
    def synthesize(self, text, out_path, voice, speed, chunk_limit, cb):
        import time
        time.sleep(0.1)

mock_tts_backend.TTSEngine = MockTTSEngine
sys.modules['core.tts_backend'] = mock_tts_backend

import core.file_handler as fh

def test_master_scan(tmp_path):
    # Setup master folder structure
    master_dir = tmp_path / "output"
    master_dir.mkdir()
    
    # Valid folder 1
    proj1 = master_dir / "proj1"
    proj1.mkdir()
    (proj1 / "script.txt").write_text("Hello")
    (proj1 / "project.json").write_text(json.dumps({"stage": "INITIAL", "status": "PENDING"}))
    
    # Invalid folder (wrong stage)
    proj2 = master_dir / "proj2"
    proj2.mkdir()
    (proj2 / "script.txt").write_text("Hello")
    (proj2 / "project.json").write_text(json.dumps({"stage": "VOICED", "status": "COMPLETED"}))
    
    # Invalid folder (missing script)
    proj3 = master_dir / "proj3"
    proj3.mkdir()
    (proj3 / "project.json").write_text(json.dumps({"stage": "INITIAL", "status": "PENDING"}))
    
    valid_folders = fh.scan_master_folder(str(master_dir))
    assert len(valid_folders) == 1
    assert valid_folders[0] == proj1
