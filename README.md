# polymarket-research-core

Shared logic for the Polymarket research projects, so the standalone CLI bot and
the managed-agent Skill never drift. Settings-agnostic and dependency-light
(httpx + pydantic only).

## What's inside

- **`polymarket/`** — Gamma market discovery + CLOB live prices (public, no auth). Pass a base URL or use the defaults.
- **`models`** — Pydantic contracts: `Market`, `SubQuestion`, `Evidence`, `ProbabilityEstimate`, `ResearchNote`, `CostRecord`.
- **`edge`** — `compute_edge(model_prob, market_price, confidence, edge_threshold=…, confidence_threshold=…)`.
- **`notes`** — `build_note`, `render_markdown`, `save_note` (Markdown + JSON).
- **`prompts`** — decomposition + estimation prompt templates.
- **`units`** — Gordon micro-unit helpers (`1_000_000 units = $1.00`).
- **`util`** — `extract_json`, `clamp01`.

## Consumers

- [`polymarket-research-bot`](https://github.com/ank3it/polymarket-research-bot) — standalone CLI bot.
- `polymarket-research-agent` — managed-agent Skill (autonomous, scheduled).

## Install

```bash
pip install -e .
# or from git:
pip install "git+https://github.com/ank3it/polymarket-research-core.git"
```

## Usage

```python
import asyncio
from polymarket_research_core import GammaClient, ClobClient, compute_edge

async def main():
    markets = await GammaClient().list_markets(limit=5)
    m = markets[0]
    price = await ClobClient().yes_price(m)
    print(m.question, price)
    print(compute_edge(0.72, price or 0.5, 0.8))

asyncio.run(main())
```

## License

MIT — see [LICENSE](./LICENSE).
