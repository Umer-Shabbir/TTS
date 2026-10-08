import pytest
from pathlib import Path
from core.file_handler import read_text_file, build_output_path

def test_read_text_file(tmp_path):
    text_file = tmp_path / "test.txt"
    text_file.write_text("Hello TTS", encoding="utf-8")

    content = read_text_file(str(text_file))
    assert content == "Hello TTS"

def test_build_output_path(tmp_path):
    out_path = build_output_path(str(tmp_path), "test_doc.txt", "{name}_{voice}", "Heart", 1.0)

    assert str(tmp_path) in out_path
    assert out_path.endswith(".wav")
    assert "test_doc" in out_path
    assert "Heart" in out_path

def test_build_output_path_deduplication(tmp_path):
    # Test file path generation when a file already exists
    out_path1 = build_output_path(str(tmp_path), "doc.txt", "{name}", "Heart", 1.0)

    # Touch the file
    Path(out_path1).write_text("dummy")

    # Next call should add _1
    out_path2 = build_output_path(str(tmp_path), "doc.txt", "{name}", "Heart", 1.0)
    assert out_path2 != out_path1
    assert out_path2.endswith("_1.wav")
