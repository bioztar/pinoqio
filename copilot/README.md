# copilot/

Pinoqio, the negotiation copilot whose nose grows when theirs should. Project overview, demo link and honest limits are in the [root README](../README.md); module-level design is in [docs/architecture.md](docs/architecture.md); the Devpost text is in [docs/DEVPOST.md](docs/DEVPOST.md).

Run from this folder with `uv run`.

```
uv sync
uv run pytest                                  # 93 tests
uv run python -m pinoqio.app --source fake     # scripted call, no keys
uv run python -m pinoqio.web                   # web demo on :8000
```

Keys come from the repo-root `.env` (see `../.env.example`): `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `NEBIUS_API_KEY`.
Set `PINOQIO_ENV_FILE` to load a different file.

Lane contract: `pinoqio/events.py` is frozen; change it only through its own PR.
