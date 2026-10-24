"""Pinoqio judge: learns an expert's unwritten rules from labeled conversations (Plata track).

    python pipeline.py adapt --train /input/train.jsonl --artifacts /artifacts
    python pipeline.py eval  --test /input/test.jsonl --artifacts /artifacts --out /output/predictions.csv

adapt: explain every `bad` example -> merge explanations into a per-topic rulebook -> self-check on train
       -> save rulebook.json (used verbatim by eval) and explanation.md for the jury (rendered from the same file).
eval:  rulebook for the item's topic goes into the prompt; any violated rule makes the conversation `bad`.
"""
import argparse
import csv
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gemma

TEACHER = os.environ.get("JUDGE_TEACHER_MODEL", gemma.FAST)
JUDGE = os.environ.get("JUDGE_MODEL", gemma.FAST)
WORKERS = int(os.environ.get("JUDGE_WORKERS", "6"))


# ---------- io ----------

def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def item_text(item):
    return json.dumps({"context": item["context"], "conversation": item["conversation"]}, ensure_ascii=False)


def last_reply(item, limit=220):
    replies = [m["content"] for m in item["conversation"] if m["role"] == "assistant"]
    text = " ".join((replies[-1] if replies else "").split())
    return text[:limit] + ("…" if len(text) > limit else "")


def first_question(item, limit=120):
    qs = [m["content"] for m in item["conversation"] if m["role"] == "user"]
    text = " ".join((qs[0] if qs else "").split())
    return text[:limit] + ("…" if len(text) > limit else "")


def parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in model output")
    return json.loads(m.group(0))


def example_text(item):
    q = " ".join(m["content"] for m in item["conversation"] if m["role"] == "user")
    return f"{q} || {last_reply(item, 600)}"


class Precedents:
    """Nearest expert-labeled training conversations of the same topic (TF-IDF, local, no API calls)."""

    def __init__(self, examples, per_label=2):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.per_label = per_label
        self.by_topic = {}
        for topic in {e["topic"] for e in examples}:
            rows = [e for e in examples if e["topic"] == topic]
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
            self.by_topic[topic] = (rows, vec, vec.fit_transform([e["text"] for e in rows]))

    def nearest(self, item, k=5):
        if item["topic"] not in self.by_topic:
            return []
        rows, vec, matrix = self.by_topic[item["topic"]]
        sims = (matrix @ vec.transform([example_text(item)]).T).toarray().ravel()
        return [rows[i] for i in sims.argsort()[::-1] if rows[i]["item_id"] != item["item_id"]][:k]

    def find(self, item):
        if item["topic"] not in self.by_topic:
            return []
        rows, vec, matrix = self.by_topic[item["topic"]]
        sims = (matrix @ vec.transform([example_text(item)]).T).toarray().ravel()
        order = sims.argsort()[::-1]
        picked = {"bad": [], "good": []}
        for i in order:
            e = rows[i]
            if e["item_id"] != item["item_id"] and len(picked[e["label"]]) < self.per_label:
                picked[e["label"]].append(e)
        return picked["bad"] + picked["good"]


def precedent_block(found):
    if not found:
        return ""
    lines = []
    for e in found:
        why = f" | expert's objection: {e['violation']}" if e["label"] == "bad" and e.get("violation") else ""
        lines.append(f"- expert label {e['label'].upper()}: {e['text'][:700]}{why}")
    return "SIMILAR TRAINING CONVERSATIONS ALREADY LABELED BY THE EXPERT (precedents):\n" + "\n".join(lines) + "\n\nCONVERSATION TO GRADE:\n"


def pmap(fn, items):
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(fn, items))


# ---------- adapt ----------

EXPLAIN_SYSTEM = (
    "You audit replies of a bank's personal finance assistant (Mexican bank, MXN). An expert labeled this "
    "conversation BAD. Find exactly what the expert objected to. Check every number, date, product condition "
    "and promise in the assistant's replies against the context; check whether it answered what was asked, "
    "invented facts, claimed actions it cannot perform, agreed with a wrong user claim, or asked for data it "
    "already had. Then state the violation as a general, reusable rule for this topic, not tied to this "
    'customer. JSON only: {"violation": "<what is wrong here, citing the facts>", "rule": "<general rule>"}'
)

