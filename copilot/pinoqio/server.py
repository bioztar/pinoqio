"""FastAPI face server: serves the UI, pushes Utterances/Verdicts over /ws, accepts /interject."""
import asyncio
import contextlib
import dataclasses
import inspect
import logging
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pinoqio.events import Utterance, Verdict
from pinoqio.summary import Summary, summarize

log = logging.getLogger("pinoqio.server")
UI_FILE = Path(__file__).parent / "ui" / "index.html"
ART_DIR = Path(__file__).resolve().parents[2] / "shared" / "pinoqio-art"  # partner's scene player


def to_json(event: Utterance | Verdict | Summary) -> dict:
    kind = {Utterance: "utterance", Summary: "summary"}.get(type(event), "verdict")
    return {"type": kind, **dataclasses.asdict(event)}


class Hub:
    """Fan-out of events to websocket clients; late joiners get the full history replayed."""

    def __init__(self) -> None:
        self._history: tuple[dict, ...] = ()
        self._subs: set[asyncio.Queue] = set()

    @property
    def history(self) -> tuple[dict, ...]:
        return self._history

    def publish(self, event: Utterance | Verdict | Summary) -> None:
        msg = to_json(event)
        self._history = (*self._history, msg)
        for q in self._subs:
            q.put_nowait(msg)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        for msg in self._history:
            q.put_nowait(msg)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)


class InterjectBody(BaseModel):
    text: str


async def default_interject(text: str) -> None:
    """Call the voice lane's hook if it has landed; otherwise just log."""
    try:
        from pinoqio import voice
        hook = voice.interject
    except (ImportError, AttributeError):
        log.info("interject (voice lane not merged, stub): %s", text)
        return
    result = hook(text)
    if inspect.isawaitable(result):
        await result


def create_app(
    source: Callable[[Hub], AsyncIterator[Utterance | Verdict]] | None = None,
    interject: Callable[[str], object] = default_interject,
) -> FastAPI:
    """`source(hub)` yields events to publish; it gets the hub in case it needs to tee."""
    hub = Hub()

    async def pump() -> None:
        try:
            async for event in source(hub):
                hub.publish(event)
        except Exception:
            log.exception("event source died")

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI):
        task = asyncio.create_task(pump()) if source else None
        yield
        if task:
            task.cancel()

    app = FastAPI(lifespan=lifespan)
    app.state.hub = hub
    app.mount("/static", StaticFiles(directory=UI_FILE.parent / "static"), name="static")
    if ART_DIR.is_dir():  # repo checkout only; the web image has no shared/
        app.mount("/art", StaticFiles(directory=ART_DIR), name="art")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return UI_FILE.read_text(encoding="utf-8")

    @app.post("/interject")
    async def post_interject(body: InterjectBody) -> dict:
        try:
            result = interject(body.text)
            if inspect.isawaitable(result):
                await result
        except Exception:
            log.exception("interject failed")
            return {"ok": False}
        return {"ok": True}

    @app.post("/summary")
    async def post_summary() -> dict:
        """The Summary button: summarise the call so far and push it to every client."""
        s = await summarize(hub.history)
        if s is None:
            return {"ok": False}
        hub.publish(s)
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(sock: WebSocket) -> None:
        await sock.accept()
        q = hub.subscribe()
        try:
            while True:
                await sock.send_json(await q.get())
        except WebSocketDisconnect:
            pass
        finally:
            hub.unsubscribe(q)

    return app
