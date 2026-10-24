# STATUS: live board (each lane edits only its own block)

## copilot/ (Vitaly)
- 2026-10-24 13:40: keys validated (Gemini both keys: gemma-4-26b-a4b-it OK ~2.5s, gemma-4-31b-it timed out at 40s, so 26B is the default; ElevenLabs creator tier active). Scaffold + lane contract `copilot/pinoqio/events.py` merged.
- Next: 4 crewmates in parallel: ears (audio + Scribe + prosody + replay), brain (Gemma analyst + scorer), face (floating window UI + server + app wiring), voice+demo (ElevenLabs TTS, demo script, replay recordings).
- 2026-10-24 13:45 ears: audio/stt/prosody/replay/ears + tests (19 green) in PR; replay smoke OK with real Scribe. Live smoke needs BlackHole call. Next: review.
- 2026-10-24 13:45 face: server, UI (Pinocchio nose hero), window, fake source, app entry done, PR open. Next: wire live/replay once ears+brain merge. Blockers: none.
- Blockers: none.
- 2026-10-24 14:50 brand: logo favicon/apple-touch/og+twitter cover, web bar logo, macOS Dock icon, /static route in PR. Next: review.
- 2026-10-24 web: demo LIVE at https://pinoqio.pro7ocol.com. Try live (passcode-gated /live ws, mic + tab audio) in PR; needs .env on VPS with keys + PINOQIO_LIVE_PASSCODE.
- 2026-10-24 13:45 voice+demo: voice.py (TTS + policy), demo/script.md, replay wavs (114 s), smoke_voice OK; PR open. Next: none, awaiting review.
- 2026-10-24 brain: config (PR #4) + Gemma analyst/scorer/brain.py done, smoke run OK (~5 s/call with thinking_level MINIMAL). Next: review/merge brain PR.

- 2026-10-24 nebius: fallback + verifier (DeepSeek-V4.1-Flash) + UI badge in PR #15, replay re-recorded, both planted contradictions verified 0.95. Stretch summary skipped.

- 2026-10-24 summary: post-call summary on Nebius (Summary button, auto at call end, in recorded web demo) in PR #17.

- 2026-10-24 doctor: `python -m pinoqio.doctor` stage preflight (10 s) + `app --demo-safe` pre-warm, PR open. Doctor shows Gemma 26B timing out at 10 s on this Mac right now.
- 2026-10-24 docs: root README (hero, mermaid, honest limits), DEVPOST.md, architecture.md in PR. Found: app.py voice hook imports a missing module-level `voice.on_verdict`, so the desktop app does not speak yet (documented as a known gap). README links `judge/README.md`, which the judge lane must add.
- 2026-10-24 video: `/demo/backup.mp4` route + web-bar link in PR; the mp4 is not recorded yet (Mac locked). Run `copilot/scripts/record_backup.sh` on an unlocked Mac to produce `copilot/demo/backup-demo.mp4`.

## judge/ (Partner)
- (fill in)
