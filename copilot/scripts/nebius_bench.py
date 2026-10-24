"""Latency/quality check of candidate Nebius models on the verifier prompt.

Run: PINOQIO_ENV_FILE=/path/to/.env PYTHONPATH=. uv run python scripts/nebius_bench.py [model ...]
Expect: price and delivery -> is_contradiction true (>=0.85), honest pair -> false.
"""
import asyncio
import sys
import time

from pinoqio.events import Utterance
from pinoqio.verifier import Claim, verify

MODELS = (
    "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "deepseek-ai/DeepSeek-V4.1-Flash",
    "openai/gpt-oss-120b",
)

HIST = (
    Utterance(1, "them", "Our unit price for the 500 units is 40 thousand euros.", 42.0, 46.0),
    Utterance(2, "me", "When can you deliver?", 47.0, 49.0),
    Utterance(3, "them", "We can deliver in mid-March, around the 15th.", 50.0, 54.0),
    Utterance(4, "me", "And the price again?", 55.0, 57.0),
    Utterance(5, "them", "For the 500 units the price is 48 thousand euros.", 58.0, 62.0),
    Utterance(6, "me", "And delivery?", 63.0, 65.0),
    Utterance(7, "them", "Actually we are looking at the end of April for delivery.", 66.0, 70.0),
    Utterance(8, "me", "On which day?", 71.0, 72.0),
    Utterance(9, "them", "Delivery will be on the 15th of March, as I said.", 73.0, 76.0),
)

CASES = (
    ("price 40k->48k", 5, Claim("unit price", "40 thousand euros", 1, 42.0, "48 thousand euros", 58.0), True),
    ("delivery mid-March->end of April", 7, Claim("delivery date", "mid-March, around the 15th", 3, 50.0, "end of April", 66.0), True),
    ("honest: mid-March -> 15th of March", 9, Claim("delivery date", "mid-March, around the 15th", 3, 50.0, "15th of March", 73.0), False),
)


async def main(models: tuple[str, ...]) -> None:
    for model in models:
        print(f"\n{model}")
        for name, upto, claim, expect in CASES:
            t0 = time.perf_counter()
            try:
                v = await verify(claim, HIST[:upto], (), model=model)
                ok = "OK " if v.is_contradiction == expect else "BAD"
                print(f"  {ok} {time.perf_counter() - t0:4.1f}s {name}: {v.is_contradiction} {v.confidence:.2f} {v.reason[:80]}")
            except Exception as e:
                print(f"  ERR {time.perf_counter() - t0:4.1f}s {name}: {type(e).__name__} {str(e)[:100]}")


asyncio.run(main(tuple(sys.argv[1:]) or MODELS))
