"""core/queue_manager.py – Job queue with pause/resume/retry, fully logged."""
import queue, threading, uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional
from core.tts_backend import TTSEngine
from core.logger import log


@dataclass
class TTSJob:
    text:        str
    voice:       str
    output_path: str
    speed:       float = 1.0
    chunk_limit: int   = 250
    source_name: str   = "text_input"

    job_id:      str      = field(default_factory=lambda: uuid.uuid4().hex[:8].upper())
    status:      str      = "queued"
    error:       str      = ""
    progress:    str      = ""

    created_at:  datetime = field(default_factory=datetime.now)
    started_at:  Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def preview(self) -> str:
        flat = self.text.replace("\n", " ").strip()
        return flat[:75] + "…" if len(flat) > 75 else flat

    @property
    def duration_str(self) -> str:
        if self.started_at and self.finished_at:
            s = (self.finished_at - self.started_at).total_seconds()
            return f"{s:.1f}s" if s < 60 else f"{int(s//60)}m {int(s%60)}s"
        return ""

    @property
    def char_count(self) -> int:
        return len(self.text)


class QueueManager:
    def __init__(self, schedule_fn: Callable):
        self._sched    = schedule_fn
        self._q:       queue.Queue = queue.Queue()
        self._jobs:    Dict[str, TTSJob] = {}
        self._handlers = defaultdict(list)
        self._engine   = TTSEngine()
        self._stop     = threading.Event()
        self._resume   = threading.Event()
        self._resume.set()
        self._pausing  = False
        log.step("QueueManager initialised — worker thread starting")
        threading.Thread(target=self._worker, name="tts-worker", daemon=True).start()

    def on(self, event: str, cb: Callable): self._handlers[event].append(cb)

    def enqueue(self, job: TTSJob):
        self._jobs[job.job_id] = job
        self._q.put(job.job_id)
        log.info(f"Job {job.job_id} queued — voice='{job.voice}' "
                 f"source='{job.source_name}' chars={job.char_count}")
        self._emit("queued", job)

    def pause(self):
        if self._resume.is_set():
            self._pausing = True
            self._resume.clear()
            log.info("Queue pause requested — will pause after current job")
            self._emit("pausing")

    def resume(self):
        if not self._resume.is_set():
            self._pausing = False
            self._resume.set()
            log.info("Queue resumed")
            self._emit("resumed")

    def is_paused(self)  -> bool: return not self._resume.is_set()
    def is_pausing(self) -> bool: return self._pausing

    def retry(self, job_id: str) -> Optional[TTSJob]:
        old = self._jobs.get(job_id)
        if not old or old.status != "failed":
            log.warn(f"Retry requested for job {job_id} but status is "
                     f"'{old.status if old else 'not found'}'")
            return None
        new = TTSJob(text=old.text, voice=old.voice, output_path=old.output_path,
                     speed=old.speed, chunk_limit=old.chunk_limit,
                     source_name=old.source_name)
        log.info(f"Retrying job {job_id} as new job {new.job_id}")
        self.enqueue(new)
        return new

    def cancel_queued(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.status == "queued":
            job.status = "cancelled"
            log.info(f"Job {job_id} cancelled")
            self._emit("cancelled", job_id)
            return True
        return False

    def all_jobs(self) -> List[TTSJob]: return list(self._jobs.values())

    def pending_count(self) -> int:
        return sum(1 for j in self._jobs.values()
                   if j.status in ("queued", "processing"))

    def shutdown(self):
        log.info("QueueManager shutdown requested")
        self._stop.set()
        self._resume.set()

    def _worker(self):
        log.debug("Worker thread started")
        while not self._stop.is_set():
            try: jid = self._q.get(timeout=0.5)
            except queue.Empty: continue

            job = self._jobs.get(jid)
            if not job or job.status == "cancelled":
                log.debug(f"Skipping job {jid} (cancelled or not found)")
                self._q.task_done(); continue

            job.status = "processing"; job.started_at = datetime.now()
            log.step(f"Job {jid} started — '{job.source_name}'")
            self._emit("started", jid)

            try:
                self._engine.synthesize(
                    text=job.text, out_path=job.output_path,
                    voice=job.voice, speed=job.speed,
                    chunk_limit=job.chunk_limit,
                    cb=lambda m, j=jid: self._emit("progress", j, m),
                )
                job.status = "completed"; job.finished_at = datetime.now()
                log.step(f"Job {jid} COMPLETED in {job.duration_str} "
                         f"→ {job.output_path}")
                self._emit("completed", jid, job.output_path)

            except Exception as exc:
                job.status = "failed"; job.error = str(exc)
                job.finished_at = datetime.now()
                log.error(f"Job {jid} FAILED: {exc}")
                self._emit("failed", jid, str(exc))

            finally:
                self._q.task_done()

            # Pause check — AFTER job finishes
            if not self._resume.is_set():
                self._pausing = False
                log.info(f"Queue paused after job {jid}")
                self._emit("paused")
                self._resume.wait()
                if not self._stop.is_set():
                    log.info("Worker wait unblocked (queue resumed)")
                    # DO NOT double-emit "resumed" here. Parent `resume()` already emitted it.

            if self._q.empty():
                log.info("Queue exhausted — all jobs done")
                self._emit("exhausted")

        log.debug("Worker thread exited")

    def _emit(self, ev: str, *args):
        for cb in self._handlers[ev]:
            _cb, _a = cb, args
            self._sched(lambda _cb=_cb, _a=_a: _cb(*_a))
