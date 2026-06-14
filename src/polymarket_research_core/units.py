"""Gordon micro-unit helpers. 1,000,000 units = $1.00 USD."""
from __future__ import annotations

UNITS_PER_USD = 1_000_000


def units_to_usd(units: int) -> float:
    return units / UNITS_PER_USD


def usd_to_units(usd: float) -> int:
    return int(round(usd * UNITS_PER_USD))
