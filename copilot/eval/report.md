# Pinoqio eval: honest numbers

56 counterparty lines across 8 scripted negotiations (SaaS renewal, freelance rate, car purchase, rent, supplier, hiring offer, partnership, refund). Text only, prosody empty. Real pipeline: Gemma 4 analyst, Nebius verifier, Nebius fallback. Ground-truth label per line is in `eval/scenarios/*.json`; raw per-line results in `eval/results.json`.

Prediction rule: contradiction if the verified `Verdict.contradiction` is set, else number_drift / evasion if that chip fired, else honest. Honest cases include restated numbers and corrections announced upfront.

## Per-label precision / recall

| Label | Lines | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|
| contradiction | 8 | 7 | 0 | 1 | 100% | 88% |
| number_drift | 8 | 7 | 7 | 1 | 50% | 88% |
| evasion | 8 | 7 | 1 | 1 | 88% | 88% |
| honest | 32 | 24 | 3 | 8 | 89% | 75% |

## Headline

- **False-alarm rate on honest lines:** 8/32 = 25%
- **Any-flag recall on non-honest lines:** 21/24 = 88%
- **Exact-label accuracy:** 45/56 = 80%
- **Public interjection (verified contradiction conf >= 0.85):** would fire on 13/56 lines (6 on real contradictions, 7 on other lines). The live policy allows one interjection per call, so these are per-line triggers, not spoken interjections.

## Latency per call

| Model / role | Calls | Mean latency |
|---|---|---|
| Gemma 4 analyst (every line) | 37 ok, 19 failed | 5.54 s |
| Nebius verifier (flagged lines) | 16 ok, 5 failed | 3.63 s |
| Nebius fallback analyst | 10 ok, 9 failed | 5.60 s |

Latency averages successful calls only; failures (error, or Gemma > 8 s budget) are counted separately and trigger the fallback / unverified cap. Mean total model time per counterparty line: 8.32 s.

## Three example catches

- **number_drift** (01_saas_renewal, line 11, p=95%): "Right, so for the two year term it is 58 thousand a year."
  - Evidence chips: Said "52 thousand a year", now "58 thousand a year"; Annual price: 52000 at 0:45, now 58000
- **contradiction** (04_rent, line 13, p=92%): "Utilities are included in the rent, that is how it has always been."
  - Evidence chips: Said "utilities not included", now "Utilities are included in the rent"; Hedging: that is how it has always been
- **evasion** (07_partnership, line 5, p=62%): "Look, the market is moving so fast, everybody is asking about this category, it's really exciting times."
  - Evidence chips: ME asked how many accounts have actually bought a similar product; THEM pivots to market excitement and gives no number.; Hedging: Look, so fast, everybody, really exciting times

## One honest failure

**False alarm on an honest line** (05_supplier, line 7): "Net 30 from delivery. One note: I said March, but customs means it is realistically the first week of April, sorry for not flagging it sooner."

- Truth: honest. Predicted: number_drift. p=95%.
- Chips: Said "For the 500 units our price is 40 thousand euros, delivered in March.", now "One note: I said March, but customs means it is realistically the first week of April, sorry for not flagging it sooner."; Delivery date: March at 0:05, now first week of April; Hedging: realistically

## Caveats

- 56 hand-written lines, one run: small sample, wide error bars. Models are non-deterministic; rerun for variance.
- Scripted lines are cleaner than real speech (no STT errors, no cross-talk). Expect real-call numbers to be worse.
- Prosody is empty here, so this measures the verbal path only.