MERGE_SYSTEM = (
    "You write the evaluation rulebook of a financial domain expert. You get the expert's violations found in "
    "BAD conversations of one topic (with item ids) and a sample of GOOD conversations. Merge them into 4-10 "
    "distinct, general rules. Each rule must be checkable from the context and conversation, and must not "
    "contradict the GOOD sample. Order by priority: 1 = most severe (wrong facts, money or product conditions), "
    "higher numbers = softer issues. For each rule list the item ids that illustrate it. "
    'JSON only: {"rules": [{"id": "<TOPIC>-<n>", "priority": <int>, "rule": "<imperative rule>", '
    '"why": "<why the expert cares>", "evidence": ["<item_id>", ...]}], '
    '"good_looks_like": "<one sentence: what a GOOD reply does in this topic>"}'
)


def explain_bad(item):
    r = gemma.ask(f"Topic: {item['topic']}\n\n{item_text(item)}", model=TEACHER, system=EXPLAIN_SYSTEM)
    try:
        out = parse_json(r["text"])
    except Exception:
        out = {"violation": r["text"][:400], "rule": ""}
    return {"item_id": item["item_id"], "topic": item["topic"], **out}


def merge_topic(topic, explained, goods):
    bad_lines = "\n".join(f"- [{e['item_id']}] violation: {e['violation']} | rule: {e['rule']}" for e in explained)
    good_lines = "\n".join(f"- [{g['item_id']}] Q: {first_question(g)} | A: {last_reply(g, 300)}" for g in goods[:15])
    prompt = f"TOPIC: {topic}\n\nBAD conversations, expert's violations:\n{bad_lines}\n\nGOOD sample:\n{good_lines}"
    out = parse_json(gemma.ask(prompt, model=TEACHER, system=MERGE_SYSTEM)["text"])
    for i, rule in enumerate(sorted(out["rules"], key=lambda x: x.get("priority", 99)), 1):
        rule["id"] = f"{topic[:4].upper()}-{i}"
    out["rules"] = sorted(out["rules"], key=lambda x: x.get("priority", 99))
    return out


BOUNDARY_SYSTEM = (
    "You get training conversations where a rule-based judge disagreed with the expert's label, with the judge's "
    "reasoning. Describe 1-3 concrete CONDITIONS under which the expert's labels are hard to predict or look "
    "inconsistent (e.g. 'short replies that omit X were labeled both ways'). Each condition must cite the item ids "
    'it is based on. JSON only: {"boundaries": [{"condition": "<one sentence>", "items": ["<item_id>", ...]}]}'
)


def summarize_boundaries(misses, by_id):
    """Turns raw disagreements into named conditions with evidence (jury criterion: clear boundaries)."""
    if not misses:
        return []
    lines = "\n".join(f"- [{m['item_id']}] topic {m['topic']}, expert {m['expert']}, judge {m['judge']}. "
                      f"Q: {first_question(by_id[m['item_id']])} | A: {last_reply(by_id[m['item_id']], 300)} | judge: {m['judge_reason']}"
                      for m in misses)
    try:
        out = parse_json(gemma.ask(lines, model=TEACHER, system=BOUNDARY_SYSTEM)["text"])
        return [b for b in out.get("boundaries", []) if b.get("condition")]
    except Exception as e:
        print(f"boundaries: {type(e).__name__}", file=sys.stderr)
        return []


