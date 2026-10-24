"""Web mode: uv run python -m pinoqio.web. Same UI as the desktop app, plus a top bar and a recorded-call demo.

Every browser connection gets its own session. The demo replays demo/replay/events.jsonl, so it costs no API calls.
"""
import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse

from pinoqio import live, record
from pinoqio.server import UI_FILE

log = logging.getLogger("pinoqio.web")
BAR_FILE = UI_FILE.parent / "web_bar.html"
REPLAY_DIR = Path(__file__).resolve().parents[1] / "demo" / "replay"


def render_index(live: bool) -> str:
    bar = BAR_FILE.read_text(encoding="utf-8").replace("{{LIVE}}", "true" if live else "false")
    return UI_FILE.read_text(encoding="utf-8").replace("<body>", "<body>\n" + bar, 1)


def create_web_app(replay_dir: Path = REPLAY_DIR, live_passcode: str | None = None, live_pipeline=None) -> FastAPI:
    events = record.load(replay_dir / "events.jsonl")
    app = FastAPI()
    index = render_index(live=bool(live_passcode))

    @app.get("/", response_class=HTMLResponse)
    async def root() -> str:
        return index

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    @app.get("/demo/call.mp3")
    async def call_audio() -> FileResponse:
        return FileResponse(replay_dir / "call.mp3", media_type="audio/mpeg")

    @app.websocket("/demo")
    async def demo(sock: WebSocket) -> None:
        await sock.accept()
        try:
            await sock.receive_text()  # the browser sends "start" when its audio starts playing
            await record.play(events, sock.send_json)
            await sock.send_json({"type": "end"})
            await sock.close()
        except WebSocketDisconnect:
            pass

    if live_passcode:
        live_state = live.LiveState()

        @app.websocket("/live")
        async def live_ws(sock: WebSocket) -> None:
            await live.run_session(sock, live_passcode, live_state, live_pipeline or live.real_pipeline)

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    app = create_web_app(live_passcode=os.environ.get("PINOQIO_LIVE_PASSCODE") or None)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), log_level="info")


if __name__ == "__main__":
    main()
