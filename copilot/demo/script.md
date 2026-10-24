# Demo script: the supplier call (~2.5 min)

Buyer = Vitaly (`me`, MacBook mic). Supplier = partner (`them`, Teams audio).
Scenario: buyer wants 500 industrial LED panels. Read naturally, no acting. Short lines.

Line format (parsed by `make_replay.py`; keep it):
`N. **ROLE** [gap_s]: text`, where `gap_s` is the silence before the line.
Lines starting with `>` are stage notes, not spoken.

## 1. Small talk (baseline: supplier relaxed, steady pace)

> Supplier: normal speed, no hesitation. Pinoqio learns the baseline here.

1. **BUYER** [0.5]: Hi Marco, thanks for making time today.
2. **SUPPLIER** [0.8]: Hi, good to talk. How was your week?
3. **BUYER** [0.6]: Busy, but good. Yours?
4. **SUPPLIER** [0.8]: Same here. Lots of orders, lots of coffee.
5. **BUYER** [0.6]: Ha. Let's talk about the LED panels, five hundred units.

## 2. The anchors (price and delivery stated)

> Supplier: confident, clear. These are the numbers Pinoqio will hold him to.

6. **SUPPLIER** [0.8]: Sure. For five hundred units, the price is forty thousand euros.
7. **BUYER** [0.6]: Forty thousand. Good. And delivery?
8. **SUPPLIER** [0.8]: We can deliver by the middle of March.
9. **BUYER** [0.6]: Middle of March. Great, that works for us.

## 3. The dodge (direct question, non-answer)

> Supplier: pause a beat too long, then wander. Say "um". Never give a number.

10. **BUYER** [0.6]: One more thing. What is your defect rate on this model?
11. **SUPPLIER** [2.4]: Um, well, it depends on how you count it, really.
12. **SUPPLIER** [0.4]: Our quality team is very experienced, and customers are happy.
13. **BUYER** [0.6]: Understood, but what is the actual percentage?
14. **SUPPLIER** [1.8]: We can send you documents later. Let's move on, there is more to cover.

## 4. Contradiction 1: the price moves (public interjection fires here)

> Supplier: a long pause before the lie, slightly faster speech, a little higher.
> Expected: Pinoqio's voice cuts in on the call after line 17 (once per session).

15. **BUYER** [0.6]: Okay. So we agree on the order. Can you confirm the final price?
16. **SUPPLIER** [2.2]: Yes. With the, um, new material costs, it comes to forty-eight thousand.
17. **BUYER** [0.8]: Forty-eight? You said forty earlier.

> Pause for Pinoqio's interjection (about 4 s). Let it finish before speaking.

18. **SUPPLIER** [4.5]: Right. Well, the quote I gave first was only a rough estimate.

## 5. Contradiction 2: the delivery date moves

> Supplier: again hesitate before the date, then sound breezy.

19. **BUYER** [0.8]: Fine, let's keep talking. And the delivery stays mid-March?
20. **SUPPLIER** [2.4]: Actually, we are looking at the end of April, because of shipping.
21. **BUYER** [0.6]: April. That is six weeks later than you said.
22. **SUPPLIER** [1.2]: Things change. These dates are never really fixed.

## 6. Honest closing (baseline returns, probability drops)

> Supplier: relaxed again, normal pace.

23. **BUYER** [0.8]: I appreciate the honesty. I need the defect rate in writing.
24. **SUPPLIER** [0.9]: That is fair. I will send you the test report tomorrow.
25. **BUYER** [0.6]: And a firm price and date, in the same email.
26. **SUPPLIER** [0.9]: Yes, I will put both in writing.
27. **BUYER** [0.6]: Thank you, Marco. Talk tomorrow.
28. **SUPPLIER** [0.7]: Thank you. Have a good day.
