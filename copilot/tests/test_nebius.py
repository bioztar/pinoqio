import json

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


async def test_chain_moves_to_next_model_at_once_on_5xx(monkeypatch):
    sleeps, models = [], []
    monkeypatch.setattr(nebius.asyncio, "sleep", lambda s: sleeps.append(s))

    def handler(req):
        model = json.loads(req.read())["model"]
        models.append(model)
        return httpx.Response(503, text="overloaded") if len(models) == 1 else ok('{"a": 2}')

    patch_client(monkeypatch, handler)
    monkeypatch.setattr(nebius.config, "nebius_model", lambda: "deepseek-ai/DeepSeek-V4.1-Flash")
    data, used = await nebius.ask_json_model("p")
    assert data == {"a": 2} and used == nebius.FALLBACK_MODEL
    assert models == ["deepseek-ai/DeepSeek-V4.1-Flash", nebius.FALLBACK_MODEL] and sleeps == []


async def test_chain_second_pass_recovers_from_gateway_burst(monkeypatch):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503, text="<html>503") if len(calls) <= 2 else ok('{"a": 3}')

    patch_client(monkeypatch, handler)
    monkeypatch.setattr(nebius, "ROUND_PAUSE_S", 0)
    assert await nebius.ask_json("p") == {"a": 3}
    assert len(calls) == 3  # both models 503, then first model of the second pass answers


async def test_chain_error_names_status_and_body_snippet_not_key(monkeypatch):
    patch_client(monkeypatch, lambda req: httpx.Response(429, text="rate limited"))
    with pytest.raises(nebius.NebiusError) as e:
        await nebius.ask_json("p")
    assert "http 429" in str(e.value) and "rate limited" in str(e.value) and "k" != str(e.value)


async def test_explicit_model_has_no_chain(monkeypatch):
    models = []

    def handler(req):
        models.append(json.loads(req.read())["model"])
        return httpx.Response(503)

    patch_client(monkeypatch, handler)
    async def nosleep(s):
        return None

    monkeypatch.setattr(nebius.asyncio, "sleep", nosleep)
    with pytest.raises(nebius.NebiusError):
        await nebius.ask_json("p", model="only/this")
    assert models == ["only/this", "only/this"]


def test_short_name():
    assert nebius.short_name("deepseek-ai/DeepSeek-V4.1-Flash") == "DeepSeek"
    assert nebius.short_name("Qwen/Qwen3-235B-A22B-Instruct-2507") == "Qwen3"
