import pytest
from pathlib import Path
from core.file_handler import read_text_file, load_multiple_files, build_output_path
from datetime import datetime
import re

def test_read_text_file(tmp_path):
    p = tmp_path / "test.txt"
    p.write_text("Hello World", encoding="utf-8")
    
    content = read_text_file(str(p))
    assert content == "Hello World"
    
def test_read_text_file_latin1(tmp_path):
    p = tmp_path / "test_latin.txt"
    p.write_bytes(b"Hello \xff World") # Invalid UTF-8, valid latin-1
    
    content = read_text_file(str(p))
    assert content == "Hello \xff World"

def test_load_multiple_files(tmp_path):
    p1 = tmp_path / "f1.txt"
    p1.write_text("content 1", encoding="utf-8")
    
    p2 = tmp_path / "f2.txt"
    p2.write_text("content 2", encoding="utf-8")
    
    p3_missing = tmp_path / "f3.txt"
    
    results = load_multiple_files([str(p1), str(p2), str(p3_missing)])
    
    assert len(results) == 3
    assert results[0] == (str(p1), "f1", "content 1")
    assert results[1] == (str(p2), "f2", "content 2")
    assert results[2][0] == str(p3_missing)
    assert results[2][1] == "f3"
    assert "[ERROR reading file:" in results[2][2]

def test_build_output_path(tmp_path):
    out_dir = str(tmp_path / "output")
    
    path1 = build_output_path(out_dir, "test_file.txt", "{name}_{ts}", "Heart", 1.0)
    assert path1.endswith(".wav")
    assert "test_file" in path1
    assert "output" in path1
    assert "Heart" not in path1 # Voice not in template
    
    path2 = build_output_path(out_dir, "test_file.txt", "{name}_{voice}_{speed}", "Heart", 1.5)
    assert path2.endswith(".wav")
    assert "test_file" in path2
    assert "Heart" in path2
    assert "1p5" in path2
    
def test_build_output_path_dedup(tmp_path):
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Create the file that would normally be generated
    base_name = "test_file" # We can't predict ts, but let's mock the template to be stable
    
    path1 = build_output_path(str(out_dir), "test_file.txt", "{name}", "Heart", 1.0)
    assert Path(path1).name == "test_file.wav"
    
    # Touch this file to simulate it already exists
    Path(path1).write_text("dummy")
    
    # Should get _1
    path2 = build_output_path(str(out_dir), "test_file.txt", "{name}", "Heart", 1.0)
    assert Path(path2).name == "test_file_1.wav"
    Path(path2).write_text("dummy")
    
    # Should get _2
    path3 = build_output_path(str(out_dir), "test_file.txt", "{name}", "Heart", 1.0)
    assert Path(path3).name == "test_file_2.wav"
