"""Generate deterministic Northwind Retail Group CSV fixtures."""

from __future__ import annotations

import csv
import logging
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "data" / "csv"
SEED = 20251007
REGIONS = ("North", "South", "East", "West")
CATEGORIES = {
    "Home Organization": (142.0, 0.58),
    "Outdoor Living": (188.0, 0.62),
    "Kitchen": (96.0, 0.55),
    "Seasonal": (124.0, 0.60),
}
TARGETS = {
    "North": (190_000, 205_000, 215_000, 230_000),
    "South": (175_000, 190_000, 200_000, 215_000),
    "East": (195_000, 210_000, 225_000, 250_000),
    "West": (165_000, 180_000, 195_000, 220_000),
}


def quarter_dates(year: int, quarter: int) -> tuple[date, date]:
    """Return the inclusive start and end dates for a quarter."""
    first_month = (quarter - 1) * 3 + 1
    start = date(year, first_month, 1)
    if quarter == 4:
        next_quarter = date(year + 1, 1, 1)
    else:
        next_quarter = date(year, first_month + 3, 1)
    return start, next_quarter - timedelta(days=1)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    """Write a UTF-8 CSV with stable line endings and column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate_sales(rng: random.Random) -> list[dict[str, object]]:
    """Generate 1,200 region-quarter sales rows plus documented quality cases."""
    rows: list[dict[str, object]] = []
    row_number = 0
    for quarter in range(1, 5):
        start, end = quarter_dates(2025, quarter)
        day_span = (end - start).days + 1
        for region in REGIONS:
            for _ in range(75):
                row_number += 1
                category = rng.choice(tuple(CATEGORIES))
                unit_price, cost_ratio = CATEGORIES[category]
                units = rng.randint(13, 27)
                revenue = round(units * unit_price * rng.uniform(0.88, 1.12), 2)
                cost = round(revenue * cost_ratio * rng.uniform(0.96, 1.04), 2)
                if row_number == 1199:
                    revenue = 82_500.00
                    cost = 51_000.00
                if row_number == 37:
                    revenue_value: object = ""
                else:
                    revenue_value = f"{revenue:.2f}"
                cost_value: object = "" if row_number in {422, 981} else f"{cost:.2f}"
                transaction_date = start + timedelta(days=rng.randrange(day_span))
                rows.append(
                    {
                        "date": transaction_date.isoformat(),
                        "region": region,
                        "product_category": category,
                        "units": units,
                        "revenue": revenue_value,
                        "cost": cost_value,
                    }
                )
    rng.shuffle(rows)
    return rows


def generate_targets() -> list[dict[str, object]]:
    """Generate the approved regional quarterly gross-revenue targets."""
    return [
        {
            "region": region,
            "quarter": f"Q{quarter}",
            "target_revenue": target,
        }
        for region in REGIONS
        for quarter, target in enumerate(TARGETS[region], start=1)
    ]


def generate_feedback(rng: random.Random) -> list[dict[str, object]]:
    """Generate response-level customer feedback observations."""
    channels = ("store", "online", "pickup", "delivery")
    rows: list[dict[str, object]] = []
    for index in range(320):
        quarter = rng.randint(1, 4)
        start, end = quarter_dates(2025, quarter)
        score: object = (
            ""
            if index == 73
            else rng.choices(
                [2.0, 3.0, 3.5, 4.0, 4.5, 5.0],
                weights=[2, 8, 12, 28, 30, 20],
            )[0]
        )
        rows.append(
            {
                "date": (start + timedelta(days=rng.randint(0, (end - start).days))).isoformat(),
                "region": rng.choice(REGIONS),
                "score": score,
                "channel": rng.choice(channels),
            }
        )
    return rows


def generate_deliveries(rng: random.Random) -> list[dict[str, object]]:
    """Generate supplier shipments with on-time, late, missing, and defect cases."""
    suppliers = (
        "Aster Home",
        "Blue Cedar Supply",
        "Crown Outdoor",
        "Delta Kitchen",
        "Evergreen Goods",
        "Fjord Imports",
    )
    rows: list[dict[str, object]] = []
    for index in range(240):
        promised = date(2025, 7, 1) + timedelta(days=rng.randint(0, 91))
        is_late = index % 12 == 0
        delivered = (
            promised + timedelta(days=rng.randint(1, 6))
            if is_late
            else promised - timedelta(days=rng.randint(0, 2))
        )
        rows.append(
            {
                "supplier": rng.choice(suppliers),
                "promised_date": "" if index == 18 else promised.isoformat(),
                "delivered_date": "" if index == 201 else delivered.isoformat(),
                "defect_rate": "" if index == 94 else f"{rng.uniform(0.001, 0.047):.4f}",
            }
        )
    return rows


def main() -> None:
    """Generate all sample CSVs using the fixed seed."""
    rng = random.Random(SEED)
    write_csv(
        CSV_DIR / "sales_2025.csv",
        ["date", "region", "product_category", "units", "revenue", "cost"],
        generate_sales(rng),
    )
    write_csv(
        CSV_DIR / "regional_targets.csv",
        ["region", "quarter", "target_revenue"],
        generate_targets(),
    )
    write_csv(
        CSV_DIR / "customer_feedback.csv",
        ["date", "region", "score", "channel"],
        generate_feedback(rng),
    )
    write_csv(
        CSV_DIR / "supplier_deliveries.csv",
        ["supplier", "promised_date", "delivered_date", "defect_rate"],
        generate_deliveries(rng),
    )
    logging.getLogger(__name__).info("Generated deterministic sample data in %s", CSV_DIR)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
