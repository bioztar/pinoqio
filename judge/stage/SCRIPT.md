# Plata track: stage script (judge mode)

Open `deck.html` in any browser (works offline, images inside). Next slide: → or scroll.
The screen number is in the top-right corner of every slide. The title slide plays by itself.

| Screen | Say |
|---|---|
| Title (Pinoqio plays by itself) | People contradict themselves. Bots do too. And when the topic is money, a mistake is expensive. |
| 1 / 7 (150 dots) | Plata's expert marked 150 bot answers: good or bad. His rules are written nowhere. |
| 2 / 7 (three steps) | We gave these marks to Pinoqio. It found the expert's rules by itself. |
| 3 / 7 (rules) | For example: a transfer to your own account is not spending. |
| 4 / 7 (real case) | The bot said: you spent 6,600. The truth is 5,100. Gemma said "good". Pinoqio said "bad", and named the rule. |
| 5 / 7 (dots) | Agreement with the expert: from 81 to 93 percent. Missed mistakes: from 13 to 4. |
| 6 / 7 (charts) | In Plata's score: 9.3 for accuracy, plus points for the explanation it writes itself. |
| 7 / 7 (code + Pinoqio) | Pinoqio catches lies in people and mistakes in bots. Open source. Plata can try it today. |

Short on time: Title → 4/7 → 5/7 → 7/7.

Plata submission: fork https://github.com/balalaka128/metalearning-llmaaj, commit `03c9dbc893c48485a0ab170b04dd3b5b4de6ffb2`, public test macro_topic_accuracy 0.934.
