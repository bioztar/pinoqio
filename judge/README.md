# Pinoqio judge: a judge that learns from an expert

Entry for Plata's "A Judge That Learns from an Expert" track. Part of [Pinoqio](../README.md), MIT license.

The expert's rules are written nowhere; they live in the labels. `adapt` reads the labeled training
conversations, writes the expert's rules down as a per-topic rulebook, and `eval` grades new conversations
with those rules. Any violated rule makes a conversation `bad`. Model: Gemma 4 via the Gemini API.

## How it works

`adapt` (training set only):
1. For every `bad` conversation, Gemma explains what exactly the expert objected to and states it as a general rule.
2. Per topic, the explanations are merged into 4-10 rules with priorities and the ids of the training examples behind each rule.
3. A topic-balanced sample of the training set is re-judged with the rules; disagreements with the expert become the "boundaries" section.
4. Saves to `/artifacts`:
   - `rulebook.json`: the rules, used verbatim by `eval`;
   - `prompts/<topic>.txt`: the exact system prompt `eval` sends for each topic;
   - `examples.jsonl`: labeled training conversations used as precedents;
   - `explanation.md`: **the explanation for the jury**, rendered from `rulebook.json`.

`eval`: for each test conversation, the topic's rules go into the prompt; optionally (`JUDGE_PRECEDENTS=1`) also the 2 most similar `bad` and 2 most similar `good`
training conversations (local TF-IDF, no extra API calls) go into the prompt. Output: `/output/predictions.csv`.

## Run with Docker

```sh
cd judge
docker build -t pinoqio-judge .
docker run --rm -e GEMINI_API_KEY -v "$PWD/in:/input" -v "$PWD/artifacts:/artifacts" pinoqio-judge adapt
docker run --rm -e GEMINI_API_KEY -v "$PWD/in:/input" -v "$PWD/artifacts:/artifacts" -v "$PWD/out:/output" pinoqio-judge eval
```

`in/` holds `train.jsonl` for `adapt` and `test.jsonl` for `eval`, as produced by Plata's `prepare_inputs.py`.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | required | Gemini API key. `GEMINI_API_KEY_JUDGE` or `GOOGLE_API_KEY` also work. |
| `JUDGE_MODEL` | `gemma-4-26b-a4b-it` | Model for `eval` and the self-check. `gemma-4-31b-it` works too and falls back to 26B on server errors; on the free tier it returned 500 for hours, so all reported runs use 26B. |
| `JUDGE_TEACHER_MODEL` | `gemma-4-26b-a4b-it` | Model that explains bad examples and writes the rules. |
| `JUDGE_RPM` | `14` | Request rate limit; the Gemma free tier allows about 15 per minute. |
| `JUDGE_WORKERS` | `6` | Parallel requests. |
| `JUDGE_SELF_CHECK_PER_TOPIC` | `12` | Training conversations per topic re-judged for the boundaries section. |
| `JUDGE_PRECEDENTS` | `0` | `1` adds the 2+2 most similar labeled training conversations to each `eval` prompt (0.881 vs 0.894 without on the public test, so off by default). They are always used as the fallback label when the API fails. |

Requests: about one per `bad` training example, one per topic, one per self-check example and one per test
example. At 14 requests per minute, `adapt` on 150 examples takes about 8 minutes and `eval` on 80 about 6.

## Results on Plata's public split

| | macro_topic_accuracy | bad answers missed |
|---|---|---|
| Gemma 4 26B A4B, plain prompt | 0.814 | 13 of 30 |
| Pinoqio rulebook (final run) | 0.934 | 4 of 30 |

Plata's data goes in `judge/data/` and is never committed (see `.gitignore`). Score locally with Plata's
scorer: `./score.sh runs/<run>`. `report.py` builds the one-page stage report from a run.
