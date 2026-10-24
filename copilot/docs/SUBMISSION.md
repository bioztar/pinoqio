# MLH submission: Hacktoberfest Hack Day Barcelona

Event slug: `hacktoberfest-hack-day-barcelona`. Deadline: Oct 24, 6:00 PM CEST.

## Name
Pinoqio

## One-line pitch (short_description)
The negotiation copilot whose nose grows when theirs should: live contradiction, dodge and voice-stress detection on any Mac call, with the evidence on screen and the big contradictions said out loud.

## Description
Pinoqio listens to a live negotiation call (Teams, Meet, Zoom: any Mac call app) on two separate channels, so it always knows who said what. ElevenLabs Scribe Realtime transcribes both sides; every counterparty line is analysed by Gemma 4 for contradictions with verbatim quotes, numbers that drift from what was promised, dodged questions and hedging, while local prosody analysis compares their pitch, pauses, speech rate, fillers and time-to-answer against their own baseline. An open-source second model (DeepSeek-V4.1-Flash on Nebius) double-checks every contradiction, answers when Gemma is slow, and writes the post-call summary.

The result is a lie probability per answer, capped at 95% because it is a nudge, not a verdict, shown as a Pinocchio whose nose grows and shrinks with it, plus a claim check ("Probably false · 74%: pitch up, slow to answer"), then/now quotes, a promise ledger and an "ask this next" suggestion in a floating window. In public mode Pinoqio says each real contradiction out loud into the call with ElevenLabs TTS ("Earlier you said 40,000, now 48,000. Which one is it?"); in private mode it stays silent and only shows the evidence.

Honest numbers on 56 scripted negotiation lines: contradictions 100% precision / 88% recall, any-flag recall 88%, and 25% of honest lines still get flagged (copilot/eval/report.md).

The same repo holds a second lane for the Plata Bank challenge: a judge that learns an expert's labelling rules from examples (`judge/`), with a learned rulebook and a jury-ready explanation: macro topic accuracy 0.814 zero-shot to 0.934 on Plata's public test, packaged as Plata's Docker `adapt`/`eval` contract.

## Technologies
Python 3.12, uv, FastAPI, uvicorn, WebSockets, pywebview, sounddevice, BlackHole (virtual audio), Praat/parselmouth, NumPy, Docker, Traefik; Google Gemma 4 (gemma-4-26b-a4b-it via the Gemini API, google-genai SDK); ElevenLabs Scribe v2 Realtime (speech-to-text) and ElevenLabs Flash v2.5 TTS; Nebius Token Factory with DeepSeek-V4.1-Flash and Qwen3-30B-A3B (open-weights models).

## Links
- GitHub: https://github.com/bioztar/pinoqio
- Live demo: https://pinoqio.pro7ocol.com (replay demo; "Try live" behind a passcode)
- extra_links:
  - Architecture slide: https://github.com/bioztar/pinoqio/blob/main/copilot/docs/architecture-slide.png
  - Eval report: https://github.com/bioztar/pinoqio/blob/main/copilot/eval/report.md
  - Plata judge (lane): https://github.com/bioztar/pinoqio/tree/main/judge

## ai_tools
- claude-code
- coding:anthropic/claude-opus-5.5

## Prize categories (sponsor_usage)
- **Best Use of Gemma 4:** Gemma 4 26B A4B is the analyst on every counterparty line: it extracts claims and numbers into a promise ledger, finds contradictions with verbatim quotes, flags dodges and hedging, and suggests the next question. The Plata judge lane also runs on Gemma 4 with a rulebook it learns from the expert's labels.
- **Best Open-Source AI Project:** MIT-licensed, public repo with both lanes; the second opinion runs on open-weights models (DeepSeek-V4.1-Flash, Qwen3-30B on Nebius), prosody is local, and the eval set and report are published so anyone can reproduce the numbers.
- **A Judge That Learns from an Expert (Plata Bank Challenge):** The `judge/` lane learns Plata's expert labelling rules in `adapt` (explains every bad example, merges them into a per-topic rulebook with priorities and evidence item_ids, self-checks on train) and applies them in `eval`; macro topic accuracy 0.814 zero-shot to 0.934 on the public test, shipped as Plata's Docker contract with a jury explanation generated from the same rulebook.
- **Best Use of ElevenLabs:** ElevenLabs is both ears and voice: Scribe v2 Realtime transcribes each call channel live, and Flash v2.5 TTS lets Pinoqio say a verified contradiction out loud into the call or whisper a cue into the user's earpiece.
