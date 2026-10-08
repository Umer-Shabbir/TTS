import json
import os
import tempfile
from pathlib import Path

meta = {
    "stage": "INITIAL", 
    "status": "PENDING"
}
with tempfile.TemporaryDirectory() as tmpdir:
    path = Path(tmpdir) / "project.json"
    path.write_text(json.dumps(meta))
    
    # how to update
    try:
        data = json.loads(path.read_text())
        print("old:", data)
        data["stage"] = "VOICED"
        path.write_text(json.dumps(data, indent=2))
        print("new:", path.read_text())
    except Exception as e:
        print(e)
