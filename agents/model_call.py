"""Model transport for the autoinsight loop: cassette-first, fail-closed.

A request is served from a recorded cassette in ``data/model_cassettes/`` keyed by
request hash, else via an explicit live call, else it fails loudly with
``CassetteMiss`` (no invented text). Every call -- hit, live, or miss -- is
appended to a usage log with model id, tier, hash, and timestamp.

Live calls require ``BLINDSPOT_LIVE=1`` plus ``META_MODEL_API_KEY``. The
endpoint defaults to the documented Meta Model API chat-completions URL
(``https://api.meta.ai/v1/chat/completions``, per dev.meta.ai) and can be
overridden with ``META_MODEL_API_URL``. The live backend POSTs the OpenAI
chat-completions shape (``{"model", "messages": [{role, content}]}``) with
``Authorization: Bearer <key>`` and reads ``choices[0].message.content``
(a bare ``{"text"}`` response body is also accepted). Contributor-tier note:
prompts sent live must be public aggregates only; the anonymized prompts
the autoinsight prompt builder produces qualify.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import urllib.request

DEFAULT_MODEL = "muse-spark-1.2-contributor"
DEFAULT_URL = "https://api.meta.ai/v1/chat/completions"


class CassetteMiss(Exception):
    """No recorded cassette and no live transport for this request."""


def canonical_hash(request: dict) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()


def _log(usage_path: pathlib.Path, entry: dict) -> None:
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    log = json.loads(usage_path.read_text()) if usage_path.exists() else []
    log.append(entry)
    usage_path.write_text(json.dumps(log, indent=1) + "\n")


def _live_post(url: str, key: str, payload: dict, timeout_s: int = 180) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode())


def _extract_text(body: dict) -> str | None:
    if isinstance(body.get("text"), str):
        return body["text"]
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def complete(
    prompt: str,
    model: str = DEFAULT_MODEL,
    cassettes_dir: str | pathlib.Path = "data/model_cassettes",
    usage_path: str | pathlib.Path = "meta_usage.json",
    record: bool = False,
) -> dict:
    """Complete one anonymized prompt. Returns {"text","model","source","request_hash"}."""
    request = {"model": model, "prompt": prompt}
    digest = canonical_hash(request)
    usage_path, cassettes_dir = map(pathlib.Path, (usage_path, cassettes_dir))
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()

    cassette = cassettes_dir / f"{digest}.json"
    if cassette.exists() and not record:
        saved = json.loads(cassette.read_text())
        _log(usage_path, {"ts": stamp, "request_hash": digest, "model": model,
                           "hit": True, "source": "cassette"})
        return {"text": saved["response"]["text"], "model": model,
                "source": "cassette", "request_hash": digest}

    if os.environ.get("BLINDSPOT_LIVE") == "1" and os.environ.get("META_MODEL_API_KEY"):
        url = os.environ.get("META_MODEL_API_URL") or DEFAULT_URL
        chat = {"model": model,
                "messages": [{"role": "user", "content": prompt}]}
        body = _live_post(url, os.environ["META_MODEL_API_KEY"], chat)
        text = _extract_text(body) if isinstance(body, dict) else None
        if not text:
            raise CassetteMiss("live transport returned no readable text; refusing to invent one")
        cassettes_dir.mkdir(parents=True, exist_ok=True)
        cassette.write_text(json.dumps({"request": request, "response": {"text": text},
                                                 "recorded_at": stamp, "model": model,
                                                 "url": url}) + "\n")
        _log(usage_path, {"ts": stamp, "request_hash": digest, "model": model,
                           "hit": True, "source": "live-recorded"})
        return {"text": text, "model": model,
                "source": "live-recorded", "request_hash": digest}

    _log(usage_path, {"ts": stamp, "request_hash": digest, "model": model,
                      "hit": False, "source": "miss",
                      "live_key_present": bool(os.environ.get("META_MODEL_API_KEY"))})
    raise CassetteMiss(
        f"no cassette for request {digest[:16]}... (model={model!r}); "
        "record one with BLINDSPOT_LIVE=1 plus META_MODEL_API_KEY and "
        "META_MODEL_API_URL, or run the pipeline with --model-round off")
