# PulseNet

**Predictive Decision-Support for Critical Resource Shortages**

PulseNet predicts where the next shortage of a critical resource — LPG, fuel, medicine, electricity — will hit *before* it hits, and hands a human administrator a one-click way to stop it.

## Architecture

```
[ Live feeds: GDACS / USGS / Reuters RSS ]
                    │
                    ▼
    Agent 1 — Ingestion Filter (Gemini / rule-based)
                    │
                    ▼
    Agent 2 — Graph Explorer (trade dependency graph)
                    │
                    ▼
    Agent 3 — Ripple Evaluator (Monte Carlo + reroutes)
                    │
                    ▼
    Dashboard — heatmap, ranked reroutes, Approve/Reject
```

**Design principle:** LLMs parse unstructured shock data; deterministic Python handles graph traversal and Monte Carlo simulation.

## Quick Start

### 1. Install dependencies

```bash
cd pulsenet
pip install -r requirements.txt
```

### 2. (Optional) Configure API keys

Copy `.env.example` to `.env` and add keys for enhanced extraction:

```bash
cp .env.example .env
```

- `GEMINI_API_KEY` — Google AI Studio key for ripple narratives (optional)
- `GEMINI_INGESTION_API_KEY` — separate project key for ingestion (optional)
- Without keys, rule-based extraction works out of the box.

### 3. Seed the trade graph

```bash
python scripts/seed_database.py
```

### 4. Run the dashboard

```bash
streamlit run app.py
```

Open http://localhost:8501

### 5. Demo flow

1. Click **Fetch Live Feeds & Run Pipeline** in the sidebar
2. Watch GDACS, USGS, and Reuters events get ingested
3. View the time-to-shortage heatmap for exposed regions
4. Review ranked reroute suggestions with confidence badges
5. Click **Approve**, **Reject**, or **Adjust** — decisions are logged
6. Low-monitoring regions show **"LOW CONFIDENCE — verify manually"**

## MVP Features

- ✅ Live ingestion from GDACS + USGS + Reuters RSS
- ✅ Static trade graph (LPG, Diesel, Wheat) for 50+ countries
- ✅ Full pipeline: shock → ripple → reroute suggestion
- ✅ Approve/Reject/Adjust with decision logging
- ✅ Data confidence badge per region (equity-weighted)
- ✅ LangGraph agent orchestration
- ✅ Monte Carlo reroute simulation

## Tech Stack

| Component | Technology |
|-----------|------------|
| LLM | Gemini 2.0 Flash (optional) |
| Orchestration | LangGraph |
| Database | SQLite (local) / Supabase (optional) |
| Frontend | Streamlit |
| Feeds | GDACS RSS, USGS GeoJSON, Reuters RSS |

## Responsible AI

- **Decision support only** — no autonomous execution
- **Equity-weighted** — under-monitored regions get explicit low-confidence flags
- **Explainable** — deterministic math for graph + simulation; LLM only for text parsing

## Project Structure

```
pulsenet/
├── app.py                 # Streamlit dashboard
├── requirements.txt
├── .env.example
├── data/
│   └── trade_graph_seed.py  # UN Comtrade-style baseline
├── scripts/
│   └── seed_database.py
└── src/
    ├── agents/
    │   ├── ingestion.py       # Agent 1
    │   ├── graph_explorer.py  # Agent 2
    │   └── ripple_evaluator.py# Agent 3
    ├── feeds/
    │   └── connectors.py      # GDACS, USGS, Reuters
    ├── pipeline/
    │   └── workflow.py        # LangGraph state machine
    ├── simulation/
    │   └── monte_carlo.py
    ├── config.py
    └── database.py
```

## License

Hackathon project — free to use and modify.
