"""Polymarket Gamma API — market discovery & metadata (public, no auth).

Base: https://gamma-api.polymarket.com
Settings-agnostic: pass a base URL (defaults to the public endpoint). Several
fields (outcomes, outcomePrices, clobTokenIds) arrive as JSON-encoded strings
and are decoded here into a clean `Market`.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import httpx

from polymarket_research_core.models import Market
from polymarket_research_core.polymarket import DEFAULT_GAMMA_URL

logger = logging.getLogger(__name__)


def _loads_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_market(raw: dict[str, Any]) -> Market:
    outcomes = [str(o) for o in _loads_list(raw.get("outcomes"))] or ["Yes", "No"]
    prices = [float(p) for p in _loads_list(raw.get("outcomePrices"))]
    token_ids = [str(t) for t in _loads_list(raw.get("clobTokenIds"))]

    market_prices = {o: prices[i] for i, o in enumerate(outcomes) if i < len(prices)}
    clob_token_ids = {o: token_ids[i] for i, o in enumerate(outcomes) if i < len(token_ids)}

    return Market(
        id=str(raw.get("id") or raw.get("conditionId") or raw.get("slug")),
        slug=str(raw.get("slug", "")),
        question=str(raw.get("question", "")),
        description=str(raw.get("description", "")),
        resolution_rules=str(raw.get("description", "")),  # Gamma puts rules in description
        end_date=_parse_dt(raw.get("endDate")),
        liquidity=float(raw.get("liquidity") or 0.0),
        volume=float(raw.get("volume") or 0.0),
        outcomes=outcomes,
        clob_token_ids=clob_token_ids,
        market_prices=market_prices,
    )


class GammaClient:
    def __init__(self, base_url: str = DEFAULT_GAMMA_URL, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def list_markets(
        self,
        *,
        limit: int = 50,
        active: bool = True,
        closed: bool = False,
        order: str = "volume",
        ascending: bool = False,
        extra_params: dict[str, Any] | None = None,
    ) -> list[Market]:
        params: dict[str, Any] = {
            "limit": limit,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "order": order,
            "ascending": str(ascending).lower(),
        }
        if extra_params:
            params.update(extra_params)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/markets", params=params)
            resp.raise_for_status()
            data = resp.json()

        rows = data if isinstance(data, list) else data.get("data", [])
        markets = [parse_market(r) for r in rows]
        logger.info("Gamma returned %d markets", len(markets))
        return markets

    async def get_market(self, market_id: str) -> Market | None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/markets/{market_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return parse_market(resp.json())
