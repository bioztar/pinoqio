"""Stage deck for the judge mode: one idea per slide, the speaker's line as the caption, numbers from a run.

    python deck.py runs/final runs/baseline_gemma-4-26b-a4b-it_orig data/plata/data/public_test.csv runs/final/deck.html [hero.jpg]
"""
import base64
import csv
import html
import json
import sys
from pathlib import Path

from pipeline import first_question
from report import TOPICS, in_numbers, read_preds, stats

esc = html.escape
REPO = "github.com/bioztar/pinoqio"
CONV_SOURCE = "input_en"  # Plata ships an English translation of every conversation; None = original language


LINES = [
    "I'm listening. So far it all adds up. Suspiciously so.",
    "A minute ago it was different. I'm not nitpicking, I just have a wooden memory.",
    "Two versions of one story. You're not lying, you're shipping updates. Without a changelog.",
    "Your story moves faster than the peso.",
    "The deposit is refundable, then it isn't. That's not a contract, that's a series with an open ending.",
    "I'd say 'I believe you', but my nose filed an appeal.",
    "You can see my nose from Montjuïc. The tour guides added it to the route.",
    "A sprout grew on my nose. Even nature thinks your story needs fertilizer.",
    "A sparrow built a nest and took out a mortgage. Says there'll be no truth here for thirty years.",
]
LIE_BUTTON = "Lie again"
WORDS = ("contradiction", "contradictions")


