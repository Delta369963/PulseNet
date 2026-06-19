# PulseNet v2 — Implementation Summary

Built per `prompt.md` Architecture A (Geo-Agentic Dependency & Ontology Network),
adapted to run on free-tier compute while keeping the existing Next.js frontend intact.

---

## Core principle

**LLMs parse unstructured chaos → deterministic code does the math → every action ends at a human.**

The engine never executes a reroute. It predicts, explains, and proposes. Every number
is traceable to a source. Under-monitored regions get an explicit `⚠ LOW CONFIDENCE` flag,
never a silent "no risk."

---

## Architecture

```
Next.js frontend  (Conflictly-style ops dashboard — components unchanged)
        │  fetch('/api/*') — same API contract as v0.9
        ▼
Next.js /api routes
  GETs → Prisma reads directly (stats, shocks, graph, decisions)
  POST /api/shocks/ingest ──────────────→ FastAPI /ingest  (TS fallback if engine offline)
  POST /api/ripple ─────────────────────→ FastAPI /ripple  (TS fallback if engine offline)
  GET  /api/ledger ─────────────────────→ FastAPI /ledger  (returns [] if engine offline)
        │
        ▼
FastAPI pulsenet-engine  (mini-services/pulsenet-engine/)
  ┌──────────────────────────────────────────────────────┐
  │ Feeds (concurrent)                                   │
  │   USGS (seismic, keyless) · GDACS · ReliefWeb        │
  │   GDELT · Reuters · BBC Business · Al Jazeera        │
  │   Maritime Executive · ACLED (OAuth bearer)          │
  └───────────────────┬──────────────────────────────────┘
                      │ raw items
  ┌───────────────────▼──────────────────────────────────┐
  │ Consensus agents (asyncio ∥)                         │
  │   Alpha (Gemini Key A) ─────┐                        │
  │                            ├─→ Gamma (Byzantine Δ)   │
  │   Beta  (Gemini Key B) ─────┘        ↓               │
  │   Gemini JSON mode: response_mime_type=application/json│
  └───────────────────┬──────────────────────────────────┘
                      │ validated ConsensusShock + δ
  ┌───────────────────▼──────────────────────────────────┐
  │ Compute (pure Python, no I/O)                        │
  │   SRI → cascade DAG (networkx) → Monte Carlo (numpy) │
  └───────────────────┬──────────────────────────────────┘
                      │ shocks, exposures, reroutes, DAG
  ┌───────────────────▼──────────────────────────────────┐
  │ Shared SQLite (db/custom.db, WAL mode)               │
  │   Prisma-owned schema + SystemicConsensusLedger      │
  └──────────────────────────────────────────────────────┘
```

---

## What was built (phase by phase)

### Phase 1 — Prisma schema + seed
- Added SRI inputs to `Country`: `gdpPerCapita`, `gridDensity`, `historicalVolatility`, `sri`
- New `SystemicConsensusLedger` model (prompt §4 interpretability table)
- `prisma/seed.ts` updated: 20 countries with World Bank–sourced SRI values, computed
  using the exact same formula as `app/compute/sri.py`

### Phase 2 — FastAPI engine (one concern per module)

| Module | Responsibility |
|---|---|
| `app/config.py` | All env vars; `feature_flags()` at `/health` for live debugging |
| `app/logging.py` | Structured JSON logs + correlation ID per run (grep-able) |
| `app/compute/sri.py` | SRI formula — pure math, zero I/O, 100% testable |
| `app/compute/cascade.py` | NetworkX cascade DAG + fixed `recuperation_factor` (see below) |
| `app/compute/monte_carlo.py` | Numpy Monte Carlo, seeded RNG for deterministic tests |
| `app/db/{models,session,repo}.py` | SQLAlchemy on Prisma's SQLite; WAL mode |
| `app/feeds/usgs.py` | Structured seismic feed — no LLM needed |
| `app/feeds/rss.py` | Generic RSS (feedparser) for GDACS, Reuters, BBC, GDELT, etc. |
| `app/feeds/acled.py` | ACLED conflict feed via OAuth bearer; auto-refreshes on 401 |
| `app/feeds/registry.py` | Loads `feeds.yaml`, runs all sources concurrently |
| `app/agents/llm.py` | GeminiClient — JSON mode (`response_mime_type=application/json`) |
| `app/agents/parser.py` | Alpha/Beta parse; deterministic keyword fallback if LLM dark |
| `app/agents/gamma.py` | Byzantine consensus Δ — weighted disagreement score |
| `app/agents/graph.py` | Orchestrates Alpha ∥ Beta → Gamma |
| `app/services/ingest_service.py` | Feeds → consensus → ledger → DB |
| `app/services/ripple_service.py` | Graph traversal + SRI cascade + Monte Carlo + reroutes |
| `app/main.py` | FastAPI wiring only |

