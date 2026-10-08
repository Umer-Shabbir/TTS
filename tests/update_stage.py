import re
with open("H:/Automation/TTS/ui/app.py", "r", encoding="utf-8") as f:
    code = f.read()

new_code = re.sub(
r"""            meta_path = folder / "metadata.json"
            if meta_path.exists\(\):
                try:
                    import json
                    meta = json.loads\(read_text_file\(str\(meta_path\)\)\)
                    # TTS explicitly reads ONLY 'voice_name' from metadata per contract.
                    # It DOES NOT interpret 'preset_name'.
                    voice_name = meta.get\("voice_name", ""\).strip\(\)

                    if voice_name and voice_name in VOICE_CATALOGUE:
                        voice = voice_name
                except Exception as e:
                    log.error\(f"Failed to read metadata.json for voice selection: \{e\}"\)""",
r"""            meta_path = folder / "project.json"
            if not meta_path.exists():
                meta_path = folder / "metadata.json" # Fallback to old name

            if meta_path.exists():
                try:
                    import json
                    meta = json.loads(read_text_file(str(meta_path)))
                    
                    # Contract check: Only queue if audio is missing and script is ready
                    has_audio = (folder / "audio.wav").exists()
                    # We check the queue status but if audio doesn't exist we queue anyway because the task requires TTS
                    # If project.json says it's past TTS (e.g. IMAGES_READY, VOICED, RENDERED) we might skip, but checking audio is safer
                    stage = meta.get("stage", "")
                    status = meta.get("status", "")
                    
                    if has_audio:
                        log.warn(f"Skipped {folder.name} — audio.wav already exists")
                        self._status(f"Skipped: {folder.name} (audio.wav exists)")
                        skipped += 1
                        continue
                        
                    if stage and stage not in ("INITIAL", "INITIAL"):
                        # In later stages but audio is missing? Maybe it was deleted. We'll proceed.
                        pass
                        
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
