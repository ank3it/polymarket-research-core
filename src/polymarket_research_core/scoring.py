"""Phase-0 measurement: score a forecast trajectory against the realized outcome.

The unit of statistical power is a *resolved market*, not a snapshot. We record a
probability trajectory per market (each cycle), and when the market resolves we
score the agent's final estimate against the 0/1 outcome — and against the market
price as the baseline. Lead-time uses the full trajectory.

All functions are pure and settings-agnostic so they're trivially testable.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Data contracts
# --------------------------------------------------------------------------- #
class Snapshot(BaseModel):
    """One timestamped reading of a market during a research cycle."""

    market_id: str
    market_slug: str = ""
    question: str = ""
    ts: datetime
    model_prob: float        # agent's P(YES), 0..1
    market_price: float      # Polymarket implied P(YES), 0..1
    confidence: float = 0.5
    edge: float = 0.0


class CalibrationBin(BaseModel):
    lo: float
    hi: float
    n: int
    mean_pred: float | None = None
    mean_obs: float | None = None


class MarketScore(BaseModel):
    """Scores for one resolved market (final estimate + path-based lead-time)."""

    market_id: str
    market_slug: str = ""
    question: str = ""
    outcome: int                       # realized: 1 = YES, 0 = NO
    resolved_at: datetime | None = None
    final_model_prob: float
    final_market_price: float
    brier_model: float
    brier_market: float
    logloss_model: float
    logloss_market: float
    lead_time_hours: float | None = None
    n_snapshots: int = 1
    scored_at: datetime = Field(default_factory=_now)


class ScorecardSummary(BaseModel):
    """Aggregate across all resolved markets — the headline of the scorecard."""

    updated_at: datetime = Field(default_factory=_now)
    n_resolved: int = 0
    mean_brier_model: float | None = None
    mean_brier_market: float | None = None
    mean_logloss_model: float | None = None
    mean_logloss_market: float | None = None
    brier_skill_score: float | None = None     # 1 - brier_model/brier_market; >0 beats market
    mean_lead_time_hours: float | None = None
    win_rate_vs_market: float | None = None     # share of markets where model Brier < market Brier
    calibration: list[CalibrationBin] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Point scoring
# --------------------------------------------------------------------------- #
def _clamp(p: float, eps: float = 1e-6) -> float:
    return min(1.0 - eps, max(eps, p))


def brier_score(prob: float, outcome: int) -> float:
    """Squared error: (p - y)^2. Lower is better; 0..1."""
    return (prob - outcome) ** 2


def log_loss(prob: float, outcome: int, eps: float = 1e-6) -> float:
    """Negative log-likelihood of the outcome. Lower is better."""
    p = _clamp(prob, eps)
    return -(outcome * math.log(p) + (1 - outcome) * math.log(1.0 - p))


# --------------------------------------------------------------------------- #
# Trajectory helpers
# --------------------------------------------------------------------------- #
def _side(prob: float) -> int:
    """Which outcome a probability commits to (1=YES) at the 0.5 line."""
    return 1 if prob >= 0.5 else 0


def lead_time_hours(snapshots: list[Snapshot], outcome: int) -> float | None:
    """Hours the agent committed to the correct side *before* the market did.

    Positive  -> agent was earlier than the market (good).
    Negative  -> the market got there first.
    None      -> one of them never committed to the realized side.
    """
    if not snapshots:
        return None
    ordered = sorted(snapshots, key=lambda s: s.ts)

    def first_commit(read) -> datetime | None:
        for s in ordered:
            if _side(read(s)) == outcome:
                return s.ts
        return None

    agent_ts = first_commit(lambda s: s.model_prob)
    market_ts = first_commit(lambda s: s.market_price)
    if agent_ts is None or market_ts is None:
        return None
    return (market_ts - agent_ts).total_seconds() / 3600.0


def score_market(
    snapshots: list[Snapshot],
    outcome: int,
    resolved_at: datetime | None = None,
) -> MarketScore:
    """Score one market: point metrics on the final snapshot, lead-time on the path."""
    if not snapshots:
        raise ValueError("need at least one snapshot to score a market")
    ordered = sorted(snapshots, key=lambda s: s.ts)
    final = ordered[-1]
    return MarketScore(
        market_id=final.market_id,
        market_slug=final.market_slug,
        question=final.question,
        outcome=outcome,
        resolved_at=resolved_at,
        final_model_prob=final.model_prob,
        final_market_price=final.market_price,
        brier_model=brier_score(final.model_prob, outcome),
        brier_market=brier_score(final.market_price, outcome),
        logloss_model=log_loss(final.model_prob, outcome),
        logloss_market=log_loss(final.market_price, outcome),
        lead_time_hours=lead_time_hours(ordered, outcome),
        n_snapshots=len(ordered),
    )


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def calibration_bins(
    pairs: list[tuple[float, int]], n_bins: int = 10
) -> list[CalibrationBin]:
    """Bin (predicted_prob, outcome) pairs to build a reliability curve."""
    bins: list[CalibrationBin] = []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        members = [
            (p, y) for p, y in pairs
            if (p >= lo and p < hi) or (i == n_bins - 1 and p == 1.0)
        ]
        if members:
            mp = sum(p for p, _ in members) / len(members)
            mo = sum(y for _, y in members) / len(members)
            bins.append(CalibrationBin(lo=lo, hi=hi, n=len(members), mean_pred=mp, mean_obs=mo))
        else:
            bins.append(CalibrationBin(lo=lo, hi=hi, n=0))
    return bins


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def build_scorecard(scores: list[MarketScore], n_bins: int = 10) -> ScorecardSummary:
    """Aggregate per-market scores into the headline scorecard."""
    if not scores:
        return ScorecardSummary(n_resolved=0)
    bm = _mean([s.brier_model for s in scores])
    bk = _mean([s.brier_market for s in scores])
    leads = [s.lead_time_hours for s in scores if s.lead_time_hours is not None]
    skill = (1.0 - bm / bk) if (bm is not None and bk not in (None, 0.0)) else None
    wins = sum(1 for s in scores if s.brier_model < s.brier_market)
    return ScorecardSummary(
        n_resolved=len(scores),
        mean_brier_model=bm,
        mean_brier_market=bk,
        mean_logloss_model=_mean([s.logloss_model for s in scores]),
        mean_logloss_market=_mean([s.logloss_market for s in scores]),
        brier_skill_score=skill,
        mean_lead_time_hours=_mean(leads),
        win_rate_vs_market=wins / len(scores),
        calibration=calibration_bins(
            [(s.final_model_prob, s.outcome) for s in scores], n_bins=n_bins
        ),
    )
