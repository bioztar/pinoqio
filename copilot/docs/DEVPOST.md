# Pinoqio: Devpost submission text

**Tagline:** The negotiation copilot whose nose grows when theirs should.

**Links:** live demo https://pinoqio.pro7ocol.com · code https://github.com/bioztar/pinoqio (MIT)

**Tracks:** Gemma 4 · ElevenLabs · open source

## Inspiration

In a negotiation, the facts are in the conversation, but nobody has the spare attention to hold them. The supplier says forty thousand at minute one and forty-eight at minute two, and you only notice on the way home. We wanted a teammate with perfect memory sitting in the call, who never gets tired and never gets distracted by the next thing you want to say. The Pinocchio nose is the interface: you read a call at a glance instead of reading a dashboard.

## What it does

Pinoqio joins your Teams call as a silent listener. It transcribes both sides in real time, keeps a ledger of every number and promise the other side makes, and checks each new statement against what came before.

- A native always-on-top window shows a Pinocchio nose that grows with a live deception-cue score, with evidence chips underneath: the two clashing quotes, the number that changed, the question that was dodged, the hedging phrases, and vocal shifts against that person's own baseline.
- A short whisper in your earpiece suggests what to ask next ("Price changed. Ask why.").
- Once per call, when a contradiction is near-certain, Pinoqio says it out loud in the meeting: "Sorry to jump in. Earlier you said forty thousand, now forty-eight. Which one is it?"
- When the call ends you get a summary: commitments, open questions, red flags with quotes, and a draft follow-up email.

Try it without keys on the web demo, which replays a scripted supplier call (voiced with ElevenLabs TTS) that was run once through the real pipeline and recorded. "Try live" runs your own mic and a shared browser tab through the same pipeline (passcode-gated, 5 minute cap).

## How we built it

- **Ears.** ElevenLabs Scribe Realtime (`scribe_v2_realtime`) over two websockets, one per speaker, with VAD-committed segments. Call audio is captured through BlackHole. Praat (parselmouth) extracts pitch, and we derive speech rate, pause ratio, filler count and response latency, each scored as a z-score against that speaker's own running baseline.
- **Brain.** Gemma 4 26B-A4B through the Gemini API reads every counterparty utterance with the transcript and the ledger, and returns strict JSON: contradiction with verbatim quotes, number drift, evasion, hedging, ledger updates and a suggested next question. A second model (DeepSeek-V4.1-Flash on Nebius) independently verifies every contradiction or number drift, and also serves as fallback analyst if Gemma errors or exceeds 8 s.
- **Score.** A small, readable logistic model. Verbal cues carry most of the weight; vocal cues are small and capped. The output is capped at 95% and every contribution becomes a chip that cites its evidence.
- **Face.** FastAPI + a websocket feed into a pywebview always-on-top window. The same UI runs in the browser for the web demo.
- **Voice.** ElevenLabs Flash v2.5 TTS to named output devices: a private earpiece for whispers, the call for the single interjection. The speak-or-stay-quiet policy is a pure function with unit tests.
- **Ship.** Four agent-driven lanes worked in parallel from a frozen event contract (`events.py`), 93 tests, Docker on a VPS behind Traefik.

## Challenges we ran into

- **Honesty about deception research.** The literature is humbling: pitch d ≈ 0.27 and latency d ≈ 0.18 (Sporer & Schwandt 2006), most nonverbal cues unreliable (DePaulo et al. 2003), and the best multimodal detectors reach about 65% (DOLOS, ICCV 2023). We did not want to ship a lie detector that lies. So the strongest signal is checkable text (contradictions and number changes), vocal cues are capped, and the score never reaches 100%.
- **False accusations.** Offers legitimately change in negotiations. We tuned the analyst for precision over recall, added a second model as verifier, and made the public interjection a question rather than a claim.
- **Latency.** Gemma 4 31B timed out at 40 s on our keys, so we use 26B-A4B (about 5 s per call with minimal thinking) and a time budget with a Nebius fallback so a slow call never stalls the pipeline.
- **Audio plumbing.** Routing call audio to a virtual device, keeping two Scribe sessions alive, and making the web "Try live" mode work from browser tab audio.

## Accomplishments that we're proud of

- On our scripted demo call, both planted contradictions are caught and verified by a second model at 0.95 confidence, and the public interjection fires at the right moment.
- Every number on screen traces back to a quote. No unexplained score.
- A working public demo and a clean multi-agent build: frozen contract, small PRs, 93 passing tests.

## What we learned

- The most trustworthy "lie" signal is boring: someone's own words against their own earlier words.
- A second model checking the first is cheap and removes most embarrassing false positives.
- Stating a tool's limits in the interface builds more trust than a bigger number.

## What's next

- Wire the voice policy into the desktop app's live loop (the engine and policy are built and tested; the auto-hook is the last step).
- Measure precision and recall on real negotiation transcripts instead of a scripted call.
- Windows support and native call-audio capture without a virtual device.
- Per-person baselines that persist across calls, and consent prompts for participants.

## Built with

Gemma 4 (26B-A4B, Gemini API) · ElevenLabs Scribe Realtime · ElevenLabs Flash v2.5 TTS · Nebius AI Studio (DeepSeek-V4.1-Flash) · Python 3.12 · FastAPI · pywebview · Praat / parselmouth · BlackHole · Docker · Traefik · uv
