"""Baseline: zero-shot Gemma judge, no learned rules. Usage: python baseline.py [model] [language]"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

import gemma

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "plata" / "data"

SYSTEM = (
    "You evaluate replies of a bank's personal finance assistant. You get the customer's data (context) "
    "and the conversation. Evaluate the entire conversation. Label it 'bad' if the assistant breaks any "
    "applicable rule of a careful financial expert: wrong numbers or calculations against the context, "
    "unsupported claims, misleading advice, ignoring the question. Otherwise label it 'good'. "
    'Answer with JSON only: {"reason": "<one sentence>", "label": "good" | "bad"}'
)


def item_text(row, language: str | None) -> str:
    if language:
        return row[f"input_{language}"]
    return json.dumps({"context": json.loads(row.context), "conversation": json.loads(row.conversation)}, ensure_ascii=False)


def parse_label(text: str) -> str:
    m = re.search(r'"label"\s*:\s*"(good|bad)"', text)
    if m:
        return m.group(1)
    return "bad" if "bad" in text.lower() else "good"


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else gemma.FAST
    language = sys.argv[2] if len(sys.argv) > 2 else None
    test = pd.read_csv(DATA / "public_test.csv")

    def judge(row):
        try:
            r = gemma.ask(f"Topic: {row.topic}\n\n{item_text(row, language)}", model=model, system=SYSTEM)
        except Exception as e:  # one failed item must not kill the run; fall back to the majority class
            print(f"{row.item_id}: {type(e).__name__} {str(e)[:80]}", file=sys.stderr)
            r = {"text": '{"label": "good"}', "in_tokens": 0, "out_tokens": 0, "seconds": 0}
        return {"item_id": row.item_id, "label": parse_label(r["text"]), "raw": r["text"], **{k: r[k] for k in ("in_tokens", "out_tokens", "seconds")}}

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(judge, [row for row in test.itertuples()]))

    out = ROOT / "runs" / f"baseline_{model}_{language or 'orig'}"
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)
    df[["item_id", "label"]].to_csv(out / "predictions.csv", index=False)
    df.to_json(out / "raw.jsonl", orient="records", lines=True, force_ascii=False)
    print(f"tokens in/out: {df.in_tokens.sum()}/{df.out_tokens.sum()}, mean latency {df.seconds.mean():.1f}s")
    print(out)


if __name__ == "__main__":
    main()
