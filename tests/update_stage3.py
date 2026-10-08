import re
with open("H:/Automation/TTS/ui/app.py", "r", encoding="utf-8") as f:
    code = f.read()

new_code = re.sub(
r"""            # ── Output goes into the project folder per contract ──────────
            out  = str\(folder / "audio.wav"\)
            stem = folder.name

            job = TTSJob\(
                text=text,
                voice=voice,
                output_path=out,
                speed=speed,
                chunk_limit=self._cfg.get\("chunk_limit", CFG.CHUNK_CHAR_LIMIT\),
                source_name=stem,
                project_folder=str\(folder\) # pass folder to job
            \)
            self._qm.enqueue\(job\)""",
r"""            else:
                # If no project.json, skip checking stage constraints but still check for audio
                has_audio = (folder / "audio.wav").exists()
                if has_audio:
                    log.warn(f"Skipped {folder.name} — audio.wav already exists")
                    self._status(f"Skipped: {folder.name} (audio.wav exists)")
                    skipped += 1
                    continue

            # ── Output goes into the project folder per contract ──────────
            out  = str(folder / "audio.wav")
            stem = folder.name

            job = TTSJob(
                text=text,
                voice=voice,
                output_path=out,
                speed=speed,
                chunk_limit=self._cfg.get("chunk_limit", CFG.CHUNK_CHAR_LIMIT),
                source_name=stem,
                project_folder=str(folder) # pass folder to job
            )
            self._qm.enqueue(job)""",
code)

with open("H:/Automation/TTS/ui/app.py", "w", encoding="utf-8") as f:
    f.write(new_code)
