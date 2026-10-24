import httpx
import pytest

from pinoqio import nebius


REAL_CLIENT = httpx.AsyncClient


def patch_client(monkeypatch, handler):
    monkeypatch.setattr(nebius.httpx, "AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(nebius.config, "nebius_key", lambda: "k")
    monkeypatch.setattr(nebius.config, "nebius_base_url", lambda: "https://example.test/v1/")


def ok(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


async def test_request_shape_and_parse(monkeypatch):
    seen = {}

    def handler(req):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], req.read()
        return ok('{"a": 1}')

    patch_client(monkeypatch, handler)
    assert await nebius.ask_json("p", "s", "m/x") == {"a": 1}
    assert seen["url"] == "https://example.test/v1/chat/completions" and seen["auth"] == "Bearer k"
    assert b'"temperature":0' in seen["body"].replace(b" ", b"") and b"json_object" in seen["body"]


async def test_retries_once_on_429_then_succeeds(monkeypatch):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(429) if len(calls) == 1 else ok("{}")

    patch_client(monkeypatch, handler)
    assert await nebius.ask_json("p") == {}
    assert len(calls) == 2


async def test_fails_after_second_5xx(monkeypatch):
    patch_client(monkeypatch, lambda req: httpx.Response(503))
    with pytest.raises(nebius.NebiusError):
        await nebius.ask_json("p")


async def test_4xx_not_retried_and_bad_json_raises(monkeypatch):
    calls = []
    patch_client(monkeypatch, lambda req: (calls.append(1), httpx.Response(400))[1])
    with pytest.raises(nebius.NebiusError):
        await nebius.ask_json("p")
    assert len(calls) == 1
    patch_client(monkeypatch, lambda req: ok("not json"))
    with pytest.raises(nebius.NebiusError):
        await nebius.ask_json("p")


def test_short_name():
    assert nebius.short_name("deepseek-ai/DeepSeek-V4.1-Flash") == "DeepSeek"
    assert nebius.short_name("Qwen/Qwen3-235B-A22B-Instruct-2507") == "Qwen3"
