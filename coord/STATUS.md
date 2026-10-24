# STATUS: live board (each lane edits only its own block)

## copilot/ (Vitaly)
- 2026-10-24 13:40: keys validated (Gemini both keys: gemma-4-26b-a4b-it OK ~2.5s, gemma-4-31b-it timed out at 40s, so 26B is the default; ElevenLabs creator tier active). Scaffold + lane contract `copilot/pinoqio/events.py` merged.
- Next: 4 crewmates in parallel: ears (audio + Scribe + prosody + replay), brain (Gemma analyst + scorer), face (floating window UI + server + app wiring), voice+demo (ElevenLabs TTS, demo script, replay recordings).
- 2026-10-24 13:45 ears: audio/stt/prosody/replay/ears + tests (19 green) in PR; replay smoke OK with real Scribe. Live smoke needs BlackHole call. Next: review.
- 2026-10-24 13:45 face: server, UI (Pinocchio nose hero), window, fake source, app entry done, PR open. Next: wire live/replay once ears+brain merge. Blockers: none.
- Blockers: none.
- 2026-10-24 13:45 voice+demo: voice.py (TTS + policy), demo/script.md, replay wavs (114 s), smoke_voice OK; PR open. Next: none, awaiting review.

## judge/ (Partner)
- (fill in)
