"""Unit tests for the shared core (no network)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from polymarket_research_core.edge import compute_edge
from polymarket_research_core.evoi import SourceOption, evoi_decision, spend_saved
from polymarket_research_core.scoring import (
    Snapshot,
    brier_score,
    build_scorecard,
    lead_time_hours,
    log_loss,
    score_market,
)
from polymarket_research_core.models import (
    Evidence,
    Market,
    ProbabilityEstimate,
    ResearchNote,
)
from polymarket_research_core.notes import render_markdown
from polymarket_research_core.polymarket.gamma import parse_market
from polymarket_research_core.units import units_to_usd, usd_to_units
from polymarket_research_core.util import clamp01, extract_json


def test_units_roundtrip():
    assert units_to_usd(7000) == 0.007
    assert usd_to_units(0.01) == 10000


def test_extract_json_fenced():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_clamp01():
    assert clamp01(-1) == 0.0 and clamp01(2) == 1.0 and clamp01(0.5) == 0.5


def test_parse_market_json_strings():
    raw = {
        "id": "123", "slug": "will-x", "question": "Will X?",
        "description": "Resolves YES if X.",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.62", "0.38"]',
        "clobTokenIds": '["tokenYes", "tokenNo"]',
        "liquidity": "12000", "volume": "50000", "endDate": "2026-09-01T00:00:00Z",
    }
    m = parse_market(raw)
    assert m.market_prices["Yes"] == 0.62
    assert m.clob_token_ids["Yes"] == "tokenYes"
    assert m.liquidity == 12000.0
    assert m.end_date is not None


def test_compute_edge_flag():
    res = compute_edge(0.80, 0.60, 0.9, edge_threshold=0.07, confidence_threshold=0.6)
    assert round(res.edge, 2) == 0.20 and res.flagged is True


def test_compute_edge_low_conf_not_flagged():
    res = compute_edge(0.80, 0.60, 0.3, edge_threshold=0.07, confidence_threshold=0.6)
    assert res.flagged is False


def test_render_markdown():
    note = ResearchNote(
        market_id="1", market_slug="s", question="Will X?",
        model_prob=0.7, market_price=0.6, edge=0.1, confidence=0.8, flagged=True,
        sub_estimates=[ProbabilityEstimate(sub_question_id="a", prob=0.7,
                                           confidence=0.8, rationale="because")],
        evidence=[Evidence(sub_question_id="a", provider="exa",
                           operation_id="exa.search.web", url="http://x", title="T", snippet="s")],
        cost_units=14000,
    )
    md = render_markdown(note)
    assert "Not a trade recommendation" in md
    assert "$0.0140" in md and "FLAGGED" in md


def test_market_yes_price_property():
    m = Market(id="1", slug="s", question="q", market_prices={"Yes": 0.55})
    assert m.yes_price == 0.55


# --------------------------------------------------------------------------- #
# Phase 0 — scoring
# --------------------------------------------------------------------------- #
def test_brier_and_logloss_perfect_vs_wrong():
    assert brier_score(1.0, 1) == 0.0
    assert brier_score(0.0, 1) == 1.0
    # confident-and-wrong is punished far harder by log-loss than by Brier
    assert log_loss(0.99, 0) > log_loss(0.5, 0) > log_loss(0.01, 0)


def _snap(ts, mp, px, mid="1"):
    return Snapshot(market_id=mid, ts=ts, model_prob=mp, market_price=px)


def test_score_market_uses_final_snapshot():
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    snaps = [
        _snap(t0, 0.40, 0.50),
        _snap(t0 + timedelta(hours=6), 0.80, 0.55),  # final estimate
    ]
    s = score_market(snaps, outcome=1)
    assert s.final_model_prob == 0.80 and s.n_snapshots == 2
    assert s.brier_model < s.brier_market          # 0.80 beats 0.55 for a YES


def test_lead_time_agent_earlier_is_positive():
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    snaps = [
        _snap(t0, 0.70, 0.40),                       # agent already on YES, market not
        _snap(t0 + timedelta(hours=10), 0.75, 0.65), # market crosses to YES later
    ]
    lt = lead_time_hours(snaps, outcome=1)
    assert lt == 10.0


def test_build_scorecard_skill_score():
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    # model nails both; market is mediocre -> positive skill score, 100% win rate
    a = score_market([_snap(t0, 0.9, 0.6, "a")], outcome=1)
    b = score_market([_snap(t0, 0.1, 0.4, "b")], outcome=0)
    card = build_scorecard([a, b])
    assert card.n_resolved == 2
    assert card.win_rate_vs_market == 1.0
    assert card.brier_skill_score is not None and card.brier_skill_score > 0
    assert len(card.calibration) == 10


# --------------------------------------------------------------------------- #
# Phase 0 — EVOI shadow
# --------------------------------------------------------------------------- #
def test_evoi_buys_when_value_exceeds_price():
    opt = SourceOption(source="noaa", price_usd=0.40, expected_info_gain=0.3)
    d = evoi_decision(opt, stake_at_risk_usd=10.0, market_id="m")
    assert d.decision == "BUY" and d.evoi_value == 3.0


def test_evoi_skips_and_spend_saved():
    opt = SourceOption(source="exa.search.web", price_usd=0.50, expected_info_gain=0.02)
    d = evoi_decision(opt, stake_at_risk_usd=5.0, market_id="m")
    assert d.decision == "SKIP"
    assert spend_saved([d]) == 0.50
