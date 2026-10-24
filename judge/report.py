"""Demo report for the judge lane: one self-contained HTML page built from a run.

    python report.py runs/v1 runs/baseline_gemma-4-26b-a4b-it_orig data/plata/data/public_test.csv runs/v1/report.html
"""
import csv
import html
import json
import sys
from pathlib import Path

from pipeline import first_question, parse_json

TOPICS = {"spending": "Spending", "savings": "Savings", "credit": "Credit card", "financial_position": "My money now"}
REPO = "https://github.com/bioztar/pinoqio"
esc = html.escape


def read_preds(path):
    with open(path, encoding="utf-8") as f:
        return {r["item_id"]: r["label"] for r in csv.DictReader(f)}


def stats(gold, pred, topic_of):
    by_topic = {}
    for t in TOPICS:
        ids = [i for i in gold if topic_of[i] == t]
        by_topic[t] = sum(gold[i] == pred[i] for i in ids) / len(ids)
    bad = [i for i in gold if gold[i] == "bad"]
    good = [i for i in gold if gold[i] == "good"]
    return {
        "macro": sum(by_topic.values()) / len(by_topic),
        "by_topic": by_topic,
        "missed": sum(pred[i] == "good" for i in bad), "bad_total": len(bad),
        "false_alarm": sum(pred[i] == "bad" for i in good), "good_total": len(good),
    }


def in_numbers(row, lang):
    """One plain sentence with the real figures, so the stage case is obvious without reading JSON."""
    import gemma
    prompt = (f"Customer data and conversation below. The expert labeled the bot's answer BAD. In ONE short sentence in {lang}, "
              "using the concrete numbers from the customer data, say what the correct answer would be and how the bot's "
              "answer differs. Plain words, no JSON.\n\n"
              + json.dumps({"context": json.loads(row["context"]), "conversation": json.loads(row["conversation"])}, ensure_ascii=False))
    return gemma.ask(prompt, model=gemma.FAST)["text"].strip()


def render_value(v):
    if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
        cols = list(dict.fromkeys(k for row in v for k in row))
        head = "".join(f"<th>{esc(c)}</th>" for c in cols)
        rows = "".join("<tr>" + "".join(f"<td>{esc(str(r.get(c, '')))}</td>" for c in cols) + "</tr>" for r in v[:8])
        return f'<div class="scroll"><table class="ctx"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
    if isinstance(v, dict):
        return '<div class="kv">' + "".join(f"<span><b>{esc(k)}</b> {esc(json.dumps(x, ensure_ascii=False))}</span>" for k, x in v.items()) + "</div>"
    return f'<span class="mono">{esc(str(v))}</span>'


def bars_svg(before, after):
    """Paired horizontal bars per topic, one 0-100% scale."""
    w, label_w, row_h, top = 640, 190, 46, 24
    scale = (w - label_w - 50) / 100
    h = top + row_h * len(TOPICS) + 8
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Agreement with the expert by topic">']
    for pct in (0, 50, 100):
        x = label_w + pct * scale
        parts.append(f'<line x1="{x}" y1="{top - 8}" x2="{x}" y2="{h - 4}" class="grid"/>'
                     f'<text x="{x}" y="{top - 12}" class="tick" text-anchor="middle">{pct}%</text>')
    for n, t in enumerate(TOPICS):
        y = top + n * row_h
        b, a = before[t] * 100, after[t] * 100
        parts.append(f'<text x="0" y="{y + 20}" class="lab">{esc(TOPICS[t])}</text>'
                     f'<rect x="{label_w}" y="{y + 4}" width="{b * scale:.1f}" height="12" rx="2" class="b0"/>'
                     f'<text x="{label_w + b * scale + 6:.1f}" y="{y + 14}" class="val0">{b:.0f}</text>'
                     f'<rect x="{label_w}" y="{y + 20}" width="{a * scale:.1f}" height="14" rx="2" class="b1"/>'
                     f'<text x="{label_w + a * scale + 6:.1f}" y="{y + 32}" class="val1">{a:.0f}%</text>')
    parts.append("</svg>")
    return "".join(parts)


