# HANDOVER — pinoqio — 2026-10-24 16:30
## State: everything merged on main and clean (copilot #3-#47, judge #18 at 0.934). Web live at https://pinoqio.pro7ocol.com. MLH submitted (manually). Demo 16:45.
## Done this session
- Copilot lane complete (see coord/STATUS.md). Judge lane merged from PR #18 (partner's authorship kept).
- Plata fork: https://github.com/balalaka128/metalearning-llmaaj @ 03c9dbc893c48485a0ab170b04dd3b5b4de6ffb2 (public, code identical to judge/ on main). Docker tested: copilot/docs/judge-docker-report.md.
- Tidy: worktrees removed, merged branches deleted, PR #1 and issues #2/#14 closed.
## Open
- Plata: confirm the partner sent the organizers the fork URL + commit SHA (README "Submitting your solution"). Do not push to the fork after sending.
- Combined stage deck: needs the partner's generated runs/final/deck.html (judge/deck.py output, data stays local).
- Backup video: copilot/scripts/record_backup.sh on an unlocked Mac.
## Run the demo
1. `cd copilot && uv run python -m pinoqio.doctor`
2. `uv run python -m pinoqio.app --source live --voice public --demo-safe` (add `--art scene` for the partner's art, `PINOQIO_LANG=ru` for Russian lines)
3. Fallback: `--source replay --them-wav demo/replay/them.wav --me-wav demo/replay/me.wav`, or the web demo.
