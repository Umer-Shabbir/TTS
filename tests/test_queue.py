import pytest
import sys
from unittest.mock import MagicMock
import time
import threading

# Mock TTSEngine before it gets imported by queue_manager
mock_tts_backend = MagicMock()
class MockTTSEngine:
    def synthesize(self, text, out_path, voice, speed, chunk_limit, cb):
        time.sleep(0.5)

mock_tts_backend.TTSEngine = MockTTSEngine
sys.modules['core.tts_backend'] = mock_tts_backend

from core.queue_manager import TTSJob, QueueManager

def mock_scheduler(fn):
    fn()

def test_job_creation():
    job = TTSJob(
        text="Hello World",
        voice="af_heart",
        output_path="/tmp/out.wav"
    )

    assert job.text == "Hello World"
    assert job.voice == "af_heart"
    assert job.status == "queued"
    assert job.char_count == 11
    assert job.preview == "Hello World"
    assert len(job.job_id) == 8

def test_queue_enqueue():
    # Use real thread for this, it will just process and complete
    qm = QueueManager(mock_scheduler)

    events = []
    qm.on("queued", lambda job: events.append("queued"))

    job = TTSJob(text="1", voice="af_heart", output_path="out.wav")
    qm.enqueue(job)

    # Wait for the thread to get it
    time.sleep(0.1)

    assert len(events) == 1

    jobs = qm.all_jobs()
    assert len(jobs) == 1

    # Let it finish and shutdown
    qm.shutdown()

def test_queue_cancel_queued():
    qm = QueueManager(mock_scheduler)

    events = []
    qm.on("cancelled", lambda jid: events.append(jid))

    # Enqueue a job that will take 0.5 sec
    job1 = TTSJob(text="1", voice="af", output_path="out1")
    qm.enqueue(job1)

    # Give it a tiny bit to get picked up
    time.sleep(0.1)

    # Queue another job
    job2 = TTSJob(text="2", voice="af", output_path="out2")
    qm.enqueue(job2)

    # Job2 is queued because worker is busy with job1
    assert job2.status == "queued"

    # Cancel it
    res = qm.cancel_queued(job2.job_id)
    assert res is True
    assert job2.status == "cancelled"

    qm.shutdown()

def test_retry():
    with pytest.MonkeyPatch().context() as m:
        # Mock thread here to test state changes without race conditions
        m.setattr(threading, "Thread", MagicMock())
        qm = QueueManager(mock_scheduler)

        # Attempt retry on missing job
        res = qm.retry("nonexistent")
        assert res is None

        job = TTSJob(text="3", voice="af", output_path="out")
        qm.enqueue(job)

        # Retry on queued job should fail
        res = qm.retry(job.job_id)
        assert res is None

        # Manually set to failed
        job.status = "failed"

        # Now it should work
        new_job = qm.retry(job.job_id)
        assert new_job is not None
        assert new_job.job_id != job.job_id
        assert new_job.text == job.text
        assert new_job.status == "queued"
