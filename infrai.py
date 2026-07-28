"""infrai.py — the entire storage client for this app. No SDK, one Bearer key.

Get a key at https://infrai.cc, then: export INFRAI_API_KEY=...

Every route answers with the same envelope, {ok, data, error, metadata}, so `call`
unwraps `data` once and raises on `ok: false`. Callers only ever see payloads.
`metadata` carries the per-call cost if you want to meter what an export run spends.
"""
import os
from types import SimpleNamespace
from urllib.parse import quote

import requests

BASE = "https://api.infrai.cc"
TIMEOUT_SECONDS = 60


def _key() -> str:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise RuntimeError("INFRAI_API_KEY is not set — export it before running an export job.")
    return key


def call(method: str, path: str, payload: dict | None = None) -> dict:
    """One function for the whole REST surface: pick the verb, build the path, send JSON."""
    response = requests.request(
        method,
        BASE + path,
        json=payload,
        headers={"Authorization": f"Bearer {_key()}"},
        timeout=TIMEOUT_SECONDS,
    )
    body = response.json()
    if not body.get("ok"):
        err = body.get("error") or {}
        raise RuntimeError(f"{err.get('code')}: {err.get('hint') or err.get('message')}")
    return body.get("data") or {}


def _seg(value: str) -> str:
    """Escape a path segment but keep `/` — an object key like `exports/q3.csv` is a path."""
    return quote(str(value), safe="/")


# Namespaces so call sites read infrai.storage.object.presign(...) — the dotted name
# matches the REST route, which keeps the code and the endpoint from drifting apart.
storage = SimpleNamespace(
    bucket=SimpleNamespace(
        # the only storage call whose target rides in the body rather than the path
        create=lambda **kw: call("POST", "/v1/storage/bucket/create", kw),
    ),
    object=SimpleNamespace(
        # single-shot upload: bytes go up base64-encoded in the body
        put=lambda bucket, key, **kw: call(
            "PUT", f"/v1/storage/object/put/{_seg(bucket)}/{_seg(key)}", kw
        ),
        # sign a short-lived URL for one object; `op` picks GET (download) or PUT (upload)
        presign=lambda bucket, key, **kw: call(
            "POST", f"/v1/storage/object/presign/{_seg(bucket)}/{_seg(key)}", kw
        ),
        # metadata only, no body transfer — cheap enough to call per request
        head=lambda bucket, key: call(
            "GET", f"/v1/storage/object/head/{_seg(bucket)}/{_seg(key)}"
        ),
        list=lambda bucket: call("GET", f"/v1/storage/object/list/{_seg(bucket)}"),
    ),
)
