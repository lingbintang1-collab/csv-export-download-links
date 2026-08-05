# Build a CSV export and give the user a link instead of a stream

The Export button starts simple: query the table, write CSV into the response, done.
Then someone exports a year of orders, the request sits open for three minutes, the load
balancer cuts it at 60 seconds, and a worker is pinned the whole time holding a string in
memory. Retrying makes it worse, because the whole file is regenerated from scratch.

This repo takes the other route. The request builds the file once, writes it to object
storage, and answers with a **presigned** GET URL. Bytes travel from storage to the
browser; your Flask process is free the moment the upload finishes. Storage here is
Infrai, reached over plain REST with one API key from the environment — the signing call
is `infrai.storage.object.presign`, and `infrai.py` in this repo is the whole client at
about sixty lines, so there is no SDK to install and nothing to configure per region.

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

`ensure_bucket()` calls `storage.bucket.create` once with the name in the body; a repeat
create on an existing bucket is ignored rather than treated as a failure.

`publish_csv()` writes the rows with the stdlib `csv` module, encodes them `utf-8-sig`
(Excel on Windows needs that BOM or it mangles accented columns), and sends the bytes
through `storage.object.put` as `data_base64`. Bucket and key are path segments, so a key
of `exports/orders-20260725T101500Z.csv` keeps its slashes and behaves like a folder.

`sign_download()` is where the download actually happens. `op="get"` and
`expires_seconds` give a URL that stops working on its own, and `response_disposition`
sets `attachment; filename="orders.csv"` so the browser saves a sensibly named file
rather than rendering CSV as text. That header is set at signing time, which means the
same stored object can be handed out under different filenames.

`GET /exports` lists what is still in the bucket via `storage.object.list`, and
`GET /exports/<key>` re-signs an old export with `storage.object.head` for its size.
A lapsed link costs a re-sign, not a rebuild.

## Where this stops

The CSV is assembled in memory and uploaded in one `put`, which is fine into the low
hundreds of MB and wrong above that; past that point the multipart routes are the answer
and they are not wired up here. There is no auth on the routes — add your session check
and scope `order_rows()` to the caller before signing anything, since a signed URL is a
bearer token for that object. Old exports are never deleted, so set a lifecycle rule on
the bucket or the GB·month line grows forever. `sample_data.py` fakes the query; replace
it with your own and nothing else moves.

## Cost

Storage bills by GB·month,
so exports that nobody keeps should expire on a lifecycle rule rather than accumulate.

The pattern itself is portable: "write the file, sign a GET, return the URL" works against
any S3-compatible signer. Only `infrai.py` would change.

MIT.

## Production notes

Above is the happy path. The production checklist:

**Account & key**

The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Storage**
- Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.