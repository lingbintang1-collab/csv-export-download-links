"""One-shot export from the shell — the same code path the HTTP route uses.

    python run_export.py --since 2026-06-15 --ttl 3600

Handy for a nightly report you mail to someone: run it from cron, paste the URL
into the message body, let the link expire on its own.
"""
import argparse

from exporter import DEFAULT_TTL_SECONDS, ensure_bucket, list_exports, publish_csv
from sample_data import ORDER_HEADER, order_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an orders CSV and print a download link.")
    parser.add_argument("--since", help="only rows placed on or after this ISO date")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS, help="link lifetime in seconds")
    parser.add_argument("--list", action="store_true", help="show exports already in the bucket")
    args = parser.parse_args()

    ensure_bucket()

    if args.list:
        for obj in list_exports():
            print(obj.get("key"))
        return

    result = publish_csv("orders", ORDER_HEADER, order_rows(args.since), ttl_seconds=args.ttl)
    print(f"{result['rows']} rows, {result['bytes']} bytes -> {result['key']}")
    print(f"good for {result['url_expires_seconds']}s: {result['download_url']}")


if __name__ == "__main__":
    main()
