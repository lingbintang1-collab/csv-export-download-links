"""Build a CSV out of rows, park it in storage, hand back a link that expires.

The web process never streams the file. It writes the object once and returns a
signed URL, so a slow client downloading 80 MB is storage's problem, not a worker
of yours held open for four minutes.
"""
import base64
import csv
import io
import os
import re
from datetime import datetime, timezone

import infrai

BUCKET = os.environ.get("EXPORT_BUCKET", "app-exports")
PREFIX = "exports/"
DEFAULT_TTL_SECONDS = 900


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "export"


def object_key(slug: str) -> str:
    """Timestamped key, so two people clicking Export at once don't overwrite each other."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{PREFIX}{slug}-{stamp}.csv"


def rows_to_csv(header, rows) -> bytes:
    """Rows in, CSV bytes out. utf-8-sig because Excel needs the BOM to read accents."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def ensure_bucket() -> None:
    """Idempotent setup. A repeat create is a no-op worth ignoring; a bad key will
    surface on the first put with a real error code rather than being hidden here."""
    try:
        infrai.storage.bucket.create(name=BUCKET, acl="private")
    except RuntimeError:
        pass


def sign_download(key: str, filename: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """A GET URL good for `ttl_seconds`. response_disposition is what turns an
    in-browser render into a Save-as dialog with a name a human recognises."""
    signed = infrai.storage.object.presign(
        BUCKET,
        key,
        op="get",
        expires_seconds=ttl_seconds,
        response_disposition=f'attachment; filename="{filename}"',
    )
    return signed.get("url", "")


def publish_csv(name, header, rows, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> dict:
    """Serialise, store, sign. Returns everything the caller needs to answer a request."""
    slug = slugify(name)
    payload = rows_to_csv(header, rows)
    key = object_key(slug)
    infrai.storage.object.put(
        BUCKET,
        key,
        data_base64=base64.b64encode(payload).decode("ascii"),
        content_type="text/csv; charset=utf-8",
    )
    return {
        "key": key,
        "rows": len(rows),
        "bytes": len(payload),
        "url_expires_seconds": ttl_seconds,
        "download_url": sign_download(key, f"{slug}.csv", ttl_seconds),
    }


def list_exports() -> list:
    """Past exports still in the bucket. Useful for an 'your downloads' page."""
    response = infrai.storage.object.list(BUCKET)
    objects = response.get("items", [])
    return [o for o in objects if str(o.get("key", "")).startswith(PREFIX)]


def describe_export(key: str) -> dict:
    """Object metadata without pulling the body down — size, type, whatever head reports."""
    return infrai.storage.object.head(BUCKET, key)
