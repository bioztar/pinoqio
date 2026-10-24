# Pinoqio · demo script
Partner = buyer on the laptop · Vitaly = seller on the phone · ~4 min

## 0 · Setup before going on stage
- **Laptop:** Teams: Speaker **Pinoqio Out** (laptop speakers + BlackHole), Mic **MacBook Air Microphone**. Volume up. Do Not Disturb on.
- **Laptop:** `cd ~/DEV/pinoqio/copilot && uv run python -m pinoqio.doctor`
- **Phone:** Vitaly joins the Teams call, stands a few metres from the laptop.
- **Laptop:** `uv run python -m pinoqio.app --source live --voice public --demo-safe` (add `--art scene` for the rooftop Pinoqio)

## 1 · Opening 0:20
- **Partner (to audience):** Negotiations are full of numbers. Nobody tracks them all live. This is Pinoqio. It sits in your call and its nose grows when the other side's story doesn't add up. Let's call our supplier.

## 2 · The call 2:30
- **Buyer:** Hello! How are you?
- **Seller:** Hi! Busy, but good. Lots of orders this month.
- **Pinoqio:** Silent. Nose small, ~12%. It is learning the seller's normal voice.

- **Buyer:** I need 200 laptops. What is the price?
- **Seller:** For 200 units, it's nine hundred euros each, delivery included.
- **Pinoqio (screen):** Promise ledger: unit price 900 €, delivery included. _(wait 5 s)_

- **Buyer:** When is delivery?
- **Seller:** Two weeks from the order, guaranteed.
- **Pinoqio (screen):** Ledger: delivery 2 weeks. _(wait 5 s)_

- **Buyer:** What is the warranty?
- **Seller:** _(pause, vague)_  Well… it depends on the model. Our support is really very good, many clients are happy.
- **Pinoqio (screen):** “Dodged” chip, nose grows a notch, “Ask this next” suggests a direct question. _(wait 5 s)_

- **Buyer:** OK. What is the total price?
- **Seller:** Sure. Two hundred times one thousand fifty, plus delivery.
- **Pinoqio (OUT LOUD):** BOING! Something like: “Two minutes ago it was ‘nine hundred euros each, delivery included’. Now it's ‘one thousand fifty, plus delivery’. I'm not arguing, I'm just taking minutes.” _(let it finish, then 3 s)_

- **Buyer:** Delivery is two weeks?
- **Seller:** Actually, more like five or six weeks, with the current stock.
- **Pinoqio (OUT LOUD):** Second line, e.g. “‘Two weeks, guaranteed’ and ‘five or six weeks’: a lovely duet. Shame they're singing different songs.” _(let it finish)_

- **Buyer:** Is this your final price?
- **Seller:** _(slower, small pause, a bit higher voice)_  Yes… yes, that's our final price. Really, we can't go lower.
- **Pinoqio (screen only):** Claim check: “Probably false · ~70%”: pitch up, slow to answer, hedging. Nose long, SPROING! _(partner points at it)_

- **Buyer:** And payment?
- **Seller:** _(calm, clear)_  Net thirty days from delivery, same as always.
- **Pinoqio (screen):** Stays low: “Probably true”. It doesn't cry wolf.

- **Buyer:** OK. Please send it by email. Thank you!
- **Seller:** Will do. Have a good day!
- **Partner:** Click **Summary**: what changed (900 → 1,050, 2 → 5-6 weeks), red flags with quotes, and the next email to send.

## 3 · Wrap the demo 0:20
- **Partner (to audience):** Every flag comes with the quote behind it. Gemma 4 reads every line, an open-source model on Nebius double-checks it, ElevenLabs hears and speaks. It's a nudge, not a lie detector: on our test set it catches 7 of 8 contradictions with zero false ones.

## 4 · Slides 1:00
- **Laptop:** Open `copilot/docs/stage.html`, press → to build.

  1. **How it works**: 4 clicks, the nose grows with each stage. “Hear the call → read the signals (Gemma 4 + voice) → double-check (DeepSeek on Nebius) → act: nose, voice, web.”
  1. → once more: **Pinoqio as a judge** (partner's part). “Same idea for bots: a judge that learns an expert's rules from labelled examples. Plata's track: 0.814 → 0.934, Docker adapt/eval.”
  1. Close: “Try it at pinoqio.pro7ocol.com. MIT, fork it today.”

## If it breaks
- **No transcript of the seller:** Teams speaker is not Pinoqio Out. Fix it, the app keeps running.
- **Nose doesn't move:** Models slow. Keep talking; DeepSeek takes over within ~8 s.
- **Nothing at all:** Close the window, run the recording: `uv run python -m pinoqio.app --source replay --them-wav demo/replay/them.wav --me-wav demo/replay/me.wav --voice public` or open pinoqio.pro7ocol.com → Play demo.

Phone version: https://pinoqio.pro7ocol.com/static/script.html
