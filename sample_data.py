"""Stand-in for whatever you actually query. Swap these two names for your ORM call
and the rest of the repo does not change: exporter only wants a header and rows.
"""
from datetime import date, timedelta

ORDER_HEADER = ["order_id", "placed_on", "customer", "region", "items", "total_eur"]

_CUSTOMERS = [
    ("Ravensburg Kliniken", "DE"),
    ("Atelier Noé", "FR"),
    ("Kōbe Shoten", "JP"),
    ("Praxis Almeida", "PT"),
    ("Northwind Tooling", "GB"),
]


def order_rows(since: str | None = None) -> list:
    """Deterministic rows so the demo output is stable. `since` filters on placed_on
    (ISO date string) the way a real WHERE clause would."""
    start = date(2026, 6, 1)
    rows = []
    for index in range(48):
        customer, region = _CUSTOMERS[index % len(_CUSTOMERS)]
        placed_on = start + timedelta(days=index // 2)
        rows.append([
            f"ORD-{4100 + index}",
            placed_on.isoformat(),
            customer,
            region,
            1 + (index % 7),
            round(38.5 + index * 4.25, 2),
        ])
    if since:
        rows = [r for r in rows if r[1] >= since]
    return rows
