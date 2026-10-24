# STATUS: live board (each lane edits only its own block)

## copilot/ (Vitaly)
- 2026-10-23 23:59: repo created, no code yet (event rule: work starts 11:30).
- Next: 11:30 audio capture (BlackHole) + Scribe streaming + Gemma claim ledger.
- Blockers: none.

## judge/ (Partner)
- 2026-10-24 13:25: Plata task read (github.com/platacard/metalearning-llmaaj). Score = 10 × macro_topic_accuracy + 0.4 × I (jury, 5 binary points for the auto-generated explanation). Cost does not count. Submission: fork + Docker with `adapt`/`eval`. Private set has new hidden rules, so rules must be learned in `adapt`.
- Baseline (zero-shot Gemma 4 26B A4B, public test): macro_topic_accuracy 0.814; spending is weakest (0.61); misses bad cases (13 of 30 bad predicted good).
- Next: rule induction in `adapt` -> rulebook.json + explanation.md, rulebook-driven `eval`, Docker.
- Blockers: need to ask Plata whose API key/network the Docker run gets.
- 2026-10-24 14:30: `judge/pipeline.py` adapt/eval done (Plata Docker interface). Public test: **macro_topic_accuracy 0.814 → 0.894** (same in two runs), missed bad answers 13 → 6 of 30, false alarms 3 → 3 of 50. 21 learned rules, train self-check 143/150. `explanation.md` for the jury is rendered from the same `rulebook.json` the judge prompt uses. `judge/report.py` builds the stage page.
- Gemma 4 31B returns 500 for long stretches on the free tier; client falls back to 26B A4B.
- Next: Docker build check (no Docker on this laptop), stage page, mascot art (concepts in ~/Projects/pinoqio-art, not in repo yet).
- 2026-10-24 15:50: final run on the final code, public test: **macro_topic_accuracy 0.934** (credit 1.00, savings 1.00, financial_position 0.91, spending 0.83); bad answers missed 4/30, false alarms 2/50. Rate limiter (14 RPM, free tier ~15), key from GEMINI_API_KEY_JUDGE / GEMINI_API_KEY / GOOGLE_API_KEY, `prompts/<topic>.txt` and boundary conditions in the jury explanation, API-error fallback to nearest training labels. Docker image builds and runs (colima). Plata submission fork: github.com/balalaka128/metalearning-llmaaj. Stage deck: `judge/deck.py`. Mascot art: PR #40.
