# HANDOVER — pinoqio — 2026-10-24 16:12
## State: copilot + judge lanes merged on main (116 tests), web live at https://pinoqio.pro7ocol.com; MLH submission pending (DevRelay installed, needs Claude Code restart).
## Done this session
- Copilot: ears (Scribe Realtime), brain (Gemma 4 analyst + Nebius DeepSeek verifier/fallback/summary, hedged race), face (floating window, image nose with BOING animation, claim check card, --art cartoon|scene), voice modes (--voice public|whisper|private), doctor preflight, eval report, pitch deck, architecture build slide, web demo + Try live (passcode in server .env).
- Partner judge lane: 0.934 on Plata public test (PR #18, partner merges); Docker tested on VPS, findings on PR #18.
## In flight
- MLH submission: content ready in copilot/docs/SUBMISSION.md. After restart, run the DevRelay prompt (devrelay-mlh-submissions skill), deadline 18:00 CEST.
- Backup video: copilot/scripts/record_backup.sh (needs unlocked Mac, ~3 min).
## Next steps
1. Restart Claude Code, paste the DevRelay prompt, submit + enter 4 categories.
2. Live Teams test with partner (scenario A in chat): `cd copilot && uv run python -m pinoqio.doctor`, then `uv run python -m pinoqio.app --source live --voice public --demo-safe [--art scene]`.
3. Demo 16:45.
## Blockers / needs human
- Gemma free tier + Nebius gateway were flaky 15:00-15:45 (timeouts, 503 bursts): if doctor shows red, demo the replay.
## Key files
- copilot/docs/SUBMISSION.md — MLH form answers
- copilot/docs/pitch.html, architecture-slide.html — stage
- copilot/eval/report.md — honest numbers