def main(run_dir, base_dir, test_csv, out_path):
    run_dir, base_dir = Path(run_dir), Path(base_dir)
    with open(test_csv, encoding="utf-8") as f:
        test = {r["item_id"]: r for r in csv.DictReader(f)}
    gold = {i: r["label"] for i, r in test.items()}
    topic_of = {i: r["topic"] for i, r in test.items()}
    base, ours = read_preds(base_dir / "predictions.csv"), read_preds(run_dir / "predictions.csv")
    reasons = {}
    with open(run_dir / "predictions.reasons.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            reasons[r["item_id"]] = r
    rulebook = json.loads((run_dir / "artifacts" / "rulebook.json").read_text(encoding="utf-8"))
    s0, s1 = stats(gold, base, topic_of), stats(gold, ours, topic_of)

    # The stage case: expert said bad, the untrained judge let it through, Pinoqio caught it and named a rule
    order = list(TOPICS)
    caught = [i for i in gold if gold[i] == "bad" and base[i] == "good" and ours[i] == "bad" and reasons[i].get("violated")]
    caught.sort(key=lambda i: (order.index(topic_of[i]), len(test[i]["conversation"])))
    case = caught[0] if caught else next(i for i in gold if gold[i] == ours[i] == "bad")

    rules = [(t, r) for t, b in rulebook["topics"].items() for r in b["rules"]]
    rule_text = {r["id"]: r["rule"] for _, r in rules}
    case_reason = reasons[case].get("reason", "")
    numbers = in_numbers(test[case], "English")

    conv = json.loads(test[case]["conversation"])
    ctx = json.loads(test[case]["context"])
    dialog = "".join(f'<div class="msg {m["role"]}"><span class="who">{"Customer" if m["role"] == "user" else "Bank bot"}</span>'
                     f'<p>{esc(m["content"])}</p></div>' for m in conv)
    ctx_html = "".join(f'<div class="ctx-row"><span class="ctx-key">{esc(k)}</span>{render_value(v)}</div>' for k, v in ctx.items())
    violated = [v for v in reasons[case].get("violated", []) if v in rule_text]
    violated_html = "".join(f'<li><span class="rid">{esc(v)}</span> {esc(rule_text[v])}</li>' for v in violated) or "<li>Wrong facts</li>"

    rules_html = ""
    for t, book in rulebook["topics"].items():
        items = "".join(f'<li><span class="prio p{min(r.get("priority", 3), 4)}">{r.get("priority", "")}</span>'
                        f'<span class="rid">{esc(r["id"])}</span><span>{esc(rule_text[r["id"]])}</span>'
                        f'<span class="ev">{len(r.get("evidence", []))} examples</span></li>' for r in book["rules"])
        rules_html += f'<div class="topic"><h3>{esc(TOPICS.get(t, t))}</h3><ol class="rules">{items}</ol></div>'

    sc = rulebook.get("self_check", {})
    pct = lambda x: f"{x * 100:.0f}%"
    page = TEMPLATE.format(
        before=pct(s0["macro"]), after=pct(s1["macro"]),
        missed0=s0["missed"], missed1=s1["missed"], bad_total=s1["bad_total"],
        fa0=s0["false_alarm"], fa1=s1["false_alarm"], good_total=s1["good_total"],
        n_test=len(gold), n_train=rulebook.get("train_total", 150), n_rules=len(rules),
        bars=bars_svg(s0["by_topic"], s1["by_topic"]),
        case_topic=esc(TOPICS[topic_of[case]]), case_q=esc(first_question({"conversation": conv}, 200)),
        dialog=dialog, ctx=ctx_html, violated=violated_html, case_reason=esc(case_reason), numbers=esc(numbers), pts0=f"{10 * s0['macro']:.1f}", pts1=f"{10 * s1['macro']:.1f}",
        rules=rules_html, check_note=(f" Re-checking {sc['train_size']} training conversations, the judge with these rules agrees with the expert in {sc['agree']}." if sc else ""), repo=REPO,
    )
    Path(out_path).write_text(page, encoding="utf-8")
    print(out_path)


TEMPLATE = """<meta charset="utf-8">
<title>Pinoqio Judge</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Unbounded:wght@600;700&family=Golos+Text:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: stage report, one column ~60rem; result first, then how, a real case, the rules, try it yourself */
:root {{
  --bg: #f4f5f7; --surface: #ffffff; --ink: #17181c; --muted: #5d6270; --line: #dcdfe6;
  --wood: #c2701f; --wood-soft: #f6e6d3; --good: #1d7a4f; --good-soft: #dcf0e6; --bad: #c23a2b; --bad-soft: #f8e0dc;
  --f-display: "Unbounded", "Arial Black", system-ui, sans-serif;
  --f-body: "Golos Text", -apple-system, "Segoe UI", Roboto, sans-serif;
  --f-mono: "JetBrains Mono", ui-monospace, Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ color-scheme: dark;
  --bg: #121317; --surface: #1b1d23; --ink: #eceef3; --muted: #9ba1ae; --line: #2d313b;
  --wood: #f0a159; --wood-soft: #3a2a19; --good: #5fd39a; --good-soft: #15342a; --bad: #ff8a7a; --bad-soft: #3d1f1b; }} }}
:root[data-theme="dark"] {{ color-scheme: dark;
  --bg: #121317; --surface: #1b1d23; --ink: #eceef3; --muted: #9ba1ae; --line: #2d313b;
  --wood: #f0a159; --wood-soft: #3a2a19; --good: #5fd39a; --good-soft: #15342a; --bad: #ff8a7a; --bad-soft: #3d1f1b; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font: 400 16px/1.55 var(--f-body);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }}
.wrap {{ max-width: 60rem; margin: 0 auto; padding-block: 2.5rem 4rem; display: flex; flex-direction: column; gap: 3rem; }}
h1, h2, h3 {{ margin: 0; text-wrap: balance; }}
h1 {{ font: 700 clamp(2rem, 6vw, 3.2rem)/1.05 var(--f-display); }}
h1 .nose {{ color: var(--wood); }}
h2 {{ font: 700 1.3rem/1.2 var(--f-display); }}
h3 {{ font: 600 1.05rem/1.3 var(--f-body); }}
p {{ margin: 0; max-width: 65ch; }}
a {{ color: var(--wood); }}
.eyebrow {{ font: 600 0.75rem/1 var(--f-mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }}
.mono {{ font-family: var(--f-mono); font-variant-numeric: tabular-nums; }}
section {{ display: flex; flex-direction: column; gap: 1rem; }}
header {{ display: flex; flex-direction: column; gap: 0.9rem; }}
.lede {{ font-size: 1.15rem; color: var(--muted); }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: 1rem; }}
.tile {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 1.1rem 1.2rem; display: flex; flex-direction: column; gap: 0.35rem; }}
.big {{ font: 700 2.1rem/1.1 var(--f-display); font-variant-numeric: tabular-nums; }}
.big .from {{ color: var(--muted); font-size: 1.3rem; }}
.big .arrow {{ color: var(--muted); font-size: 1.2rem; padding: 0 0.3rem; }}
.tile .sub {{ color: var(--muted); font-size: 0.9rem; }}
.chart {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 1rem; overflow-x: auto; }}
.chart svg {{ width: 100%; min-width: 30rem; height: auto; display: block; }}
.chart .grid {{ stroke: var(--line); stroke-width: 1; }}
.chart .tick {{ fill: var(--muted); font: 400 11px var(--f-mono); }}
.chart .lab {{ fill: var(--ink); font: 500 14px var(--f-body); }}
.chart .b0 {{ fill: var(--line); }} .chart .b1 {{ fill: var(--wood); }}
.chart .val0 {{ fill: var(--muted); font: 400 11px var(--f-mono); }}
.chart .val1 {{ fill: var(--ink); font: 600 12px var(--f-mono); }}
.legend {{ display: flex; gap: 1.2rem; flex-wrap: wrap; font-size: 0.88rem; color: var(--muted); }}
.legend i {{ display: inline-block; width: 0.8rem; height: 0.8rem; border-radius: 2px; margin-right: 0.35rem; vertical-align: -1px; }}
.steps {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: 1rem; counter-reset: s; }}
.steps li {{ counter-increment: s; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.1rem; display: flex; flex-direction: column; gap: 0.4rem; }}
.steps li::before {{ content: counter(s); font: 700 1.1rem/1 var(--f-display); color: var(--wood); }}
.case {{ display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 1rem; }}
.panel {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.1rem; display: flex; flex-direction: column; gap: 0.75rem; min-width: 0; }}
.msg {{ display: flex; flex-direction: column; gap: 0.2rem; }}
.msg p {{ white-space: pre-wrap; font-size: 0.95rem; }}
.msg.assistant p {{ background: var(--bg); border-radius: 8px; padding: 0.6rem 0.75rem; }}
.who {{ font: 600 0.7rem/1 var(--f-mono); letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }}
.ctx-row {{ display: flex; flex-direction: column; gap: 0.25rem; }}
.ctx-key {{ font: 600 0.72rem/1 var(--f-mono); color: var(--muted); }}
.scroll {{ overflow-x: auto; }}
table.ctx {{ border-collapse: collapse; font: 400 0.78rem/1.4 var(--f-mono); font-variant-numeric: tabular-nums; }}
table.ctx th, table.ctx td {{ padding: 0.2rem 0.6rem 0.2rem 0; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }}
table.ctx th {{ color: var(--muted); font-weight: 600; }}
.kv {{ display: flex; flex-wrap: wrap; gap: 0.2rem 0.9rem; font: 400 0.8rem/1.5 var(--f-mono); }}
.kv b {{ color: var(--muted); font-weight: 600; }}
.verdicts {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.6rem; }}
.v {{ border-radius: 8px; padding: 0.6rem 0.7rem; display: flex; flex-direction: column; gap: 0.2rem; font-size: 0.85rem; }}
.v b {{ font: 700 1rem/1.2 var(--f-display); }}
.v.bad {{ background: var(--bad-soft); color: var(--bad); }} .v.good {{ background: var(--good-soft); color: var(--good); }}
.v .note {{ color: var(--ink); opacity: 0.75; font-size: 0.78rem; }}
.numbers {{ margin: 0; font-size: 1.05rem; }}
.numbers b {{ color: var(--wood); }}
.caught {{ border-left: 3px solid var(--wood); padding-left: 0.8rem; display: flex; flex-direction: column; gap: 0.4rem; }}
.caught ul {{ margin: 0; padding-left: 1rem; }}
.rid {{ font: 600 0.75rem/1 var(--f-mono); color: var(--wood); background: var(--wood-soft); padding: 0.2rem 0.35rem; border-radius: 4px; white-space: nowrap; }}
.topics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr)); gap: 1rem; }}
.topic {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.1rem; display: flex; flex-direction: column; gap: 0.7rem; min-width: 0; }}
.rules {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.55rem; }}
.rules li {{ display: grid; grid-template-columns: 1.4rem auto 1fr auto; gap: 0.5rem; align-items: baseline; font-size: 0.92rem; }}
.prio {{ font: 700 0.75rem/1.4 var(--f-mono); text-align: center; border-radius: 4px; }}
.p1 {{ background: var(--bad-soft); color: var(--bad); }} .p2 {{ background: var(--wood-soft); color: var(--wood); }}
.p3, .p4 {{ background: var(--bg); color: var(--muted); }}
.ev {{ font: 400 0.72rem/1 var(--f-mono); color: var(--muted); white-space: nowrap; }}
.howto {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr)); gap: 1rem; }}
pre {{ margin: 0; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 0.8rem 0.9rem; overflow-x: auto; font: 400 0.8rem/1.55 var(--f-mono); }}
.small {{ font-size: 0.88rem; color: var(--muted); }}
@media (max-width: 720px) {{ .case {{ grid-template-columns: 1fr; }} .verdicts {{ grid-template-columns: 1fr; }}
  .rules li {{ grid-template-columns: 1.4rem 1fr; }} .rules li .rid, .rules li .ev {{ grid-column: 2; }} }}
</style>
<div class="wrap">

<header>
  <span class="eyebrow">Pinoqio · judge mode · Plata track</span>
  <h1>A judge that learns from the <span class="nose">expert</span></h1>
  <p class="lede">An expert marked {n_train} bank-bot conversations as good or bad. Pinoqio found the expert's rules in these marks by itself, and now checks new answers the way the expert would.</p>
</header>

<section>
  <div class="tiles">
    <div class="tile"><span class="eyebrow">Task</span><p>Plata's expert marks the bank bot's answers as good or bad. His rules are written nowhere.</p></div>
    <div class="tile"><span class="eyebrow">Solution</span><p>Pinoqio reads the marks, writes the rules down, and judges like the expert. Every verdict names the rule.</p></div>
    <div class="tile"><span class="eyebrow">Result</span><p>Misses half as many bad answers: {missed0} → {missed1} of {bad_total}.</p></div>
  </div>
  <p class="small">Plata's score (out of 12) on the public test: without training ≈ {pts0} (no explanation). Pinoqio: {pts1} for accuracy + up to 2.0 for the auto-generated explanation.</p>
</section>

<section>
  <span class="eyebrow">Result on {n_test} new conversations Pinoqio never saw</span>
  <div class="tiles">
    <div class="tile"><span class="eyebrow">Agreement with the expert</span>
      <span class="big"><span class="from">{before}</span><span class="arrow">→</span>{after}</span>
      <span class="sub">Average accuracy over four topics, Plata's metric</span></div>
    <div class="tile"><span class="eyebrow">Bot mistakes missed</span>
      <span class="big"><span class="from">{missed0}</span><span class="arrow">→</span>{missed1}<span class="from"> of {bad_total}</span></span>
      <span class="sub">A bad answer the judge called good</span></div>
    <div class="tile"><span class="eyebrow">False alarms</span>
      <span class="big"><span class="from">{fa0}</span><span class="arrow">→</span>{fa1}<span class="from"> of {good_total}</span></span>
      <span class="sub">A good answer the judge called bad</span></div>
  </div>
  <div class="chart">{bars}</div>
  <div class="legend"><span><i style="background:var(--line)"></i>Gemma without training</span><span><i style="background:var(--wood)"></i>Pinoqio with the expert's rules</span><span>Same Gemma 4 model. The only difference is the learned rules</span></div>
</section>

<section>
  <h2>How it works</h2>
  <ol class="steps">
    <li><h3>The expert marks examples</h3><p class="small">About 150 conversations marked good or bad. The expert does not write any rules.</p></li>
    <li><h3>Pinoqio finds the rules</h3><p class="small">For every bad answer it asks: what is wrong, and what general rule is behind it? Then it merges them into {n_rules} rules by topic, with priorities and real examples.</p></li>
    <li><h3>It checks new answers</h3><p class="small">It checks every number against the customer's data, then the topic's rules. One broken rule means bad.</p></li>
  </ol>
</section>

<section>
  <h2>A real case from Plata's test set</h2>
  <p class="small">Topic: {case_topic}. Customer asks: “{case_q}”</p>
  <div class="case">
    <div class="panel"><span class="eyebrow">Conversation</span>{dialog}</div>
    <div class="panel"><span class="eyebrow">Customer data the bot could see</span>{ctx}</div>
  </div>
  <div class="panel">
    <div class="verdicts">
      <div class="v bad"><span class="who">Expert</span><b>Bad</b></div>
      <div class="v good"><span class="who">Gemma without training</span><b>Good</b><span class="note">Missed the mistake</span></div>
      <div class="v bad"><span class="who">Pinoqio</span><b>Bad</b><span class="note">Caught it</span></div>
    </div>
    <p class="numbers"><b>In numbers:</b> {numbers}</p>
    <div class="caught"><span class="eyebrow">Why Pinoqio said bad</span><p>{case_reason}</p><ul>{violated}</ul></div>
  </div>
</section>

<section>
  <h2>The expert's rules Pinoqio found</h2>
  <p class="small">Left: priority, 1 = most serious (wrong money or product terms). Right: how many real marked examples stand behind the rule.{check_note}</p>
  <div class="topics">{rules}</div>
</section>

<section>
  <h2>Try it on your own task</h2>
  <div class="howto">
    <div class="panel"><h3>1. Data</h3><p class="small">CSV or JSONL: <span class="mono">item_id, topic, context, conversation, label</span>. The label is <span class="mono">good</span> or <span class="mono">bad</span> from your expert. Works for support bots, moderation, any expert review.</p></div>
    <div class="panel"><h3>2. Learn the rules</h3><pre>python pipeline.py adapt \\
  --train train.jsonl --artifacts out/</pre><p class="small">You get the rules in <span class="mono">rulebook.json</span> and an explanation in <span class="mono">explanation.md</span>.</p></div>
    <div class="panel"><h3>3. Check new answers</h3><pre>python pipeline.py eval \\
  --test new.jsonl --artifacts out/ \\
  --out predictions.csv</pre><p class="small">Every conversation gets a label and the broken rule.</p></div>
  </div>
  <p class="small">Open source, MIT license: <a href="{repo}">{repo}</a>, folder <span class="mono">judge/</span>. Gemma 4 via the Gemini API, key in <span class="mono">GEMINI_API_KEY_JUDGE</span>.</p>
</section>

</div>
"""

if __name__ == "__main__":
    main(*sys.argv[1:5])
