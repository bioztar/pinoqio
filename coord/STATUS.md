# STATUS: live board (each lane edits only its own block)

## copilot/ (Vitaly)
- 2026-10-24 13:40: keys validated (Gemini both keys: gemma-4-26b-a4b-it OK ~2.5s, gemma-4-31b-it timed out at 40s, so 26B is the default; ElevenLabs creator tier active). Scaffold + lane contract `copilot/pinoqio/events.py` merged.
- Next: 4 crewmates in parallel: ears (audio + Scribe + prosody + replay), brain (Gemma analyst + scorer), face (floating window UI + server + app wiring), voice+demo (ElevenLabs TTS, demo script, replay recordings).
- 2026-10-24 13:45 ears: audio/stt/prosody/replay/ears + tests (19 green) in PR; replay smoke OK with real Scribe. Live smoke needs BlackHole call. Next: review.
- 2026-10-24 13:45 face: server, UI (Pinocchio nose hero), window, fake source, app entry done, PR open. Next: wire live/replay once ears+brain merge. Blockers: none.
- Blockers: none.
- 2026-10-24 14:50 brand: logo favicon/apple-touch/og+twitter cover, web bar logo, macOS Dock icon, /static route in PR. Next: review.
- 2026-10-24 eval: 8 scripted negotiations + `copilot/scripts/run_eval.py` + `copilot/eval/report.md` (real run: 80% exact label, 25% false alarm on honest lines, Gemma 19/56 calls over 8 s budget or errored). PR open.
- 2026-10-24 web: demo LIVE at https://pinoqio.pro7ocol.com. Try live (passcode-gated /live ws, mic + tab audio) in PR; needs .env on VPS with keys + PINOQIO_LIVE_PASSCODE.
- 2026-10-24 13:45 voice+demo: voice.py (TTS + policy), demo/script.md, replay wavs (114 s), smoke_voice OK; PR open. Next: none, awaiting review.
- 2026-10-24 brain: config (PR #4) + Gemma analyst/scorer/brain.py done, smoke run OK (~5 s/call with thinking_level MINIMAL). Next: review/merge brain PR.

- 2026-10-24 nebius: fallback + verifier (DeepSeek-V4.1-Flash) + UI badge in PR #15, replay re-recorded, both planted contradictions verified 0.95. Stretch summary skipped.

- 2026-10-24 summary: post-call summary on Nebius (Summary button, auto at call end, in recorded web demo) in PR #17.

- 2026-10-24 doctor: `python -m pinoqio.doctor` stage preflight (10 s) + `app --demo-safe` pre-warm, PR open. Doctor shows Gemma 26B timing out at 10 s on this Mac right now.
- 2026-10-24 docs: root README (hero, mermaid, honest limits), DEVPOST.md, architecture.md in PR. Found: app.py voice hook imports a missing module-level `voice.on_verdict`, so the desktop app does not speak yet (documented as a known gap). README links `judge/README.md`, which the judge lane must add.
- 2026-10-24 video: `/demo/backup.mp4` route + web-bar link in PR; the mp4 is not recorded yet (Mac locked). Run `copilot/scripts/record_backup.sh` on an unlocked Mac to produce `copilot/demo/backup-demo.mp4`.
- 2026-10-24 15:15 qa: desktop replay, doctor, local /live all pass; fixed Say-it button (was silent on repeat), voice playback logging, quote punctuation in interjection, error messages in brain warnings. PR open. Note: run one replay at a time on stage, shared keys 429 under parallel load.

## judge/ (Partner)
- 2026-10-24 13:25: Plata task read (github.com/platacard/metalearning-llmaaj). Score = 10 × macro_topic_accuracy + 0.4 × I (jury, 5 binary points for the auto-generated explanation). Cost does not count. Submission: fork + Docker with `adapt`/`eval`. Private set has new hidden rules, so rules must be learned in `adapt`.
- Baseline (zero-shot Gemma 4 26B A4B, public test): macro_topic_accuracy 0.814; spending is weakest (0.61); misses bad cases (13 of 30 bad predicted good).
- Next: rule induction in `adapt` -> rulebook.json + explanation.md, rulebook-driven `eval`, Docker.
- Blockers: need to ask Plata whose API key/network the Docker run gets.
- 2026-10-24 14:30: `judge/pipeline.py` adapt/eval done (Plata Docker interface). Public test: **macro_topic_accuracy 0.814 → 0.894** (same in two runs), missed bad answers 13 → 6 of 30, false alarms 3 → 3 of 50. 21 learned rules, train self-check 143/150. `explanation.md` for the jury is rendered from the same `rulebook.json` the judge prompt uses. `judge/report.py` builds the stage page.
- Gemma 4 31B returns 500 for long stretches on the free tier; client falls back to 26B A4B.
- Next: Docker build check (no Docker on this laptop), stage page, mascot art (concepts in ~/Projects/pinoqio-art, not in repo yet).
- 2026-10-24 15:50: final run on the final code, public test: **macro_topic_accuracy 0.934** (credit 1.00, savings 1.00, financial_position 0.91, spending 0.83); bad answers missed 4/30, false alarms 2/50. Rate limiter (14 RPM, free tier ~15), key from GEMINI_API_KEY_JUDGE / GEMINI_API_KEY / GOOGLE_API_KEY, `prompts/<topic>.txt` and boundary conditions in the jury explanation, API-error fallback to nearest training labels. Docker image builds and runs (colima). Plata submission fork: github.com/balalaka128/metalearning-llmaaj. Stage deck: `judge/deck.py`. Mascot art: PR #40.
