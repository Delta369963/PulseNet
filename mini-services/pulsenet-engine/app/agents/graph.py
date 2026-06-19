"""Consensus graph — orchestrates Alpha ∥ Beta → Gamma.

Topology (LangGraph-style, implemented with asyncio for a light dependency
footprint that runs on free-tier compute):

        raw RSS items
        ┌─────┴─────┐
     Alpha(KeyA)  Beta(KeyB)      # parallel structured extraction
        └─────┬─────┘
           Gamma                  # Byzantine consensus judge
        ConsensusShock[]          # validated + agreement delta

USGS pre-structured items skip the LLM entirely and pass through with delta=0.
"""

from __future__ import annotations

import asyncio

from app.agents import gamma
from app.agents.llm import GeminiClient
from app.agents.parser import parse_items, structured_from_prestructured
from app.logging import get_logger
from app.schemas import ConsensusShock, RawItem

logger = get_logger("agents.graph")


def _match_index(target, candidates: list, used: set[int]) -> int | None:
    """Find the best unused Beta extraction for a given Alpha extraction.

    Match heuristic: same type first, then any unused. Keeps Gamma's pairing
    deterministic so consensus is reproducible.
    """
    for i, c in enumerate(candidates):
        if i in used and len(candidates) > 1:
            continue
        if c.type == target.type and i not in used:
            return i
    for i in range(len(candidates)):
        if i not in used:
            return i
    return None


async def run_consensus(
    alpha_client: GeminiClient,
    beta_client: GeminiClient,
    items: list[RawItem],
    country_catalog: str,
    catalog_codes: set[str],
    country_name_map: dict[str, str] | None = None,
) -> list[ConsensusShock]:
    """Run the full consensus pipeline over a batch of raw items."""
    prestructured = [it for it in items if it.prestructured]
    unstructured = [it for it in items if not it.prestructured]

    results: list[ConsensusShock] = []

    # Pre-structured (USGS): no LLM, perfect agreement.
    for it in prestructured:
        shock = structured_from_prestructured(it)
        results.append(
            ConsensusShock(
                shock=shock,
                byzantine_agreement_delta=0.0,
                alpha_raw=shock.model_dump(),
                beta_raw=shock.model_dump(),
                source_feed_url=it.source_url or "",
            )
        )

    if unstructured:
        # Alpha ∥ Beta in parallel (each batches all items in one call).
        alpha_task = parse_items(alpha_client, unstructured, country_catalog, catalog_codes, country_name_map)
        beta_task = parse_items(beta_client, unstructured, country_catalog, catalog_codes, country_name_map)
        alpha_out, beta_out = await asyncio.gather(alpha_task, beta_task)

        logger.info(
            "agents parsed",
            extra={"extra": {"alpha": len(alpha_out), "beta": len(beta_out)}},
        )

        used: set[int] = set()
        beta_available = beta_client.available and len(beta_out) > 0
        for a in alpha_out:
            beta_match = None
            if beta_available:
                idx = _match_index(a, beta_out, used)
                if idx is not None:
                    beta_match = beta_out[idx]
                    used.add(idx)
            src = next(
                (it.source_url for it in unstructured if it.title[:20] in a.title or a.title[:20] in it.title),
                "",
            )
            results.append(gamma.judge(a, beta_match, source_feed_url=src or ""))

    return results
