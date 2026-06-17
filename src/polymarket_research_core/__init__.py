"""polymarket-research-core — shared logic for the Polymarket research projects.

Settings-agnostic building blocks shared by the standalone CLI bot and the
managed-agent Skill: Polymarket data access, data models, probability/edge math,
research-note rendering, prompts, and unit helpers.
"""

from polymarket_research_core.edge import EdgeResult, compute_edge
from polymarket_research_core.models import (
    CostRecord,
    Evidence,
    Market,
    ProbabilityEstimate,
    ResearchNote,
    SubQuestion,
)
from polymarket_research_core.evoi import (
    ShadowDecision,
    SourceOption,
    evoi_decision,
    spend_saved,
)
from polymarket_research_core.notes import build_note, render_markdown, save_note
from polymarket_research_core.polymarket.clob import ClobClient
from polymarket_research_core.polymarket.gamma import GammaClient, parse_market
from polymarket_research_core.scoring import (
    CalibrationBin,
    MarketScore,
    ScorecardSummary,
    Snapshot,
    brier_score,
    build_scorecard,
    calibration_bins,
    lead_time_hours,
    log_loss,
    score_market,
)
from polymarket_research_core.units import UNITS_PER_USD, units_to_usd, usd_to_units

__version__ = "0.2.0"

__all__ = [
    "Market", "SubQuestion", "Evidence", "ProbabilityEstimate", "ResearchNote", "CostRecord",
    "GammaClient", "parse_market", "ClobClient",
    "compute_edge", "EdgeResult",
    "build_note", "render_markdown", "save_note",
    "units_to_usd", "usd_to_units", "UNITS_PER_USD",
    # Phase 0 — scoring
    "Snapshot", "MarketScore", "ScorecardSummary", "CalibrationBin",
    "brier_score", "log_loss", "lead_time_hours", "score_market",
    "calibration_bins", "build_scorecard",
    # Phase 0 — EVOI shadow
    "SourceOption", "ShadowDecision", "evoi_decision", "spend_saved",
]
