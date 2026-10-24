# Pinoqio art: the character, the growing nose, the voice

Original character (not based on Disney's 1940 design; Collodi's story is public domain): a carved wooden puppet in
glasses, a teal turtleneck and a charcoal jacket, on a Barcelona rooftop at dusk. Images generated for this project.

| File | What |
|---|---|
| `index.html` | Self-contained player: the nose grows one segment per contradiction (0..8), the face goes calm → suspicious → smug, a sprout appears at 7 and a sparrow's nest at 8. |
| `frames/frame-0.jpg`, `frames/frame-8.jpg` | Short nose / full-length nose, same shot. The player reveals the long nose segment by segment. |
| `frames/expr-1.jpg`, `frames/expr-2.jpg` | Same shot, suspicious and smug faces (blended in around the head). |
| `concept.jpg` | Key art for slides and the README. |
| `lines.json` | Pinoqio's sarcastic lines, Russian and English: one per nose stage, plus interjections with `{then}` / `{now}` quotes. |

## Drive it from the live mode

```html
<iframe id="pq" src="/static/pinoqio-art/index.html?embed" style="width:100%;aspect-ratio:3/2;border:0"></iframe>
<script>
  const pq = () => document.getElementById("pq").contentWindow.pinoqio;
  // the copilot's lie probability 0..1 (same scale as setProb in copilot/pinoqio/ui/index.html)
  pq().setLevel(0.6);
  // or count contradictions: pq().lie();  pq().setLies(3);
  // show the copilot's own line in the bubble
  pq().say("Two minutes ago it was \"refundable\". Now it's \"non-refundable\".");
</script>
```

`?embed` hides the header and the buttons. Same-origin is needed for `contentWindow` access, so serve the folder from the copilot's static route.
