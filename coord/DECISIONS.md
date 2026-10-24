# DECISIONS: append only

- 2026-10-23 · Vitaly · Project name **Kevin** (superseded below). Demo over Microsoft Teams. Apache-2.0 (superseded below). One repo, two lanes (copilot/, judge/), shared/ for common clients.
- 2026-10-23 · Vitaly · The judge lane uses a separate Google project and API key so the two lanes don't share Gemma quota.
- 2026-10-24 · Vitaly · Renamed Kevin → **Pinoqio** (deliberately not spelled "Pinocchio", and not "Pinokio", an existing AI app launcher). License changed Apache-2.0 → **MIT**. Repo renamed to bioztar/pinoqio.

## 2026-10-24 13:40 — copilot defaults (Vitaly)
- Default model `gemma-4-26b-a4b-it` for both lanes; `gemma-4-31b-it` timed out (40 s) on the free tier during key validation.
- Copilot keeps its own Gemma client (`copilot/pinoqio/gemma.py`, `GEMINI_API_KEY`), same pattern as `judge/gemma.py`. No `shared/` move before the freeze, so the judge lane is never disturbed.
- Copilot v1 scope: lie probability with evidence chips, promise ledger, "ask this next", floating desktop window, private whisper to the earpiece, one public interjection (auto at contradiction confidence >= 0.85, plus a manual button).
