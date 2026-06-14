"""Unit tests for the shared core (no network)."""
from __future__ import annotations

from polymarket_research_core.edge import compute_edge
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
