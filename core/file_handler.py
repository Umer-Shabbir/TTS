"""core/file_handler.py – File I/O and output-path building."""
import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple


def read_text_file(path: str) -> str:
    """Read a plain-text file; falls back to latin-1 on UTF-8 decode errors."""
    p = Path(path)
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="latin-1")


def load_multiple_files(paths: List[str]) -> List[Tuple[str, str, str]]:
    """
    Read every path and return a list of (path, filename_stem, text) tuples.
    Files that fail to read are skipped; errors are returned as empty text with
    the error message embedded so the caller can decide what to do.
    """
    results = []
    for p in paths:
        try:
            text = read_text_file(p)
            results.append((p, Path(p).stem, text))
        except Exception as e:
            results.append((p, Path(p).stem, f"[ERROR reading file: {e}]"))
    return results


def build_output_path(output_dir: str, source_name: str = "tts",
                      template: str = "{name}_{ts}",
                      voice: str = "", speed: float = 1.0) -> str:
    """
    Build a unique WAV output path.
    Template variables: {name}, {ts}, {voice}, {speed}
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    safe_name  = re.sub(r"[^\w\-]", "_", Path(source_name).stem)[:40].strip("_") or "tts"
    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_voice = re.sub(r"[^\w]", "_", voice)[:20] if voice else ""
    safe_speed = str(speed).replace(".", "p")

    filename = template.format(name=safe_name, ts=ts,
                               voice=safe_voice, speed=safe_speed)
    filename = re.sub(r"_+", "_", filename).strip("_")[:80] or "tts"

    out_path = out / f"{filename}.wav"
    counter = 1
    while out_path.exists() or (out / f"{filename}_{counter}.wav").exists():
        out_path = out / f"{filename}_{counter}.wav"
        counter += 1
    return str(out_path)

import json

def scan_master_folder(master_dir: str) -> List[Path]:
    """
    Search immediate subdirectories of master_dir for valid project folders.
    Valid project folders must have a project.json with stage=INITIAL and status=PENDING
    and a script.txt file.
    """
    try:
        master_path = Path(master_dir)
        if not master_path.exists() or not master_path.is_dir():
            return []

        valid_folders = []
        for subdir in master_path.iterdir():
            if not subdir.is_dir():
                continue

            project_json = subdir / "project.json"
            if not project_json.exists():
                project_json = subdir / "metadata.json"
                
            script_txt = subdir / "script.txt"

            if not project_json.exists() or not script_txt.exists():
                continue

            try:
                data = json.loads(read_text_file(str(project_json)))
                if data.get("stage") == "INITIAL" and data.get("status") == "PENDING":
                    valid_folders.append(subdir)
            except Exception:
                continue

        return valid_folders
    except Exception:
        return []
