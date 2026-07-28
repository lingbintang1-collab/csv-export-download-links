"""HTTP surface for exports.

    POST /exports          build a fresh CSV, return a link
    GET  /exports          list the ones still in the bucket
    GET  /exports/<key>    re-sign an old export whose link has lapsed

No auth here on purpose — put this behind whatever session check the rest of your
app uses, and scope the rows in order_rows() to the caller before signing anything.
"""
from flask import Flask, jsonify, request

from exporter import (
    BUCKET,
    DEFAULT_TTL_SECONDS,
    describe_export,
    ensure_bucket,
    list_exports,
    publish_csv,
    sign_download,
)
from sample_data import ORDER_HEADER, order_rows

app = Flask(__name__)


def _ttl(raw, fallback: int = DEFAULT_TTL_SECONDS) -> int:
    """Clamp the requested lifetime: a link that lives for a week is a leak."""
    try:
        return max(60, min(int(raw), 24 * 3600))
    except (TypeError, ValueError):
        return fallback


@app.post("/exports")
def create_export():
    body = request.get_json(silent=True) or {}
    ensure_bucket()
    rows = order_rows(body.get("since"))
    result = publish_csv("orders", ORDER_HEADER, rows, ttl_seconds=_ttl(body.get("ttl_seconds")))
    return jsonify(result), 201


@app.get("/exports")
def index_exports():
    return jsonify({"bucket": BUCKET, "exports": list_exports()})


@app.get("/exports/<path:key>")
def resign_export(key: str):
    ttl = _ttl(request.args.get("ttl_seconds"))
    filename = key.rsplit("/", 1)[-1]
    return jsonify({
        "key": key,
        "object": describe_export(key),
        "url_expires_seconds": ttl,
        "download_url": sign_download(key, filename, ttl),
    })


if __name__ == "__main__":
    app.run(port=5000, debug=True)
