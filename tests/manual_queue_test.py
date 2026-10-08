import uuid
import sys
import os
from unittest.mock import MagicMock
sys.path.insert(0, os.path.abspath('H:/Automation/TTS'))

from core.queue_manager import TTSJob
print("Imported TTSJob")
job = TTSJob(
    text="Test",
    voice="en_us",
    output_path="out.wav",
    project_folder="my_folder"
)
print("Created TTSJob with project_folder =", job.project_folder)
print("status =", job.status)
