"""Edge = model probability - market-implied probability. Settings-agnostic."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EdgeResult:
    market_price: float
    edge: float
    flagged: bool


def compute_edge(
    model_prob: float,
    market_price: float,
    confidence: float,
    *,
    edge_threshold: float = 0.07,
    confidence_threshold: float = 0.6,
) -> EdgeResult:
    edge = model_prob - market_price
    flagged = abs(edge) >= edge_threshold and confidence >= confidence_threshold
    return EdgeResult(market_price=market_price, edge=edge, flagged=flagged)
