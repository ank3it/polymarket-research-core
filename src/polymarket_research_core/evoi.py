"""Expected Value of Information (EVOI) — the shadow-mode purchasing engine.

In Phase 0 nothing is actually bought. For each candidate data source we log the
*decision* the allocator would make: buy iff the expected edge value it unlocks
exceeds its price. Later, when markets resolve, we compare predicted info-gain to
realized improvement → a "which feeds earned their keep" leaderboard, with no
wallet required to start.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SourceOption(BaseModel):
    """A priced option on accuracy for a given market."""

    source: str                      # e.g. "exa.search.web", "noaa.forecast"
    price_usd: float                 # what the source costs to query
    expected_info_gain: float        # 0..1, predicted reduction in our uncertainty


class ShadowDecision(BaseModel):
    """A logged buy/skip decision — the EVOI ledger entry."""

    market_id: str
    sub_question_id: str = ""
    ts: datetime = Field(default_factory=_now)
    source: str
    price_usd: float
    expected_info_gain: float
    stake_at_risk_usd: float
    evoi_value: float                # expected_info_gain * stake_at_risk_usd
    decision: Literal["BUY", "SKIP"]
    reason: str = ""


def evoi_decision(
    option: SourceOption,
    stake_at_risk_usd: float,
    *,
    market_id: str,
    sub_question_id: str = "",
) -> ShadowDecision:
    """Buy iff expected edge value (info-gain x stake) exceeds the source price."""
    value = option.expected_info_gain * stake_at_risk_usd
    buy = value > option.price_usd
    reason = (
        f"EVOI ${value:.4f} {'>' if buy else '<='} price ${option.price_usd:.4f}"
        f" (info_gain={option.expected_info_gain:.2f} x stake ${stake_at_risk_usd:.2f})"
    )
    return ShadowDecision(
        market_id=market_id,
        sub_question_id=sub_question_id,
        source=option.source,
        price_usd=option.price_usd,
        expected_info_gain=option.expected_info_gain,
        stake_at_risk_usd=stake_at_risk_usd,
        evoi_value=value,
        decision="BUY" if buy else "SKIP",
        reason=reason,
    )


def spend_saved(decisions: list[ShadowDecision]) -> float:
    """Total price of sources the allocator *declined* to buy (EVOI < cost)."""
    return sum(d.price_usd for d in decisions if d.decision == "SKIP")
