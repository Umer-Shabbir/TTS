import re
with open("H:/Automation/TTS/ui/app.py", "r", encoding="utf-8") as f:
    code = f.read()

new_code = re.sub(
r"""            meta_path = folder / "project.json"
            if meta_path.exists\(\):
                try:
                    with open\(meta_path, 'r', encoding='utf-8'\) as f:
                        meta = json.load\(f\)
                    if meta.get\('stage'\) != 'INITIAL' or meta.get\('status'\) != 'PENDING':
                        log.warn\(f"Skipped \{folder.name\} — not in INITIAL/PENDING state"\)
                        self._status\(f"Skipped: \{folder.name\} \(not INITIAL/PENDING\)"\)
                        skipped \+= 1
                        continue
                try:
                    # TTS explicitly reads ONLY 'voice_name' from metadata per contract.
                    # It DOES NOT interpret 'preset_name'.
                    voice_name = meta.get\("voice_name", ""\).strip\(\)

                    if voice_name and voice_name in VOICE_CATALOGUE:
                        voice = voice_name
                except Exception as e:
                    log.error\(f"Failed to read project.json for voice selection: \{e\}"\)""",
r"""            meta_path = folder / "project.json"
            if not meta_path.exists():
                meta_path = folder / "metadata.json" # Fallback to old name

            if meta_path.exists():
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                        
                    # Contract check: Only queue if audio is missing and script is ready
                    has_audio = (folder / "audio.wav").exists()
                    
                    if has_audio:
                        log.warn(f"Skipped {folder.name} — audio.wav already exists")
                        self._status(f"Skipped: {folder.name} (audio.wav exists)")
                        skipped += 1
                        continue
                        
                    # If project.json states we aren't waiting for a script to be voiced, we can skip too
                    stage = meta.get('stage')
                    status = meta.get('status')
                    
                    if stage and stage != 'INITIAL':
                        log.warn(f"Skipped {folder.name} — not in INITIAL state (is {stage})")
                        self._status(f"Skipped: {folder.name} (wrong stage: {stage})")
                        skipped += 1
                        continue

                    # TTS explicitly reads ONLY 'voice_name' from metadata per contract.
                    # It DOES NOT interpret 'preset_name'.
                    voice_name = meta.get("voice_name", "").strip()

                    if voice_name and voice_name in VOICE_CATALOGUE:
                        voice = voice_name
                except Exception as e:
                    log.error(f"Failed to read {meta_path.name} for voice selection: {e}")""",
code)

with open("H:/Automation/TTS/ui/app.py", "w", encoding="utf-8") as f:
    f.write(new_code)
