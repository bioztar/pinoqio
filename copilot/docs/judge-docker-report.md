# Judge Docker test report (judge/pipeline, PR #18)

Run on vps2, 2026-10-24, image built from `judge/Dockerfile`, Plata inputs from `src/prepare_inputs.py` (public train/test).

## Result
| Step | Outcome |
|---|---|
| Build | OK, 265 MB |
| `adapt` (150 train) | OK, exit 0, 31m52s. Artifacts: `violations.jsonl`, `rulebook.json`, `explanation.md` |
| `eval` (20-item subset, every 4th test item) | OK, 3m40s, valid `item_id,label` CSV |
| Plata `evaluate.py` on those 20 | macro_topic_accuracy **0.750** (acc 0.75; credit 1.0 n=4, financial_position 0.6 n=5, savings 1.0 n=6, spending 0.4 n=5; confusion [[11,2],[3,4]]) |
| Full 80 eval | Not run: extrapolates to about 15 min, over the 5 min threshold. |

0.75 on 20 items vs the reported 0.894 on 80: per-topic n is 4-6, so this is not significant evidence of a gap. It does not confirm 0.894 either. A full 80 run (about 15 min, one key) would settle it.

## Contract check
- Commands, mount paths (`/input`, `/artifacts`, `/output`), output name and columns: match Plata's README.
- Plata names no API-key variable. `GEMINI_API_KEY_JUDGE` is our choice, so the organizers must be told to pass it (document in `judge/README.md`).
- Without the key the image dies at import: `KeyError: 'GEMINI_API_KEY_JUDGE'` (`gemma.py:14`).
- Network is required at run time (Gemini API). Fine if the organizers allow it; confirm.
- Runtime: private set is 190 train / 296 test. At the measured rate, adapt is about 40 min and eval about 55 min with `JUDGE_WORKERS=6`. Ask the organizers for time limits; raise `JUDGE_WORKERS` if quota allows.
- Misleading log: `self-check: 149/150 agree` checks only a 48-item sample (12 per topic) but divides by `len(train)`.

## Suggested patches (not applied; `judge/` is not our lane)

```diff
--- a/judge/gemma.py
+++ b/judge/gemma.py
@@
-_client = genai.Client(api_key=os.environ["GEMINI_API_KEY_JUDGE"])
+_KEY = os.environ.get("GEMINI_API_KEY_JUDGE")
+if not _KEY:
+    raise SystemExit("GEMINI_API_KEY_JUDGE is not set. Pass it with: docker run -e GEMINI_API_KEY_JUDGE ...")
+_client = genai.Client(api_key=_KEY)
```

```diff
--- a/judge/pipeline.py
+++ b/judge/pipeline.py
@@ in adapt(), self-check summary
-    rulebook["self_check"] = {"train_size": len(sample), "agree": len(sample) - len(misses), ...
+    (same, already uses len(sample))
-    print(f"self-check: {len(train) - len(misses)}/{len(train)} agree with the expert", file=sys.stderr)
+    print(f"self-check: {len(sample) - len(misses)}/{len(sample)} agree with the expert", file=sys.stderr)
```

## Cleanup
Test image and `/tmp/judge-test` removed from vps2. No other containers touched. No `judge/` change or push.
