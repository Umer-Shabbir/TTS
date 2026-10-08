import re
with open("H:/Automation/TTS/ui/app.py", "r", encoding="utf-8") as f:
    code = f.read()

new_code = re.sub(
r"""    def _load_project_folders_dialog\(self\):
        \"\"\"Open the universal multi-folder selector and queue every valid project folder\.\"\"\"
        initial = Path\(self\._cfg\.get\("output_dir", str\(Path\.home\(\)\)\)\)
        folders = ask_folders\(
            parent=self\.winfo_toplevel\(\),
            title="Select Project Folders",
            initial_dir=initial,
        \)
        if not folders:
            return

        import json

        count   = 0
        skipped = 0
        for folder in folders:""",
r"""    def _load_project_folders_dialog(self):
        \"\"\"Open the universal multi-folder selector and queue every valid project folder.\"\"\"
        initial = Path(self._cfg.get("output_dir", str(Path.home())))
        folders = ask_folders(
            parent=self.winfo_toplevel(),
            title="Select Project Folders",
            initial_dir=initial,
        )
        if not folders:
            return

        import json
        self._scan_and_queue_folders(folders)
        
    def _scan_and_queue_folders(self, paths: list[Path]):
        count   = 0
        skipped = 0
        
        # Expand master folders: if a folder contains project.json or metadata.json directly, it's a project.
        # Otherwise, treat it as a master folder and scan its immediate subdirectories.
        expanded_folders = []
        for p in paths:
            if (p / "project.json").exists() or (p / "metadata.json").exists() or (p / "script.txt").exists():
                if p not in expanded_folders:
                    expanded_folders.append(p)
            else:
                # Master directory case: scan subdirs
                log.info(f"Scanning master folder: {p}")
                for sub in p.iterdir():
                    if sub.is_dir() and ((sub / "project.json").exists() or (sub / "metadata.json").exists() or (sub / "script.txt").exists()):
                        if sub not in expanded_folders:
                            expanded_folders.append(sub)

        for folder in expanded_folders:""",
code)

with open("H:/Automation/TTS/ui/app.py", "w", encoding="utf-8") as f:
    f.write(new_code)