### Phase 3 — Next.js wiring
- `/api/shocks/ingest` and `/api/ripple`: proxy to engine → graceful TS fallback
- `/api/ledger`: new route, returns `[]` if engine offline
- `zai.ts`: replaced `z-ai-web-dev-sdk` with `@google/generative-ai@0.24.1`
- `package.json`: removed z-ai, added Gemini SDK
- `.env` / `.env.example`: documented all key slots

### Phase 3b — Consensus Ledger panel
- `types.ts`: `LedgerRow` type added
- `responsible-ai.tsx`: new Consensus Ledger panel showing Byzantine δ per crisis
- `page.tsx`: `loadLedger` callback + 5-min poll + prop pass-through

### Phase 4 — Backward-chaining validation
`tests/test_backward_chain.py`: seeds 2022 neon→semiconductor shock, runs forward pipeline
blind, asserts cascade confidence P > 0.12 for downstream manufacturers.

---

## Logic fixes applied

**Cascade `recuperation_factor` bug:** The original `1 - 1/SRI` formula is degenerate
when SRI ∈ [0.05, 1.0] (always returns ≤ 0). Fixed by rescaling SRI to [1, 5] first:
```
sri_scaled = 1 + sri * 4
factor = 1 - 1 / sri_scaled   → [0, 0.80] for SRI ∈ [0, 1]
```
This gives fragile nations (SRI=0.2 → factor=0.44, vulnerability=0.56) higher cascade
confidence than resilient nations (SRI=0.9 → factor=0.76, vulnerability=0.24).

**Gemini JSON mode:** `response_mime_type="application/json"` forces valid JSON output,
eliminating markdown-fence parsing failures and reducing token usage.

**Prompt clarity:** System prompt now says "Analyse step-by-step internally, then output
ONLY a valid JSON array." — encourages CoT reasoning before the constrained JSON output.

---

## How to run

```bash
# One-time setup
make install          # npm install + prisma db push + uv pip install
cp .env.example .env  # fill in GEMINI_API_KEY_A + _B (already in .env if you ran this session)

# Two terminals
make dev              # Next.js on :3000
make engine           # FastAPI on :8000

# Reset demo data
make seed             # Wipes + reloads trade graph + 2 replay shocks

# Run tests
make test             # 41 tests, all pass
```

### API keys needed

| Key | Where | Free? |
|---|---|---|
| `GEMINI_API_KEY_A` | aistudio.google.com → "Get API key" | Yes (15 RPM) |
| `GEMINI_API_KEY_B` | Second Google account/project | Yes (15 RPM) |
| `ACLED_ACCESS_TOKEN` | acleddata.com/access → OAuth JWT | Yes (academic) |
| `SEARCH_API_KEY` | serper.dev (TS fallback only) | Yes (2500/month) |

Keyless sources: USGS, GDACS, ReliefWeb, GDELT, Reuters RSS, BBC RSS, Al Jazeera, Maritime Executive.

---

## Test suite (41 tests, all pass)

| File | Tests cover |
|---|---|
| `test_sri.py` | SRI formula, normalization, weights |
| `test_cascade.py` | Recuperation factor, path confidence, DAG correctness |
| `test_monte_carlo.py` | Determinism (seeded), success probability bounds |
| `test_gamma_consensus.py` | Byzantine delta math, confidence penalization |
| `test_feeds_parse.py` | Haversine, nearest-country, RSS/USGS parsing (mocked network) |
| `test_parser.py` | LLM JSON parse, deterministic fallback, country-code filtering |
| `test_ripple_service.py` | Graph traversal, exposure creation, ledger row, idempotent re-eval |
| `test_ingest_service.py` | Feed→shock pipeline, dedup, ledger write |
| `test_api.py` | FastAPI endpoints via TestClient |
| `test_backward_chain.py` | 2022 neon→semiconductor cascade, P > 0.12 |

---

## Responsible-AI checklist

- ✅ Decision-support only — no autonomous execution
- ✅ Equity-weighted — low-density regions flagged `⚠ LOW CONFIDENCE`, never silent
- ✅ Explainable — every exposure has a causal path; every reroute has MC breakdown
- ✅ Human-in-the-loop — every reroute ends at Approve / Reject / Adjust
- ✅ Audit trail — every action logged with actor + timestamp
- ✅ Honest uncertainty — MC reports median + p95 + success probability
- ✅ Consensus transparency — Byzantine δ logged per crisis in the ledger panel
