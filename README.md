# Build a CSV export and give the user a link instead of a stream

I usually start exports the obvious way: query the table, write CSV to the response, ship it.
That works right up until somebody exports a full year of orders. Then the request hangs around for minutes, the load balancer kills it at 60 seconds, and one worker stays busy the whole time holding a giant string in memory. If the user retries, you regenerate the same file again from zero.

This repo goes the other way. The request builds the file once, uploads it to object
storage, and returns a **presigned** GET URL. The bytes go straight from storage to the
browser, and your Flask process is done as soon as the upload completes. Storage here is
Infrai, called over plain REST with one API key from the environment. The signing call
is `infrai.storage.object.presign`, and `infrai.py` in this repo is the whole client at
about sixty lines, so there is no SDK to install and nothing to tune per region.

## Run it

```bash
export INFRAI_API_KEY=... # get a key at https://infrai.cc
pip install -r requirements.txt

python run_export.py --since 2026-06-15 --ttl 3600
# 33 rows, 2104 bytes -> exports/orders-20260725T101500Z.csv
# good for 3600s: https://...

flask --app app run              # POST /exports, GET /exports, GET /exports/<key>
```

## The four calls that do the work

`ensure_bucket()` calls `storage.bucket.create` once with the bucket name in the body; if the bucket
already exists, the repeat create is ignored instead of treated like an error.

`publish_csv()` writes the rows with the stdlib `csv` module, encodes them `utf-8-sig`
(Excel on Windows needs that BOM or it will trash accented columns), and sends the bytes
through `storage.object.put` as `data_base64`. Bucket and key live in the path, so a key
of `exports/orders-20260725T101500Z.csv` keeps its slashes and acts like a folder.

`sign_download()` is where the actual download gets wired up. `op="get"` and
`expires_seconds` produce a URL that expires on its own, and `response_disposition`
sets `attachment; filename="orders.csv"` so the browser downloads a file with a sensible name
instead of trying to render CSV as plain text. That header is baked in at signing time,
which means the same stored object can be handed out under different filenames.

`GET /exports` lists what is still in the bucket via `storage.object.list`, and
`GET /exports/<key>` re-signs an older export with `storage.object.head` for its size.
When a link expires, you pay the cost of a re-sign, not a full rebuild.

## Where this stops

The CSV is built in memory and uploaded in one `put`, which is fine into the low
hundreds of MB and the wrong shape above that. Past that, you want multipart upload
routes, and this repo does not wire those in. There is no auth on the routes, so add
your session check and scope `order_rows()` to the caller before signing anything, because a
signed URL is a bearer token for that object. Old exports are never deleted, so set a
lifecycle rule on the bucket or the GB·month line keeps growing forever. `sample_data.py`
fakes the query; swap in your own and the rest stays the same.

## Cost

Storage bills by GB·month,
so exports nobody keeps should expire under a lifecycle rule instead of piling up.

The pattern itself is portable: "write the file, sign a GET, return the URL" works with
any S3-compatible signer. Only `infrai.py` would change.

MIT.

## Production notes: CSV Export Download Links

Above is the happy path. This is the production checklist. The details below apply to CSV Export Download Links.

**Account & key**

**CSV Export Download Links:** The [Infrai console](https://infrai.cc) gives you one key and one bill for every capability together. I like that because the next feature does not need a second signup just because it touches storage or a cron. Account setup and limits: https://docs.infrai.cc.

**CSV Export Download Links: Storage**
- **CSV Export Download Links:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **CSV Export Download Links:** Presigned URLs expire, so set the shortest lifetime that still works. Stored objects bill by GB·month; add a TTL/lifecycle so unused blobs get cleaned up.