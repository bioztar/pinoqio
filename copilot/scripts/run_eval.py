"""Eval: scripted negotiations (copilot/eval/scenarios/*.json) through the real analyst + verifier.

Text only, prosody empty. Writes copilot/eval/results.json and copilot/eval/report.md.
Run: PINOQIO_ENV_FILE=/path/to/.env uv run python scripts/run_eval.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pinoqio import nebius
from pinoqio.brain import verdicts
from pinoqio.events import Utterance, Verdict
from pinoqio.gemma import ask_json
from pinoqio.voice import INTERJECT_MIN_CONF

EVAL_DIR = ROOT / "eval"
LABELS = ("contradiction", "number_drift", "evasion", "honest")
GAP_S = 5.0  # synthetic seconds between lines


def predict(v: Verdict) -> str:
    """Strongest verbal finding wins; none -> honest."""
    kinds = {c.kind for c in v.chips}
    # a verifier-confirmed drift is upgraded to a Contradiction, so check the drift chip first
    if "number_drift" in kinds:
        return "number_drift"
    if v.contradiction:
        return "contradiction"
    return "evasion" if "evasion" in kinds else "honest"


def timed(name: str, ask, calls: list):
    async def wrapped(prompt, system=None):
        t0 = time.perf_counter()
        try:
            out = await ask(prompt, system)
        except BaseException:  # includes the 8 s wait_for cancel; failures are tallied, not averaged
            calls.append((name + "_fail", time.perf_counter() - t0))
            raise
        calls.append((name, time.perf_counter() - t0))
        return out
    return wrapped


async def run_scenario(sc: dict) -> list[dict]:
    calls: list[tuple[str, float]] = []
    lines = sc["lines"]

    async def feed():
        for i, ln in enumerate(lines, 1):
            yield Utterance(i, ln["speaker"], ln["text"], i * GAP_S, i * GAP_S + 3.0)

    rows = []
    async for item in verdicts(
        feed(),
        ask=timed("gemma", ask_json, calls),
        fallback=timed("nebius_fallback", nebius.ask_json, calls),
        verify_ask=timed("nebius_verify", nebius.ask_json, calls),
    ):
        if not isinstance(item, Verdict):
            continue
        ln = lines[item.utterance_id - 1]
        conf = item.contradiction.confidence if item.contradiction else 0.0
        rows.append({
            "scenario": sc["id"], "uid": item.utterance_id, "text": ln["text"], "truth": ln["label"],
            "pred": predict(item), "probability": item.probability, "contradiction_conf": conf,
            "interject": conf >= INTERJECT_MIN_CONF,
            "chips": [c.label for c in item.chips if c.kind != "model"],
            "models": [c.label for c in item.chips if c.kind == "model"],
            "calls": calls[:],
        })
        calls.clear()
    return rows


def prf(rows: list[dict], label: str) -> tuple[int, int, int, float, float]:
    tp = sum(r["truth"] == label and r["pred"] == label for r in rows)
    fp = sum(r["truth"] != label and r["pred"] == label for r in rows)
    fn = sum(r["truth"] == label and r["pred"] != label for r in rows)
    return tp, fp, fn, tp / (tp + fp) if tp + fp else 0.0, tp / (tp + fn) if tp + fn else 0.0


def mean_latency(rows: list[dict], name: str) -> tuple[float, int]:
    xs = [dt for r in rows for n, dt in r["calls"] if n == name]
    return (sum(xs) / len(xs) if xs else 0.0), len(xs)


def pct(x: float) -> str:
    return f"{x:.0%}"


def report(rows: list[dict]) -> str:
    out = [
        "# Pinoqio eval: honest numbers", "",
        f"{len(rows)} counterparty lines across 8 scripted negotiations "
        "(SaaS renewal, freelance rate, car purchase, rent, supplier, hiring offer, partnership, refund). "
        "Text only, prosody empty. Real pipeline: Gemma 4 analyst, Nebius verifier, Nebius fallback. "
        "Ground-truth label per line is in `eval/scenarios/*.json`; raw per-line results in `eval/results.json`.", "",
        "Prediction rule: contradiction if the verified `Verdict.contradiction` is set, else number_drift / evasion "
        "if that chip fired, else honest. Honest cases include restated numbers and corrections announced upfront.", "",
        "## Per-label precision / recall", "",
        "| Label | Lines | TP | FP | FN | Precision | Recall |", "|---|---|---|---|---|---|---|",
    ]
    for lab in LABELS:
        tp, fp, fn, p, r = prf(rows, lab)
        out.append(f"| {lab} | {tp + fn} | {tp} | {fp} | {fn} | {pct(p)} | {pct(r)} |")
    honest = [r for r in rows if r["truth"] == "honest"]
    false_alarms = [r for r in honest if r["pred"] != "honest"]
    lies = [r for r in rows if r["truth"] != "honest"]
    caught = [r for r in lies if r["pred"] != "honest"]
    exact = sum(r["truth"] == r["pred"] for r in rows)
    out += [
        "", "## Headline", "",
        f"- **False-alarm rate on honest lines:** {len(false_alarms)}/{len(honest)} = {pct(len(false_alarms) / len(honest))}",
        f"- **Any-flag recall on non-honest lines:** {len(caught)}/{len(lies)} = {pct(len(caught) / len(lies))}",
        f"- **Exact-label accuracy:** {exact}/{len(rows)} = {pct(exact / len(rows))}",
    ]
    fired = [r for r in rows if r["interject"]]
    good = [r for r in fired if r["truth"] == "contradiction"]
    out.append(
        f"- **Public interjection (verified contradiction conf >= {INTERJECT_MIN_CONF}):** would fire on "
        f"{len(fired)}/{len(rows)} lines ({len(good)} on real contradictions, {len(fired) - len(good)} on other lines). "
        "The live policy allows one interjection per call, so these are per-line triggers, not spoken interjections."
    )
    out += ["", "## Latency per call", "", "| Model / role | Calls | Mean latency |", "|---|---|---|"]
    for name, desc in (("gemma", "Gemma 4 analyst (every line)"), ("nebius_verify", "Nebius verifier (flagged lines)"),
                       ("nebius_fallback", "Nebius fallback analyst")):
        m, n = mean_latency(rows, name)
        nf = sum(n == name + "_fail" for r in rows for n, _ in r["calls"])
        out.append(f"| {desc} | {n} ok, {nf} failed | {m:.2f} s |" if n else f"| {desc} | 0 ok, {nf} failed | n/a |")
    tot = [sum(dt for _, dt in r["calls"]) for r in rows]
    out.append(f"\nLatency averages successful calls only; failures (error, or Gemma > 8 s budget) are counted separately and trigger the fallback / unverified cap. "
               f"Mean total model time per counterparty line: {sum(tot) / len(tot):.2f} s.")

    out += ["", "## Three example catches", ""]
    catches = sorted((r for r in rows if r["truth"] != "honest" and r["truth"] == r["pred"]),
                     key=lambda r: -r["probability"])
    seen, picks = set(), []
    for r in catches:  # one per label first, for variety
        if r["truth"] not in seen:
            seen.add(r["truth"])
            picks.append(r)
    picks = (picks + [r for r in catches if r not in picks])[:3]
    for r in picks:
        out += [f"- **{r['truth']}** ({r['scenario']}, line {r['uid']}, p={r['probability']:.0%}): \"{r['text']}\"",
                f"  - Evidence chips: {'; '.join(r['chips']) or '(none)'}"]
    if not picks:
        out.append("None: the system caught no non-honest line exactly.")

    out += ["", "## One honest failure", ""]
    fail = (sorted(false_alarms, key=lambda r: -r["probability"]) or
            sorted((r for r in lies if r["truth"] != r["pred"]), key=lambda r: r["probability"]))
    if fail:
        r = fail[0]
        kind = "False alarm on an honest line" if r["truth"] == "honest" else f"Missed {r['truth']}"
        out += [f"**{kind}** ({r['scenario']}, line {r['uid']}): \"{r['text']}\"", "",
                f"- Truth: {r['truth']}. Predicted: {r['pred']}. p={r['probability']:.0%}.",
                f"- Chips: {'; '.join(r['chips']) or '(none)'}"]
    else:
        out.append("No failures in this run.")
    out += ["", "## Caveats", "",
            f"- {len(rows)} hand-written lines, one run: small sample, wide error bars. Models are non-deterministic; rerun for variance.",
            "- Scripted lines are cleaner than real speech (no STT errors, no cross-talk). Expect real-call numbers to be worse.",
            "- Prosody is empty here, so this measures the verbal path only.", ""]
    return "\n".join(out)


async def main() -> None:
    scenarios = [json.loads(p.read_text()) for p in sorted((EVAL_DIR / "scenarios").glob("*.json"))]
    rows = [r for sc in scenarios for r in await run_scenario(sc)]  # sequential: clean latency numbers
    (EVAL_DIR / "results.json").write_text(json.dumps(rows, indent=2))
    (EVAL_DIR / "report.md").write_text(report(rows))
    print(f"{len(rows)} lines scored; wrote eval/report.md and eval/results.json")


if __name__ == "__main__":
    asyncio.run(main())
