# judge/: a judge that learns from an expert (Plata track)

Goal: match Plata's expert labels on the hidden test while keeping cost and latency low.

Plan:
1. Split the labeled data into train / val / holdout (stratified by label).
2. Baseline: a plain prompt on Gemma 4 26B A4B, scored with Plata's metric script.
3. Rule mining: collect disagreements with the expert, have a teacher model propose rules, keep a rule only if it raises the val score. Output: `rulebook.md`.
4. Add 3-6 nearest labeled examples to the prompt.
5. Cascade: low-confidence cases go to Gemma 4 31B. Pick the threshold on the quality/cost curve.

Plata's data goes in `judge/data/` and is never committed (see `.gitignore`).