def adapt(train_path, artifacts):
    artifacts = Path(artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    train = read_jsonl(train_path)
    by_id = {t["item_id"]: t for t in train}
    topics = sorted({t["topic"] for t in train})

    explained = pmap(explain_bad, [t for t in train if t["label"] == "bad"])
    (artifacts / "violations.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in explained), encoding="utf-8")
    print(f"explained {len(explained)} bad examples", file=sys.stderr)
    # Precedent store for eval: every labeled training conversation, with the expert's objection for bad ones
    why = {e["item_id"]: e.get("violation", "") for e in explained}
    examples = [{"item_id": t["item_id"], "topic": t["topic"], "label": t["label"], "text": example_text(t),
                 "violation": why.get(t["item_id"], "")} for t in train]
    (artifacts / "examples.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in examples), encoding="utf-8")

    def merge(topic):
        return topic, merge_topic(topic, [e for e in explained if e["topic"] == topic],
                                  [t for t in train if t["topic"] == topic and t["label"] == "good"])

    rulebook = {"train_total": len(train), "topics": dict(pmap(merge, topics))}
    for book in rulebook["topics"].values():
        for rule in book["rules"]:
            rule["evidence"] = [i for i in rule.get("evidence", []) if i in by_id]
    (artifacts / "rulebook.json").write_text(json.dumps(rulebook, ensure_ascii=False, indent=2), encoding="utf-8")
    # The exact system prompt eval will send for each topic: proof that the explained rules are the ones in use
    (artifacts / "prompts").mkdir(exist_ok=True)
    for topic in topics:
        (artifacts / "prompts" / f"{topic}.txt").write_text(build_system(topic, rulebook), encoding="utf-8")
    print("rulebook written", file=sys.stderr)

    # Self-check on train: where does the learned judge still disagree with the expert? -> boundaries for the jury.
    # A fixed, topic-balanced sample keeps adapt within minutes on a slow API.
    per_topic = int(os.environ.get("JUDGE_SELF_CHECK_PER_TOPIC", "12"))
    sample = [t for topic in topics for t in [x for x in train if x["topic"] == topic][:per_topic]]
    precedents = load_precedents(artifacts)
    preds = dict(pmap(lambda t: judge_item(t, rulebook, precedents), sample))
    misses = [{"item_id": t["item_id"], "topic": t["topic"], "expert": t["label"], "judge": preds[t["item_id"]]["label"],
               "judge_reason": preds[t["item_id"]].get("reason", "")} for t in sample if preds[t["item_id"]]["label"] != t["label"]]
    rulebook["self_check"] = {"train_size": len(sample), "agree": len(sample) - len(misses), "disagreements": misses,
                              "boundaries": summarize_boundaries(misses, by_id)}
    (artifacts / "rulebook.json").write_text(json.dumps(rulebook, ensure_ascii=False, indent=2), encoding="utf-8")
    (artifacts / "explanation.md").write_text(render_explanation(rulebook, by_id), encoding="utf-8")
    print(f"self-check: {len(sample) - len(misses)}/{len(sample)} agree with the expert", file=sys.stderr)


# ---------- eval ----------

JUDGE_SYSTEM = (
    "You are a financial domain expert grading a bank assistant's conversation (Mexican bank, MXN). "
    "Evaluate the entire conversation against the context. Procedure: (1) check every number, date, balance, "
    "rate and product condition the assistant states against the context; (2) check every rule below, in "
    "priority order. Any violation of an applicable rule makes the conversation bad; otherwise it is good. "
    "Do not invent rules beyond the list and obvious factual errors.\n\n"
    "RULES FOR TOPIC {topic}:\n{rules}\n\nA GOOD reply in this topic: {good}\n\n"
    'JSON only: {{"violated": ["<rule id or FACT>", ...], "reason": "<one sentence>", "label": "good" | "bad"}}'
)


def rules_text(book):
    return "\n".join(f"{r['id']} (priority {r.get('priority', '?')}): {r['rule']}" for r in book["rules"])


def build_system(topic, rulebook):
    book = rulebook["topics"].get(topic, {"rules": [], "good_looks_like": ""})
    return JUDGE_SYSTEM.format(topic=topic, rules=rules_text(book), good=book.get("good_looks_like", ""))


def judge_item(item, rulebook, precedents=None):
    try:
        prefix = precedent_block(precedents.find(item)) if precedents and USE_PRECEDENTS else ""
        r = gemma.ask(f"{prefix}Topic: {item['topic']}\n\n{item_text(item)}", model=JUDGE, system=build_system(item["topic"], rulebook))
        try:
            out = parse_json(r["text"])
        except ValueError:  # the model occasionally answers in prose; read the verdict from the text
            m = re.findall(r"\b(good|bad)\b", r["text"].lower())
            out = {"label": m[-1] if m else "good", "reason": r["text"][:200], "violated": []}
        label = out.get("label") if out.get("label") in ("good", "bad") else ("bad" if out.get("violated") else "good")
        return item["item_id"], {"label": label, "reason": out.get("reason", ""), "violated": out.get("violated", [])}
    except Exception as e:  # never drop an item: the scorer rejects missing ids
        print(f"{item['item_id']}: {type(e).__name__} {str(e)[:80]}", file=sys.stderr)
        # API failed after all retries: take the majority label of the most similar expert-labeled conversations
        sims = [e["label"] for e in (precedents.nearest(item) if precedents else [])]
        label = "bad" if sims.count("bad") > sims.count("good") else "good"
        return item["item_id"], {"label": label, "reason": "fallback after API error: label of similar training examples", "violated": []}


def load_precedents(artifacts):
    path = Path(artifacts) / "examples.jsonl"
    return Precedents(read_jsonl(path)) if path.exists() else None


USE_PRECEDENTS = os.environ.get("JUDGE_PRECEDENTS", "0") == "1"


def evaluate(test_path, artifacts, out_path):
    rulebook = json.loads((Path(artifacts) / "rulebook.json").read_text(encoding="utf-8"))
    precedents = load_precedents(artifacts)
    test = read_jsonl(test_path)
    preds = dict(pmap(lambda t: judge_item(t, rulebook, precedents), test))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "label"])
        for t in test:
            w.writerow([t["item_id"], preds[t["item_id"]]["label"]])
    with open(out_path.with_suffix(".reasons.jsonl"), "w", encoding="utf-8") as f:
        for iid, p in preds.items():
            f.write(json.dumps({"item_id": iid, **p}, ensure_ascii=False) + "\n")


# ---------- explanation for the jury ----------

def render_explanation(rulebook, by_id):
    lines = [
        "# How this judge decides",
        "",
        "Generated automatically by `adapt` from the labeled training set. The rules below are inserted verbatim "
        "into the prompt that `eval` uses for every test conversation (see `rulebook.json`, field `topics`, and "
        "the exact per-topic prompts in `prompts/<topic>.txt`), so this document is the working model, not a separate summary.",
        "",
        "## Decision procedure",
        "",
        "1. Pick the rules for the conversation's topic.",
        "2. Check every number, date, balance, rate and product condition in the assistant's replies against the customer's data.",
        "3. Check the rules in priority order (1 = most severe). **Any violated rule makes the conversation `bad`.** "
        "Because one violation is enough, priorities do not trade off against each other; they say which problem "
        "is named first and which issues the expert treats as most serious.",
        "4. No violation: `good`.",
        "",
    ]
    if USE_PRECEDENTS:
        lines += ["Together with the rules, the judge sees the 2 most similar `bad` and 2 most similar `good` training "
                  "conversations of the same topic (character n-gram TF-IDF over the question and the reply, stored in "
                  "`examples.jsonl`), with the expert's objection for the `bad` ones. They are precedents for borderline "
                  "cases; the rules above stay the decision criteria.", ""]
    lines += ["If the model API fails on a conversation after all retries, its label falls back to the majority "
              "label of the 5 most similar training conversations of the same topic (`examples.jsonl`).", ""]
    for topic, book in rulebook["topics"].items():
        lines += [f"## Topic: {topic}", "", f"**A good reply:** {book.get('good_looks_like', '')}", "",
                  "| Rule | Priority | Rule text | Why the expert cares |", "|---|---|---|---|"]
        for r in book["rules"]:
            lines.append(f"| {r['id']} | {r.get('priority', '')} | {r['rule']} | {r.get('why', '')} |")
        lines += ["", "**Training examples behind each rule** (expert label: `bad`):", ""]
        for r in book["rules"]:
            for iid in r.get("evidence", [])[:2]:
                ex = by_id[iid]
                lines.append(f"- **{r['id']}** · `{iid}` · Q: “{first_question(ex)}” · A: “{last_reply(ex)}”")
        goods = [t for t in by_id.values() if t["topic"] == topic and t["label"] == "good"][:2]
        if goods:
            lines += ["", "**What the expert accepts** (expert label: `good`, no rule above is broken):", ""]
            for ex in goods:
                lines.append(f"- `{ex['item_id']}` · Q: “{first_question(ex)}” · A: “{last_reply(ex)}”")
        lines.append("")
    sc = rulebook.get("self_check")
    if sc:
        lines += ["## Boundaries: where the rules and the expert still disagree", "",
                  f"Re-judging the training set with these rules agrees with the expert on **{sc['agree']} of {sc['train_size']}** conversations. "
                  "The disagreements below mark where the expert's rules are not fully captured, or where similar "
                  "conversations received different labels. Treat predictions on similar cases as less certain.", ""]
        for b in sc.get("boundaries", []):
            ids = ", ".join(f"`{i}`" for i in b.get("items", []) if i in by_id)
            lines.append(f"- **Condition:** {b['condition']} Examples: {ids or '—'}.")
        if sc.get("boundaries"):
            lines += ["", "All disagreements:", ""]
        for m in sc["disagreements"][:20]:
            ex = by_id[m["item_id"]]
            lines.append(f"- `{m['item_id']}` ({m['topic']}) expert **{m['expert']}**, judge {m['judge']}. "
                         f"Q: “{first_question(ex)}” · A: “{last_reply(ex, 160)}” · judge's reason: {m['judge_reason']}")
        lines.append("")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("adapt")
    a.add_argument("--train", default="/input/train.jsonl")
    a.add_argument("--artifacts", default="/artifacts")
    e = sub.add_parser("eval")
    e.add_argument("--test", default="/input/test.jsonl")
    e.add_argument("--artifacts", default="/artifacts")
    e.add_argument("--out", default="/output/predictions.csv")
    args = p.parse_args()
    if args.cmd == "adapt":
        adapt(args.train, args.artifacts)
    else:
        evaluate(args.test, args.artifacts, args.out)


if __name__ == "__main__":
    main()
