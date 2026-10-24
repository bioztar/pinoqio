# AGENTS.md: how agents work in this repo

Two humans (Vitaly and his partner) each drive coding agents (Claude Code or any other harness). The agents never talk to each other directly. **This repository is the shared channel.** Read this file first, every session.

## Lanes and ownership
| Lane | Directory | Human owner | Branch prefix |
|---|---|---|---|
| Pinoqio, the call copilot | `copilot/` | Vitaly | `copilot/` |
| Plata judge track | `judge/` | Partner (Vitaly reviews) | `judge/` |
| Shared contracts and docs | `shared/`, `README.md`, this file | both, by agreement | `shared/` |

Only touch files in your lane. If you need a change in another lane, open a GitHub issue labelled with that lane and stop.

## Protocol
1. **Session start:** `git pull --rebase`, then read `coord/STATUS.md` and open issues (`gh issue list`).
2. **One task = one branch = one PR into `main`.** Small PRs. Never push to `main` directly. The lane's human merges (squash).
3. **Status:** after every meaningful step, update your lane's block in `coord/STATUS.md`: one line of what's done, what's next and blockers, plus a timestamp. Commit it with your work.
4. **Decisions** that affect the other lane (API contract, shared dependency, Gemma quota use) go in `coord/DECISIONS.md` (append only, dated, who decided).
5. **Questions to the other side:** open a GitHub issue, assign the other human, label it `question`. Don't wait on it; work around it and note it in STATUS.
6. **Secrets:** keys live only in a local `.env` (gitignored). See `.env.example`. Never print, log or commit a key value. The judge lane uses its own key (`GEMINI_API_KEY_JUDGE`) so it never uses up the copilot's Gemma quota.
7. **Shared resources:** reuse `shared/` (Gemini client wrapper, ElevenLabs client, logging) rather than duplicating them. Changing a shared module needs a PR that both humans see.

## Timeline (24 Oct 2026)
11:30 start · 12:00 copilot go/no-go · 14:00 cold-start demo run · 15:00 feature freeze · 16:00 repo public check (license, no secrets) · 16:15 hard freeze + tag · 16:45 demos.
