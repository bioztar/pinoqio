"""Instant, local number-drift check: no model call, runs the moment a line is transcribed.

The LLM path (Gemma + Nebius) takes 3-12 s per line on a bad network. This catches the
loudest kind of inconsistency, a price or a date/duration that changes, in milliseconds, so
Pinoqio can jump in right away; the models still run afterwards and enrich the screen.

ponytail: keyword topics + regex numbers, English only; misses paraphrases the LLM catches.
"""
import re
from dataclasses import dataclass

WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "ninety": 90,
}
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december")
TOPIC_WORDS = {
    "payment": ("payment", "pay ", "net ", "invoice"),
    "price": ("price", "euro", "€", "$", "dollar", "cost", "total", "each", "per unit", "quote"),
    "delivery": ("deliver", "delivery", "week", "ship", "arrive", "lead time"),
}
NUM = r"\d[\d,.]*(?:\s*(?:thousand|k))?"
_WORD = "|".join(WORD_NUM)


@dataclass(frozen=True)
class Drift:
    topic: str
    then: str
    now: str
    then_t: float


def _topic(text: str) -> str | None:
    t = f" {text.lower()} "
    for topic, words in TOPIC_WORDS.items():  # payment first: "net thirty days" is not delivery
        if any(w in t for w in words):
            return topic
    return None


def _num(token: str) -> float | None:
    s = token.lower().replace(",", "").strip()
    mult = 1000 if s.endswith(("thousand", "k")) else 1
    s = re.sub(r"\s*(thousand|k)$", "", s)
    try:
        return float(s) * mult
    except ValueError:
        return None


_UNITS = {**WORD_NUM, "zero": 0, "thirteen": 13, "fourteen": 14, "sixteen": 16, "seventeen": 17,
          "eighteen": 18, "nineteen": 19, "seventy": 70, "eighty": 80}
_SPELLED = re.compile(r"\b(?:(?:%s|hundred|thousand|and)[\s-]+)*(?:%s|hundred|thousand)\b" % ("|".join(_UNITS), "|".join(_UNITS)))


def _spelled_to_digits(text: str) -> str:
    """'nine hundred' -> '900', 'one thousand fifty' -> '1050', 'forty-eight thousand' -> '48000'.
    Speech-to-text sometimes writes numbers out; the regexes below only read digits."""
    def conv(m: re.Match) -> str:
        words = [w for w in re.split(r"[\s-]+", m.group(0)) if w and w != "and"]
        total = cur = 0
        for w in words:
            if w == "hundred":
                cur = max(cur, 1) * 100
            elif w == "thousand":
                total += max(cur, 1) * 1000
                cur = 0
            else:
                cur += _UNITS[w]
        n = total + cur
        return str(n) if (n >= 100 or "hundred" in words or "thousand" in words) else m.group(0)
    return _SPELLED.sub(conv, text.lower())


def _price(text: str) -> str | None:
    """The money figure in a line, skipping quantities ('200 units', '200 times')."""
    t = _spelled_to_digits(text)
    found = []
    for m in re.finditer(NUM, t):
        after = t[m.end():m.end() + 12]
        if re.match(r"\s*(units?|laptops?|pieces?|pcs|times|x\b|%|percent|weeks?|days?|months?)", after):
            continue
        n = _num(m.group(0))
        if n is not None and n >= 10:
            found.append(n)
    return f"{max(found):,.0f}" if found else None


def _duration(text: str) -> str | None:
    t = text.lower()
    m = re.search(rf"(\d+|{_WORD})(?:\s*(?:or|to|-)\s*(\d+|{_WORD}))?\s*(weeks?|days?|months?)", t)
    if m:
        a = WORD_NUM.get(m.group(1), m.group(1))
        b = m.group(2) and WORD_NUM.get(m.group(2), m.group(2))
        unit = m.group(3).rstrip("s") + "s"
        return f"{a}-{b} {unit}" if b else f"{a} {unit}"
    month = next((mo for mo in MONTHS if re.search(rf"\b{mo}\b", t)), None)
    return month.capitalize() if month else None


def value(topic: str, text: str) -> str | None:
    if topic == "price":
        return _price(text)
    if topic == "delivery":
        return _duration(text)
    return None


def check(text: str, context: str, t: float, seen: dict[str, tuple[str, float]]) -> tuple[dict[str, tuple[str, float]], Drift | None]:
    """New `seen` (topic -> first value, time) and a Drift when this line changes a value.

    `context` is the buyer's previous line, used when the seller's answer has no topic word
    ("Sure. 200 times 1,050, plus delivery." answers "What is the total price?").
    """
    topic = _topic(text) if _topic(text) in ("price",) else (_topic(context) or _topic(text))
    if topic is None:
        return seen, None
    v = value(topic, text)
    if v is None:
        return seen, None
    if topic not in seen:
        return {**seen, topic: (v, t)}, None
    first, first_t = seen[topic]
    if v == first:
        return seen, None
    return seen, Drift(topic, first, v, first_t)


if __name__ == "__main__":
    seen: dict = {}
    script = [
        ("I need 200 laptops. What is the price?", "For 200 units, it's 900 euros each, delivery included."),
        ("When is delivery?", "Two weeks from the order, guaranteed."),
        ("What is the total price?", "Sure. 200 times 1,050, plus delivery."),
        ("Delivery is two weeks?", "Actually, more like five or six weeks, with the current stock."),
        ("And payment?", "Net thirty days from delivery, same as always."),
    ]
    hits = []
    for i, (me, them) in enumerate(script):
        seen, d = check(them, me, float(i * 10), seen)
        hits.append(d)
    assert hits[0] is None and hits[1] is None and hits[4] is None, hits
    assert hits[2] and (hits[2].then, hits[2].now) == ("900", "1,050"), hits[2]
    assert hits[3] and (hits[3].then, hits[3].now) == ("2 weeks", "5-6 weeks"), hits[3]
    # same call, numbers written out by speech-to-text
    seen2: dict = {}
    seen2, d1 = check("For two hundred units, it's nine hundred euros each, delivery included.", "What is the price?", 0.0, seen2)
    seen2, d2 = check("Sure. Two hundred times one thousand fifty, plus delivery.", "What is the total price?", 30.0, seen2)
    assert d1 is None and d2 and (d2.then, d2.now) == ("900", "1,050"), d2
    print("quickcheck ok")
