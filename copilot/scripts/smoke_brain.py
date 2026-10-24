"""Live smoke: scripted negotiation through the real Gemma analyst.

Run: PINOQIO_ENV_FILE=/path/to/.env uv run python scripts/smoke_brain.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pinoqio.brain import verdicts
from pinoqio.events import Utterance, Verdict

SCRIPT = (
    ("them", "Thanks for joining. Our unit price for the 500 units is 40 thousand euros."),
    ("me", "That works. When can you deliver?"),
    ("them", "We can have everything delivered in March."),
    ("me", "Good. What is the defect rate on the last batch?"),
    ("them", "Well, we really focus on quality here, our customers are always happy and we are ISO certified."),
    ("me", "Understood. Let's confirm the price again."),
    ("them", "Right, so for the 500 units the price is 48 thousand euros."),
    ("me", "And delivery is still March?"),
    ("them", "Actually we are looking at the end of April for delivery."),
    ("me", "Is payment on delivery acceptable?"),
    ("them", "Yes, payment on delivery is fine with us."),
)


async def feed():
    t = 0.0
    for i, (who, text) in enumerate(SCRIPT, 1):
        yield Utterance(i, who, text, t, t + 3.0)
        t += 5.0


async def main() -> None:
    texts: dict[int, str] = {}
    async for item in verdicts(feed()):
        if isinstance(item, Utterance):
            texts[item.id] = item.text
            continue
        print(f"\n[{item.utterance_id}] {texts[item.utterance_id][:70]}")
        print(f"  p={item.probability:.0%} verbal={item.verbal:.0%} vocal={item.vocal:.0%}")
        for c in item.chips:
            print(f"  chip {c.kind}: {c.label} (w={c.weight})")
        if item.ask_next:
            print(f"  ask: {item.ask_next}")
        print(f"  ledger: {[(i.item, i.value) for i in item.ledger]}")


asyncio.run(main())
