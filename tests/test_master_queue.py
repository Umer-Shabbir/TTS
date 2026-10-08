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

from core.queue_manager import QueueManager, TTSJob

def mock_scheduler(fn):
    fn()

def test_queue_updates_project_json(tmp_path):
    master_dir = tmp_path / "output"
    master_dir.mkdir()
    
    proj1 = master_dir / "proj1"
    proj1.mkdir()
    pjson = proj1 / "project.json"
    pjson.write_text(json.dumps({"stage": "INITIAL", "status": "PENDING"}), encoding="utf-8")
    
    qm = QueueManager(mock_scheduler)
    
    job = TTSJob(
        text="Hello",
        voice="af_heart",
        output_path=str(proj1 / "audio.wav"),
        project_folder=str(proj1)
    )
    
    qm.enqueue(job)
    
    import time
    time.sleep(1) # wait for worker
    
    assert job.status == "completed"
    
    # Read project check if updated
    with open(pjson, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert data["stage"] == "VOICED"
    assert data["status"] == "COMPLETED"

    qm.shutdown()
