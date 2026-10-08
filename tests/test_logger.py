import pytest
from core.logger import AppLogger
import threading

def test_logger_subscribe():
    logger = AppLogger()

    received = []

    def on_log(ts, level, msg):
        received.append((level, msg))

    logger.subscribe(on_log)

    logger.info("Test Info")
    logger.error("Test Error")

    assert len(received) == 2
    assert received[0] == ("INFO", "Test Info")
    assert received[1] == ("ERROR", "Test Error")

def test_logger_buffer_replay():
    logger = AppLogger()

    logger.info("Entry 1")
    logger.warn("Entry 2")

    received = []
    def on_log(ts, level, msg):
        received.append((level, msg))

    # Subscribe should immediately replay past logs
    logger.subscribe(on_log)

    assert len(received) == 2
    assert received[0] == ("INFO", "Entry 1")
    assert received[1] == ("WARN", "Entry 2")

def test_logger_level_methods():
    logger = AppLogger()
    logger.debug("Debug msg")
    logger.step("Step msg")

    logs = logger.all_entries()
    assert len(logs) == 2
    assert logs[0][1] == "DEBUG"
    assert logs[1][1] == "STEP"