def b64(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


def puppet(frames):
    """Interactive Pinoqio: short-nose base photo, the long nose revealed segment by segment, three faces."""
    f = Path(frames)
    imgs = (f'<img class="pf" src="data:image/jpeg;base64,{b64(f / "frame-0.jpg")}" alt="Pinoqio on a Barcelona rooftop at dusk">'
            + "".join(f'<img class="pf face" data-face="{k}" src="data:image/jpeg;base64,{b64(f / f"expr-{k}.jpg")}" alt="">' for k in (1, 2))
            + f'<img class="pf nose" src="data:image/jpeg;base64,{b64(f / "frame-8.jpg")}" alt="">')
    return f'''<div class="puppet" id="puppet">{imgs}<div class="tip" id="tip" hidden></div>
      <div class="pcount" id="pcount">0</div><div class="pbubble" id="pbubble"><p id="pline"></p></div></div>
    <div class="pbar"><button type="button" id="plie">{esc(LIE_BUTTON)}</button><button type="button" id="preset">↺</button><span class="hint">click: the nose grows with every contradiction</span></div>
    <script>
    (() => {{
      const LINES = {json.dumps(LINES, ensure_ascii=False)};
      const REACH = [29.4, 36.5, 43.6, 50.7, 57.8, 64.9, 72, 83.5, 98];
      const P = document.getElementById("puppet");
      let n = 0;
      function set(v) {{
        n = Math.max(0, Math.min(8, v));
        P.style.setProperty("--reach", REACH[n] + "%");
        P.style.setProperty("--tip-y", (20.2 + (REACH[n] - 36.5) * 0.07).toFixed(2) + "%");
        document.getElementById("tip").hidden = n === 0 || n === 8;
        const face = n >= 6 ? 2 : n >= 3 ? 1 : 0;
        P.querySelectorAll(".face").forEach(i => i.classList.toggle("on", +i.dataset.face === face));
        document.getElementById("pcount").textContent = n;
        document.getElementById("pline").textContent = LINES[n];
        document.getElementById("plie").disabled = n === 8;
      }}
      document.getElementById("plie").addEventListener("click", () => set(n + 1));
      document.getElementById("preset").addEventListener("click", () => set(0));
      set(0);
    }})();
    </script>'''


def waffle(missed, total, cols=10):
    """One dot per bad answer in the test set: filled = caught, hollow red = missed."""
    r, gap = 9, 24
    rows = (total + cols - 1) // cols
    w, h = cols * gap, rows * gap
    dots = []
    for i in range(total):
        x, y = (i % cols) * gap + gap / 2, (i // cols) * gap + gap / 2
        cls = "miss" if i >= total - missed else "hit"
        dots.append(f'<circle cx="{x}" cy="{y}" r="{r}" class="{cls}"/>')
    return f'<svg viewBox="0 0 {w} {h}" class="waffle" role="img" aria-label="{total - missed} of {total} caught">{"".join(dots)}</svg>'


def topic_bars(before, after):
    w, lab, row, top = 720, 200, 54, 26
    sc = (w - lab - 60) / 100
    out = [f'<svg viewBox="0 0 {w} {top + row * 4 + 6}" class="bars" role="img" aria-label="Agreement with the expert by topic">']
    for pct in (0, 50, 100):
        x = lab + pct * sc
        out.append(f'<line x1="{x}" y1="{top - 8}" x2="{x}" y2="{top + row * 4}" class="grid"/><text x="{x}" y="{top - 13}" class="tick" text-anchor="middle">{pct}%</text>')
    for n, t in enumerate(TOPICS):
        y = top + n * row
        b, a = before[t] * 100, after[t] * 100
        out.append(f'<text x="0" y="{y + 25}" class="lab">{esc(TOPICS[t])}</text>'
                   f'<rect x="{lab}" y="{y + 6}" width="{b * sc:.1f}" height="13" rx="3" class="b0"/>'
                   f'<text x="{lab + b * sc + 7:.1f}" y="{y + 17}" class="v0">{b:.0f}%</text>'
                   f'<rect x="{lab}" y="{y + 23}" width="{a * sc:.1f}" height="17" rx="3" class="b1"/>'
                   f'<text x="{lab + a * sc + 7:.1f}" y="{y + 37}" class="v1">{a:.0f}%</text>')
    out.append("</svg>")
    return "".join(out)


def score_bars(pts0, pts1):
    """Plata's final score out of 12: 10 x accuracy + 0.4 x jury points (max 2.0)."""
    w, lab, sc = 720, 200, (720 - 200 - 20) / 12
    def row(y, name, acc, jury):
        s = f'<text x="0" y="{y + 26}" class="lab">{name}</text><rect x="{lab}" y="{y + 8}" width="{acc * sc:.1f}" height="26" rx="3" class="b1"/>'
        s += f'<text x="{lab + 10}" y="{y + 27}" class="in">{acc:.1f} accuracy</text>'
        if jury:
            s += (f'<rect x="{lab + acc * sc:.1f}" y="{y + 8}" width="{jury * sc:.1f}" height="26" rx="3" class="jury"/>'
                  f'<text x="{lab + (acc + jury) * sc + 8:.1f}" y="{y + 27}" class="v1">up to +{jury:.1f} jury</text>')
        return s
    ticks = "".join(f'<line x1="{lab + v * sc}" y1="0" x2="{lab + v * sc}" y2="104" class="grid"/>'
                    f'<text x="{lab + v * sc}" y="118" class="tick" text-anchor="middle">{v}</text>' for v in (0, 4, 8, 12))
    return (f'<svg viewBox="0 0 {w + 140} 124" class="bars" role="img" aria-label="Plata score out of 12">{ticks}'
            f'{row(4, "Gemma, no training", pts0, 0)}{row(54, "Pinoqio", pts1, 2.0)}</svg>')


def main(run_dir, base_dir, test_csv, out_path, hero=None):
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
    rules = [r for b in rulebook["topics"].values() for r in b["rules"]]
    rule_text = {r["id"]: r["rule"] for r in rules}

    order = list(TOPICS)
    caught = [i for i in gold if gold[i] == "bad" and base[i] == "good" and ours[i] == "bad" and reasons[i].get("violated")]
    caught.sort(key=lambda i: (order.index(topic_of[i]), len(test[i]["conversation"])))
    case = caught[0]
    # show Plata's English translation of the conversation on stage; fall back to the original
    try:
        conv = json.loads(test[case][CONV_SOURCE])["conversation"]
    except (KeyError, ValueError, TypeError):
        conv = json.loads(test[case]["conversation"])
    bot = [m["content"] for m in conv if m["role"] == "assistant"][-1]
    numbers = in_numbers(test[case], "English")
    violated = [v for v in reasons[case].get("violated", []) if v in rule_text]

    train_total = rulebook.get("train_total", 150)
    n_bad_train = sum(len(b["rules"]) for b in rulebook["topics"].values())
    showcase = []
    for t, b in rulebook["topics"].items():
        for r in b["rules"][:2]:
            showcase.append((TOPICS.get(t, t), r["id"], r["rule"]))
    rules_html = "".join(f'<li><span class="rid">{esc(rid)}</span><span class="rt">{esc(text)}</span><span class="tp">{esc(tp)}</span></li>'
                         for tp, rid, text in showcase)
    hero_tag = ""
    if hero and Path(hero).is_dir():
        hero_tag = puppet(hero)
    elif hero and Path(hero).exists():
        hero_tag = f'<img class="hero" src="data:image/jpeg;base64,{base64.b64encode(Path(hero).read_bytes()).decode()}" alt="Pinoqio, a wooden puppet in glasses, on a Barcelona rooftop at dusk, with a long nose">'
    pct = lambda x: f"{x * 100:.0f}%"
    pts0, pts1 = round(10 * s0["macro"], 1), round(10 * s1["macro"], 1)
    labels_dots = "".join(f'<i class="{"g" if k < 90 else "r"}"></i>' for k in range(150))

    page = TEMPLATE.format(
        hero=hero_tag, train_total=train_total, n_rules=len(rules), n_test=len(gold),
        before=pct(s0["macro"]), after=pct(s1["macro"]),
        missed0=s0["missed"], missed1=s1["missed"], bad_total=s1["bad_total"],
        fa0=s0["false_alarm"], fa1=s1["false_alarm"], good_total=s1["good_total"],
        waffle0=waffle(s0["missed"], s0["bad_total"]), waffle1=waffle(s1["missed"], s1["bad_total"]),
        topic_bars=topic_bars(s0["by_topic"], s1["by_topic"]), score_bars=score_bars(pts0, pts1),
        pts0=pts0, pts1=pts1, pts_max=round(pts1 + 2.0, 1),
        rules=rules_html, labels_dots=labels_dots,
        case_q=esc(first_question({"conversation": conv}, 160)), case_bot=esc(bot), case_numbers=esc(numbers),
        case_rule=esc(f"{violated[0]}: {rule_text[violated[0]]}" if violated else "Wrong facts"),
        repo=REPO,
    )
    Path(out_path).write_text(page, encoding="utf-8")
    print(out_path)


TEMPLATE = """<meta charset="utf-8">
<title>Pinoqio Judge</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,600;0,700;1,600&family=Golos+Text:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap">
<style>
/* Layout: a stage deck. One idea per full-height slide; the visual on top, the speaker's line as a big caption below.
   Single dark look by choice, to match the Pinoqio dusk photo. */
:root {{
  color-scheme: dark;
  --bg: #120f0c; --panel: #1d1813; --ink: #f3eadc; --muted: #b3a38c; --line: #3b3127;
  --wood: #d4924f; --wood-soft: #4a321d; --teal: #4fb3a6; --good: #6fcf97; --bad: #ff7b6b;
  --display: "Cormorant Garamond", Georgia, serif; --body: "Golos Text", -apple-system, sans-serif; --mono: "JetBrains Mono", Menlo, monospace;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-snap-type: y mandatory; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font: 400 18px/1.45 var(--body);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }}
.slide {{ min-height: 100vh; scroll-snap-align: start; max-width: 1200px; margin: 0 auto; padding-block: 5vh 6vh;
  display: grid; grid-template-rows: auto 1fr auto; gap: 3vh; }}
.kicker {{ font: 500 0.8rem/1 var(--mono); letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); display: flex; justify-content: space-between; }}
.kicker b {{ color: var(--teal); font-weight: 500; }}
.visual {{ display: flex; flex-direction: column; justify-content: center; gap: 2.5vh; min-width: 0; }}
.say {{ font: 600 clamp(1.7rem, 3.6vw, 3rem)/1.12 var(--display); text-wrap: balance; max-width: 30ch; border-left: 4px solid var(--wood); padding-left: 1.2rem; }}
.say em {{ color: var(--wood); font-style: italic; }}
h1 {{ margin: 0; font: 700 clamp(2.4rem, 5.4vw, 4.6rem)/0.95 var(--display); letter-spacing: -0.02em; }}
h1 em {{ color: var(--teal); }}
.sub {{ font-size: clamp(1.1rem, 2vw, 1.5rem); color: var(--muted); max-width: 40ch; }}
.puppet {{ position: relative; aspect-ratio: 3 / 2; width: min(100%, 50vh * 1.5); border-radius: 14px; overflow: hidden; --nose-left: 29.4%; --reach: 29.4%; --tip-y: 20%;
  transition: --reach 0.75s cubic-bezier(.2, 1.35, .4, 1), --tip-y 0.75s cubic-bezier(.2, 1.35, .4, 1); }}
@property --reach {{ syntax: "<percentage>"; inherits: true; initial-value: 29.4%; }}
@property --tip-y {{ syntax: "<percentage>"; inherits: true; initial-value: 20%; }}
.pf {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
.pf.face {{ opacity: 0; transition: opacity 0.6s;
  -webkit-mask-image: radial-gradient(ellipse 12% 19% at 25% 15%, #000 72%, transparent 100%); mask-image: radial-gradient(ellipse 12% 19% at 25% 15%, #000 72%, transparent 100%); }}
.pf.face.on {{ opacity: 1; }}
.pf.nose {{ -webkit-mask-image: linear-gradient(to bottom, transparent 6%, #000 10.5%, #000 25%, transparent 30%),
    linear-gradient(to right, transparent var(--nose-left), #000 calc(var(--nose-left) + 0.5%), #000 calc(var(--reach) - 1.4%), transparent var(--reach));
  mask-image: linear-gradient(to bottom, transparent 6%, #000 10.5%, #000 25%, transparent 30%),
    linear-gradient(to right, transparent var(--nose-left), #000 calc(var(--nose-left) + 0.5%), #000 calc(var(--reach) - 1.4%), transparent var(--reach));
  -webkit-mask-composite: source-in; mask-composite: intersect; }}
.tip {{ position: absolute; left: calc(var(--reach) - 1.9%); top: calc(var(--tip-y) - 1.55%); width: 1.25%; height: 3.1%; border-radius: 50%;
  background: repeating-radial-gradient(circle at 45% 45%, #d9a46a 0 9%, #b8793f 9% 14%), #c88a4c;
  box-shadow: inset -2px -2px 4px rgba(70, 36, 12, 0.55), 2px 2px 6px rgba(0, 0, 0, 0.25); transition: opacity 0.3s; }}
.tip[hidden] {{ display: block !important; opacity: 0; }}
.pcount {{ position: absolute; left: 3%; bottom: 4%; font: 700 clamp(2.5rem, 6vw, 5rem)/0.8 var(--display); text-shadow: 0 4px 20px rgba(0,0,0,0.6); }}
.pbubble {{ position: absolute; right: 3%; bottom: 5%; max-width: 52%; background: rgba(18,14,11,0.75); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(243,234,220,0.2); border-radius: 16px 16px 4px 16px; padding: 0.7rem 1rem; }}
.pbubble p {{ margin: 0; font: 600 clamp(1rem, 1.9vw, 1.5rem)/1.2 var(--display); }}
.pbar {{ display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap; }}
.pbar button {{ font: 600 1rem/1 var(--body); border-radius: 8px; padding: 0.7rem 1.1rem; cursor: pointer; border: 1px solid var(--line); background: var(--panel); color: var(--ink); }}
.pbar #plie {{ background: var(--teal); border-color: var(--teal); color: #08201d; }}
.pbar button:focus-visible {{ outline: 2px solid var(--teal); outline-offset: 3px; }}
.pbar .hint {{ color: var(--muted); font-size: 0.95rem; }}
.hero {{ width: 100%; max-width: 100%; aspect-ratio: 3 / 2; object-fit: cover; object-position: 50% 18%; border-radius: 14px; max-height: 44vh; }}
/* slide 2 */
.dots {{ display: grid; grid-template-columns: repeat(25, 1fr); gap: 6px; max-width: 760px; }}
.dots i {{ aspect-ratio: 1; border-radius: 50%; }}
.dots i.g {{ background: var(--good); }} .dots i.r {{ background: var(--bad); }}
.legend {{ display: flex; gap: 1.5rem; flex-wrap: wrap; color: var(--muted); font-size: 1rem; }}
.legend span::before {{ content: ""; display: inline-block; width: 0.8rem; height: 0.8rem; border-radius: 50%; margin-right: 0.45rem; vertical-align: -1px; background: var(--c); }}
.question {{ font: 600 clamp(1.4rem, 2.6vw, 2.2rem)/1.2 var(--display); color: var(--muted); }}
.question b {{ color: var(--ink); }}
/* slide 3 */
.flow {{ display: grid; grid-template-columns: 1fr auto 1fr auto 1fr; align-items: stretch; gap: 1rem; }}
.step {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 1.3rem; display: flex; flex-direction: column; gap: 0.6rem; }}
.step .n {{ font: 700 2.4rem/1 var(--display); color: var(--wood); }}
.step h3 {{ margin: 0; font: 600 1.35rem/1.2 var(--body); }}
.step p {{ margin: 0; color: var(--muted); font-size: 1rem; }}
.arrow {{ align-self: center; font: 700 2.5rem/1 var(--display); color: var(--wood); }}
.chip {{ font: 500 0.85rem/1.3 var(--mono); background: var(--wood-soft); color: var(--wood); border-radius: 6px; padding: 0.35rem 0.5rem; }}
/* slide 4 */
.rules {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.8rem 1.4rem; }}
.rules li {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 0.8rem 1rem; display: grid; grid-template-columns: auto 1fr; gap: 0.2rem 0.7rem; font-size: 1rem; }}
.rid {{ font: 500 0.8rem/1.6 var(--mono); color: var(--wood); }}
.tp {{ grid-column: 2; font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }}
/* slide 5 */
.case {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 1.2rem; }}
.bubble {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 1.1rem 1.2rem; display: flex; flex-direction: column; gap: 0.6rem; }}
.who {{ font: 500 0.75rem/1 var(--mono); letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }}
.bubble p {{ margin: 0; font-size: 1.05rem; }}
.bubble p.num {{ font: 600 clamp(1.3rem, 2.2vw, 1.9rem)/1.25 var(--display); color: var(--wood); }}
.verdicts {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.8rem; }}
.v {{ border-radius: 12px; padding: 0.9rem 1rem; display: flex; flex-direction: column; gap: 0.2rem; }}
.v b {{ font: 700 1.8rem/1 var(--display); }}
.v.bad {{ background: #3a1d19; color: var(--bad); }} .v.good {{ background: #16301f; color: var(--good); }}
.v small {{ color: var(--ink); opacity: 0.7; font-size: 0.9rem; }}
/* slide 6 */
.big {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; }}
.big > div {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 1.1rem 1.2rem; }}
.big .k {{ font: 500 0.75rem/1 var(--mono); letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }}
.big .x {{ font: 700 clamp(2.4rem, 5vw, 4rem)/1.05 var(--display); font-variant-numeric: tabular-nums; margin-top: 0.4rem; }}
.big .x s {{ color: var(--muted); text-decoration: none; font-size: 0.6em; }}
.pair {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 2rem; }}
.pair figure {{ margin: 0; display: flex; flex-direction: column; gap: 0.6rem; }}
.pair figcaption {{ color: var(--muted); font-size: 1rem; }}
.pair figcaption b {{ color: var(--ink); }}
.waffle {{ width: 100%; max-width: 340px; height: auto; }}
.waffle .hit {{ fill: var(--wood); }} .waffle .miss {{ fill: none; stroke: var(--bad); stroke-width: 2.5; }}
.bars {{ width: 100%; max-width: 820px; height: auto; display: block; }}
.bars .grid {{ stroke: var(--line); }} .bars .tick {{ fill: var(--muted); font: 500 12px var(--mono); }}
.bars .lab {{ fill: var(--ink); font: 500 16px var(--body); }}
.bars .b0 {{ fill: #5a4d40; }} .bars .b1 {{ fill: var(--wood); }} .bars .jury {{ fill: var(--teal); opacity: 0.85; }}
.bars .v0 {{ fill: var(--muted); font: 500 12px var(--mono); }} .bars .v1 {{ fill: var(--ink); font: 600 14px var(--mono); }}
.bars .in {{ fill: #1b130b; font: 600 13px var(--mono); }}
.two {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 2rem; align-items: center; }}
pre {{ margin: 0; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 1rem 1.1rem; font: 500 0.95rem/1.6 var(--mono); overflow-x: auto; }}
.nav {{ position: fixed; right: max(16px, env(safe-area-inset-right, 0px)); bottom: calc(14px + env(safe-area-inset-bottom, 0px)); font: 500 0.8rem/1 var(--mono); color: var(--muted); }}
@media (max-width: 800px) {{ .flow {{ grid-template-columns: 1fr; }} .arrow {{ transform: rotate(90deg); justify-self: center; }}
  .rules, .case, .pair, .two, .big, .verdicts {{ grid-template-columns: 1fr; }} .dots {{ grid-template-columns: repeat(15, 1fr); }} }}
</style>

<section class="slide" id="s1">
  <div class="kicker"><span>Pinoqio · judge mode</span><b>Plata track</b></div>
  <div class="visual">
    <h1>A judge that learns <em>from the expert</em></h1>
    {hero}
  </div>
  <p class="say">People lie. But <em>bots make mistakes</em> too.</p>
</section>

<section class="slide" id="s2">
  <div class="kicker"><span>The problem</span><b>1 / 7</b></div>
  <div class="visual">
    <div class="dots" aria-label="150 conversations: 90 marked good, 60 marked bad">{labels_dots}</div>
    <div class="legend"><span style="--c: var(--good)">90 marked good</span><span style="--c: var(--bad)">60 marked bad</span><span>by Plata's expert</span></div>
    <p class="question">The rules behind these marks: <b>written nowhere.</b></p>
  </div>
  <p class="say">Only an expert can check these answers. <em>His rules are in his head.</em></p>
</section>

<section class="slide" id="s3">
  <div class="kicker"><span>How it works</span><b>2 / 7</b></div>
  <div class="visual">
    <div class="flow">
      <div class="step"><span class="n">1</span><h3>Expert marks</h3><p>{train_total} conversations: good or bad. No rules written.</p><span class="chip">label: bad</span></div>
      <div class="arrow" aria-hidden="true">→</div>
      <div class="step"><span class="n">2</span><h3>Pinoqio finds the rules</h3><p>For every bad answer: what is wrong, and what general rule is behind it.</p><span class="chip">{n_rules} rules, 4 topics</span></div>
      <div class="arrow" aria-hidden="true">→</div>
      <div class="step"><span class="n">3</span><h3>Judges like the expert</h3><p>Checks numbers against the customer data, then the rules. One broken rule: bad.</p><span class="chip">verdict + rule id</span></div>
    </div>
  </div>
  <p class="say">We gave Pinoqio {train_total} marked answers. <em>It found the expert's rules by itself.</em></p>
</section>

<section class="slide" id="s4">
  <div class="kicker"><span>The rules Pinoqio found</span><b>3 / 7</b></div>
  <div class="visual"><ul class="rules">{rules}</ul></div>
  <p class="say">For example: <em>a transfer to your own account is not spending.</em></p>
</section>

<section class="slide" id="s5">
  <div class="kicker"><span>A real case from Plata's test</span><b>4 / 7</b></div>
  <div class="visual">
    <div class="case">
      <div class="bubble"><span class="who">Customer</span><p>{case_q}</p><span class="who">Bank bot</span><p>{case_bot}</p></div>
      <div class="bubble"><span class="who">In numbers</span><p class="num">{case_numbers}</p><span class="who">Rule</span><p>{case_rule}</p></div>
    </div>
    <div class="verdicts">
      <div class="v bad"><span class="who">Expert</span><b>Bad</b></div>
      <div class="v good"><span class="who">Gemma, no training</span><b>Good</b><small>missed the mistake</small></div>
      <div class="v bad"><span class="who">Pinoqio</span><b>Bad</b><small>caught it, named the rule</small></div>
    </div>
  </div>
  <p class="say">The bot made a mistake with the money. <em>Gemma said good. Pinoqio said bad.</em></p>
</section>

<section class="slide" id="s6">
  <div class="kicker"><span>Results on {n_test} new conversations</span><b>5 / 7</b></div>
  <div class="visual">
    <div class="big">
      <div><span class="k">Agreement with the expert</span><div class="x"><s>{before} →</s> {after}</div></div>
      <div><span class="k">Bot mistakes missed</span><div class="x"><s>{missed0} →</s> {missed1} <s>of {bad_total}</s></div></div>
      <div><span class="k">False alarms</span><div class="x"><s>{fa0} →</s> {fa1} <s>of {good_total}</s></div></div>
    </div>
    <div class="pair">
      <figure>{waffle0}<figcaption><b>Gemma, no training.</b> Each dot is one bad answer; hollow = missed.</figcaption></figure>
      <figure>{waffle1}<figcaption><b>Pinoqio, same model + learned rules.</b></figcaption></figure>
    </div>
  </div>
  <p class="say">Same model. With the rules, Pinoqio misses <em>half as many</em> bad answers.</p>
</section>

<section class="slide" id="s7">
  <div class="kicker"><span>By topic and by Plata's score</span><b>6 / 7</b></div>
  <div class="visual">
    {topic_bars}
    {score_bars}
  </div>
  <p class="say">Plata's score: <em>{pts0} → {pts1}</em> for accuracy, plus up to 2 points for the explanation it writes itself.</p>
</section>

<section class="slide" id="s8">
  <div class="kicker"><span>Try it on your task</span><b>7 / 7</b></div>
  <div class="visual two">
    <pre>python pipeline.py adapt \\
  --train labels.jsonl --artifacts out/

python pipeline.py eval \\
  --test new.jsonl --artifacts out/ \\
  --out predictions.csv</pre>
    <div class="step"><h3>Open source, MIT</h3><p>{repo}, folder judge/. Gemma 4. Works for support bots, moderation, any expert review. You get the rules as text, and every verdict names a rule.</p></div>
  </div>
  <p class="say">It is open source. <em>Plata can try it today</em>, on any task with an expert.</p>
</section>

<div class="nav" aria-hidden="true">← → or scroll</div>
<script>
(() => {{
  const slides = [...document.querySelectorAll(".slide")];
  const current = () => slides.reduce((best, s, i) => Math.abs(s.getBoundingClientRect().top) < Math.abs(slides[best].getBoundingClientRect().top) ? i : best, 0);
  addEventListener("keydown", e => {{
    const k = e.key;
    if (!["ArrowRight", "ArrowDown", "PageDown", " ", "ArrowLeft", "ArrowUp", "PageUp"].includes(k)) return;
    e.preventDefault();
    const step = ["ArrowLeft", "ArrowUp", "PageUp"].includes(k) ? -1 : 1;
    const next = Math.max(0, Math.min(slides.length - 1, current() + step));
    slides[next].scrollIntoView({{ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }});
  }});
}})();
</script>
"""

if __name__ == "__main__":
    main(*sys.argv[1:6])
