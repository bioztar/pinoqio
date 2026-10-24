#!/bin/sh
# Score a run directory with Plata's own evaluator. Usage: ./score.sh runs/<run>
cd "$(dirname "$0")" && python3 data/plata/src/evaluate.py --test data/plata/data/public_test.csv \
  --predictions "$1/predictions.csv" --out "$1/score.json" | python3 -c "
import json,sys; r=json.load(sys.stdin)
print(f\"macro_topic_accuracy={r['score']:.3f} acc={r['accuracy']:.3f} kappa={r['kappa']:.3f} cm={r['confusion_matrix']}\")
for t,v in r['by_topic'].items(): print(f'  {t:20s} {v[\"accuracy\"]:.3f} ({v[\"correct\"]}/{v[\"n\"]})')"
