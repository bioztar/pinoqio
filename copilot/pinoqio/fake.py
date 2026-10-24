"""Scripted demo negotiation (price drift, date drift, dodged defect question) for developing the UI."""
import asyncio
from collections.abc import AsyncIterator

from pinoqio.events import Chip, Contradiction, LedgerItem, Utterance, Verdict

PRICE_40 = LedgerItem("them", "unit price", "40k EUR", 2)
DATE_MARCH = LedgerItem("them", "delivery date", "15 March", 4)
PRICE_48 = LedgerItem("them", "unit price", "48k EUR", 8)
DATE_APRIL = LedgerItem("them", "delivery date", "end of April", 10)

# (speaker, text, t_start, t_end, verdict-or-None). Verdict utterance_id is filled in below.
_SCRIPT: tuple[tuple, ...] = (
    ("me", "Thanks for joining. Let's settle the order of five thousand units.", 0.0, 5.0, None),
    ("them", "Happy to. For five thousand units our price is forty thousand euros, all in.", 6.5, 12.0,
     dict(probability=0.12, verbal=0.1, vocal=0.15, ledger=(PRICE_40,),
          ask_next="What delivery date can you commit to?")),
    ("me", "Good. And when can you deliver?", 13.0, 15.0, None),
    ("them", "We can deliver by the fifteenth of March, guaranteed.", 16.2, 20.0,
     dict(probability=0.18, verbal=0.1, vocal=0.25, ledger=(PRICE_40, DATE_MARCH),
          ask_next="What is the defect rate on the last batch?")),
    ("me", "What was the defect rate on the last batch?", 21.0, 24.0, None),
    ("them", "Our quality team is world class, we are very proud of our process, many clients trust us.", 27.5, 35.0,
     dict(probability=0.64, verbal=0.7, vocal=0.5, ledger=(PRICE_40, DATE_MARCH),
          chips=(Chip("evasion", "Dodged a direct question: no number given", 0.5, "we are very proud of our process"),
                 Chip("latency", "Paused 3.5 s before answering", 0.15),
                 Chip("pause", "Long pauses vs own baseline", 0.1)),
          ask_next="Just the percentage: what was the defect rate?")),
    ("me", "Okay, but the actual number?", 36.0, 38.0, None),
    ("them", "Let's come back to that. On price, with raw materials up, it will be forty-eight thousand.", 39.0, 46.0,
     dict(probability=0.86, verbal=0.9, vocal=0.55, ledger=(PRICE_48, DATE_MARCH),
          chips=(Chip("contradiction", "Price was 40k at 0:09, now 48k", 0.55, "it will be forty-eight thousand"),
                 Chip("number_drift", "Unit price +20% with no new terms", 0.25),
                 Chip("pitch", "Pitch +1.8 SD above own baseline", 0.1)),
          contradiction=Contradiction("it will be forty-eight thousand", "our price is forty thousand euros, all in", 2, 0.92),
          ask_next="What changed since you quoted 40k all in?")),
    ("me", "Earlier you said forty thousand, all in.", 47.0, 50.0, None),
    ("them", "Delivery, honestly, I think maybe end of April, we are hoping.", 52.0, 58.0,
     dict(probability=0.91, verbal=0.95, vocal=0.6, ledger=(PRICE_48, DATE_APRIL),
          chips=(Chip("contradiction", "Delivery was 15 March at 0:16, now end of April", 0.55, "maybe end of April"),
                 Chip("hedging", "I think / maybe / hoping", 0.25),
                 Chip("filler", "Fillers up vs own baseline", 0.1)),
          contradiction=Contradiction("I think maybe end of April", "We can deliver by the fifteenth of March, guaranteed", 4, 0.9),
          ask_next="Is 15 March still guaranteed, yes or no?")),
)


async def events(speed: float = 1.0) -> AsyncIterator[Utterance | Verdict]:
    """Yield the script with call-like timing; speed>1 plays faster."""
    clock = 0.0
    for i, (speaker, text, t_start, t_end, verdict) in enumerate(_SCRIPT, start=1):
        await asyncio.sleep(max(0.0, t_end - clock) / speed)
        clock = t_end
        yield Utterance(i, speaker, text, t_start, t_end)
        if verdict:
            await asyncio.sleep(1.2 / speed)  # model latency
            yield Verdict(utterance_id=i, **verdict)
