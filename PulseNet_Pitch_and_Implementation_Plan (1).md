# PulseNet
### Predictive Decision-Support for Critical Resource Shortages

---

## PART 1 — THE PITCH

### One-liner
PulseNet predicts where the next shortage of a critical resource — LPG, fuel, medicine, electricity — will hit *before* it hits, and hands a human administrator a one-click way to stop it.

### The Problem
Distribution networks for essential commodities are built for stability, not shocks. A seismic event, a flood, a grid failure, a port closure, a sudden border restriction, or a trucker strike all do the same thing: they sever a link in a chain that was never designed to bend. The network doesn't fail everywhere at once — it fails downstream, days or weeks later, in places that had nothing to do with the original event. By the time the shortage is visible (queues, empty cylinders, hospitals rationing diesel), it's already a humanitarian problem, and it almost always lands hardest on populations with the least cushion to absorb it.

### The Insight
The data needed to see this coming already exists — it's just scattered and never fused:
- **Shock signals** are public: disaster alerts (GDACS), conflict/event data (ACLED), port and shipping data (UNCTAD), weather and seismic feeds (NOAA/USGS).
- **Dependency structure** is public: trade baseline data (OEC, UN Comtrade) shows exactly who supplies what to whom, by commodity.
- **The missing piece** is something that can read the first kind of data, reason over the second, and tell a human *"this shock is going to become that shortage, in this place, in roughly this many days — here are two ways to stop it."**

That's a reasoning + retrieval problem, which is exactly what current LLMs (cheaply, even for free) are good at — but no existing public tool does it.

### The Solution
PulseNet is an agentic decision-support dashboard built in three layers:

1. **Ingestion** — lightweight agents continuously read live shock signals from public feeds worldwide.
2. **Graph reasoning** — a supply/trade dependency graph (built from public trade data) tells the system who is exposed to a given shock, directly and downstream.
3. **Simulation & routing** — the system estimates time-to-shortage for each exposed region and proposes 1–2 viable alternative routes or suppliers.

Everything surfaces on a dashboard. The AI never executes anything — it predicts, explains, and proposes; a human administrator approves, rejects, or adjusts.

### Why This Wins (the competitive delta)
| Existing player | What it does | What it's missing |
|---|---|---|
| Conflictly / similar OSINT trackers | Visualizes live conflict & disaster events | No supply-chain or logistics layer at all |
| BlackRock Aladdin / Palantir Foundry | Predictive risk modeling at massive scale | Closed-source, built for finance/defense, not public access |
| GitHub "supply chain risk" repos | Static optimization (linear programming) on clean historical data | Can't ingest live, messy, real-world text; no human-in-the-loop design |

PulseNet's delta is fusing *live, unstructured shock data* with a *public dependency graph* and surfacing it as a *governed, human-approved* decision tool — civic infrastructure, not a corporate or defense product.

### Responsible AI Stance
- **Decision support only.** No autonomous execution of any reroute, ever.
- **Equity-weighted, not blind.** Regions with sparse monitoring data don't get silently treated as "no risk" — they get explicitly flagged as low-confidence, which keeps a human looking exactly where the AI is weakest.

### Impact in one sentence
Shorter detection-to-response time on supply shocks means shorter shortage windows — which means fewer preventable deaths, less price gouging, and less wasted aid, concentrated where it matters most: communities with the least slack to absorb a disruption.

---

## PART 2 — IMPLEMENTATION PLAN

### 2.1 Architecture Overview

```
[ Live feeds: GDACS / ACLED / NOAA / USGS / UNCTAD / Reuters RSS ]
                          │
                          ▼
        ┌───────────────────────────────────┐
        │ Agent 1 — Ingestion Filter (Gemini)│  → extracts event, location,
        └───────────────────────────────────┘     coordinates, severity
                          │
                          ▼
        ┌───────────────────────────────────┐
        │ Agent 2 — Graph Explorer (Python)  │  → queries Supabase trade graph
        └───────────────────────────────────┘     for direct + downstream nodes
                          │
                          ▼
        ┌───────────────────────────────────┐
        │ Agent 3 — Ripple Evaluator         │  → estimates time-to-shortage,
        │ (Gemini + Monte Carlo in Python)   │     proposes reroutes
        └───────────────────────────────────┘
                          │
                          ▼
        ┌───────────────────────────────────┐
        │ Dashboard — human review layer     │  → heatmap + ranked reroutes,
        └───────────────────────────────────┘     approve / reject / adjust
```

Design principle: **LLMs handle the unstructured chaos (text → structured event); deterministic code handles the math (graph traversal, ripple calculation).** This keeps the system explainable and avoids asking a language model to do anything it's bad at.

### 2.2 Data Sources

**Live shock signals (the "exhaust data"):**
- GDACS — global disaster alerts (earthquakes, floods, cyclones), free RSS/XML
- ACLED — conflict/event data, free API for research/academic use
- Reuters World News RSS — general geopolitical signal
- NOAA / USGS — weather and seismic feeds
- UNCTAD — port call and shipping line connectivity data

**Static dependency baseline (the "graph"):**
- OEC (Observatory of Economic Complexity) API or UN Comtrade API — structured import/export data by HS code (e.g., LPG, refined petroleum, wheat) and trading-partner relationships. Pulled once, stored statically in Supabase as the structural graph — no need to rebuild this from scratch.

### 2.3 Tech Stack (entirely free-tier)
- **LLM:** Gemini 2.5 Flash, free tier (10 RPM / 250 RPD per key)
- **Orchestration:** LangGraph (open-source Python) for the agent state machine
- **Database:** Supabase free tier for the static trade graph + cached live events
- **Frontend:** Streamlit for fast iteration (swap for a polished React/Flutter front end later if time allows)
- **Hosting for demo:** local, or Streamlit Community Cloud free tier

**Scaling the rate limit:** register two separate Gemini API keys — one dedicated to high-volume ingestion parsing, one dedicated to deeper reasoning/routing — effectively doubling the usable free-tier throughput.

### 2.4 Agent-by-Agent Breakdown

| Agent | Input | Job | Output |
|---|---|---|---|
| 1 — Ingestion Filter | Raw RSS/API text | Extract event type, location, coordinates, severity, confidence | Structured JSON event |
| 2 — Graph Explorer | Structured event + Supabase graph | Find directly affected + downstream-dependent nodes | List of exposed regions/commodities |
| 3 — Ripple Evaluator | Exposed nodes + trade volumes | Estimate time-to-shortage per region; run quick Monte Carlo on 2–3 routing alternatives | Ranked reroute suggestions + confidence score |
| Dashboard | All of the above | Visualize heatmap, show source citations, expose Approve / Reject / Adjust | Human decision logged |

### 2.5 Feature Tiers — MVP vs. Stretch

**MVP (must work for the demo):**
- Live ingestion from at least two real feeds (e.g., GDACS + one news RSS)
- A static trade graph pre-loaded for a handful of countries and 2–3 commodities (e.g., LPG, diesel, wheat)
- One full pipeline run: shock detected → ripple calculated → one concrete reroute suggested
- Working Approve/Reject button on the dashboard, with the decision logged
- A visible "data confidence" badge per region

**Stretch (only if time allows):**
- Full "Sovereign Recuperation Index" scoring model
- Multilingual ingestion (vernacular-language local news translated before processing)
- Live maritime tracking via AIS/OpenSky-style feeds
- Mobile-responsive interface

### 2.6 Closing the Equity Gap (concretely, not just as a rubric answer)
This directly answers the gap previously flagged in feedback: *if marginalized regions are under-monitored, does the AI quietly treat "no data" as "no risk"?*

- Tag every region in the graph with a **monitoring density score** — a proxy built from how often it appears in live feeds historically, supplemented by publicly available connectivity stats (e.g., ITU internet/mobile penetration data) where available.
- Where monitoring density is low, the dashboard does **not** default to "no risk detected." It shows an explicit **"low confidence — verify manually"** flag instead, so the human reviewer knows exactly where the AI's blind spots are rather than trusting silence.

### 2.7 Team Execution Split (2-person build)
- **Dev 1 — Data & Graph Engineer:** Supabase schema design, OEC/Comtrade data import, RSS/API connector scripts.
- **Dev 2 — Agent & Interface Engineer:** LangGraph state machine, Gemini prompt design, Streamlit dashboard and HITL controls.

### 2.8 Build Sequence (phased, not deadline-bound)
1. **Setup** — repo, API keys, Supabase project
2. **Static graph** — load OEC/Comtrade data for ~5 countries × 2–3 commodities
3. **Ingestion agent** — get one live feed parsing reliably into structured events
4. **Ripple evaluator** — graph traversal + basic Monte Carlo + dummy rerouting logic
5. **Dashboard + HITL** — heatmap, ranked suggestions, approve/reject control
6. **Polish** — demo script, stretch features if time remains

### 2.9 Demo Script Outline
1. State the problem in one sentence with a relatable framing
2. Show the dashboard idle, then a shock event ingested live on screen
3. Show the ripple calculation resolve into a ranked reroute suggestion with a confidence badge
4. Administrator clicks Approve — show the resulting state change
5. Close on the responsible-AI angle: *"At no point does this system act on its own."*

### 2.10 Risk Register
| Risk | Mitigation |
|---|---|
| Gemini free-tier rate limits (10 RPM) | Two API keys split across ingestion vs. reasoning; cache repeated lookups |
| Stale or missing data for some regions | Surfaced honestly via the confidence badge — doubles as the responsible-AI feature |
| Demo data feeling fake | Replay real historical events (e.g., a past earthquake, a known shipping-route disruption) as if live, rather than inventing synthetic scenarios from scratch |
| Scope creep | MVP list above is the contract — stretch features only after MVP is fully working end-to-end |

### 2.11 Rubric Self-Check (USAII)
- **Problem understanding:** concrete, scoped to infrastructural shock → resource shortage, not abstract
- **AI reasoning:** LLM does what LLMs are good at (parsing chaos); deterministic code does the math — explicit justification for why AI is the right tool, not the only tool
- **Decision support, not autonomy:** every output ends at a human approval step
- **Responsible AI / HITL:** specific risk named (under-monitored regions), specific mitigation built into the architecture (confidence flagging), not just a policy statement

---

## PART 3 — RESOURCES & DATASETS (exact sign-up steps, URLs, and limits)

Everything below has been checked against current provider documentation. Where a provider's free-tier terms change frequently (notably the LLM), re-check the linked page before you build — the *mechanism* described here is stable even if the exact numbers drift.

### 3.1 Live Shock Signals — Natural Hazards

| Source | What you get | URL | How to access | Free-tier limits / notes |
|---|---|---|---|---|
| **GDACS** (Global Disaster Alert and Coordination System) | Earthquakes, tropical cyclones, floods, volcanoes — alert level (Green/Orange/Red), coordinates, affected population estimate | RSS: `http://www.gdacs.org/xml/rss.xml` · REST/GeoJSON: `https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH` | No signup, no key needed for the RSS/REST endpoints. (An optional free account at gdacs.org lets you also get email/SMS push alerts, but you don't need it for the API.) | Public, no rate limit documented for normal polling; don't hammer it — poll every few minutes, it updates roughly every 6 minutes anyway. |
| **USGS Earthquake Hazards API** | Real-time global seismic events — magnitude, depth, coordinates, tsunami flag | `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson` (or `_day`, `_week`); custom queries via `https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&...` | No signup, no API key | Free, no documented hard rate limit; this is the most reliable single feed for the seismic-shock half of your "natural disaster" coverage. |
| **NOAA / National Weather Service Alerts API** | Active US weather alerts (storms, floods, heat) by lat/long | `https://api.weather.gov/alerts/active?point={lat},{lon}` | No signup, no key | **US-only.** Rate-limited informally (recommend ≤1 request every 30 sec); fine for a demo. |
| **Open-Meteo** | Global weather forecast + historical weather, any coordinates, marine + air quality endpoints | `https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..` | No signup, no key | **This is your global complement to NOAA** since NOAA only covers the US and you're building this for worldwide use. Free for non-commercial use, no documented hard cap (soft guidance: contact them past ~10,000 requests/day, which you won't hit in a hackathon demo). |

### 3.2 Live Shock Signals — Conflict & Civil Unrest

| Source | What you get | URL | How to access | Free-tier limits / notes |
|---|---|---|---|---|
| **ACLED** (Armed Conflict Location & Event Data Project) | Disaggregated conflict/protest events worldwide — location, date, actors, fatalities | Register at `https://acleddata.com/user/register` → API base `https://acleddata.com/api/...` per their docs | Create a myACLED account (use an institutional/university email if you have one — `.edu`/college domain gets you a higher access tier automatically; a personal Gmail still works, just at a lower tier). After verifying + accepting the Terms of Use, generate an access key from your account dashboard. | Default row limit of 5,000 per call (use `limit=` and pagination for more); access tier and any further caps depend on the email domain you register with. Budget half a day for registration — it is not instant. |
| **Reuters World News RSS** (or any major wire RSS) | General-purpose geopolitical headlines as a secondary signal | Standard RSS feed parsing | No signup | Treat as supplementary signal only — RSS headlines need the LLM filter to extract anything structured; don't rely on this as your primary feed. |

### 3.3 Trade & Supply-Chain Dependency Baseline (the static "graph")

| Source | What you get | URL | How to access | Free-tier limits / notes |
|---|---|---|---|---|
| **UN Comtrade** (this is your primary source — use this one) | Country-to-country import/export data by HS commodity code (LPG, refined petroleum, wheat, medical goods, etc.) | Developer portal: `https://comtradedeveloper.un.org/` · Account creation guide: `https://uncomtrade.org/docs/how-to-create-an-account/` | Sign up for a free account on the developer portal, subscribe to the **"comtrade - v1"** product (this is the free API tier), generate a subscription key. Python helper library: `pip install comtradeapicall` (official, from the UN Comtrade GitHub). | Free tier has a **daily call cap** (check the live number on the developer portal at signup — it's modest, in the hundreds/day range). This is enough because you only need to pull the trade-baseline graph for a handful of countries/commodities *once* and cache it in Supabase — you are not calling this live during the demo. |
| **OEC (Observatory of Economic Complexity)** | Same underlying trade data, nicer visual profile pages, useful for sanity-checking numbers or pulling a quick chart for your pitch deck | `https://oec.world/en/resources/api` | Many visualizations and historical profile-page downloads are free with no login; full **programmatic API access requires a Pro/Premium subscription**, which is not free. | **Don't rely on the OEC API in your build** — use it only as a free reference/sanity-check tool in a browser. UN Comtrade is your actual data pipeline. |

### 3.4 Maritime / Port Logistics (stretch feature)

| Source | What you get | URL | How to access | Free-tier limits / notes |
|---|---|---|---|---|
| **UNCTAD Port Call data** | Public statistics on port calls and shipping-line connectivity by country | `https://unctadstat.unctad.org/` (UNCTADstat database) | Free download, no signup for the public statistical tables | Static/periodic, not real-time — fine as a structural input to your graph, not as a live feed. |
| **aisstream.io** | Live, free AIS vessel tracking via WebSocket — position, port calls, voyage destination | `https://aisstream.io/` | Create a free account, get an API key, connect via WebSocket (`wss://stream.aisstream.io/v0/stream`) | Genuinely free for individual/hackathon use. This is your easiest path to a live "ship near a blocked strait" demo moment if you build the maritime stretch goal. |

### 3.5 Regional Plug-in: India-specific LPG/petroleum data (optional, if you want a local case study)
- **Open Government Data (OGD) Platform India** — `https://www.data.gov.in/` — search "LPG" or filter by Ministry of Petroleum and Natural Gas. Gives state/district-wise LPG connection counts and consumption data (e.g., Ujjwala Yojana connection rollout by district). Free, no signup for browsing/downloading CSVs; note that most of these specific resources do **not** have a live API (it's CSV download, not REST) — fine for pre-loading your static graph with a real regional case study.
- **PPAC** (Petroleum Planning & Analysis Cell, Govt. of India) — `https://ppac.gov.in/` — state-wise active LPG domestic customer counts and consumption statistics, free download.

### 3.6 The LLM — Gemini API (correcting a common misconception)
- **Get a key:** Google AI Studio → `https://aistudio.google.com/` → create/sign in with a Google account → generate an API key. No credit card needed for the free tier.
- **Model to use:** Gemini 2.5 Flash or whichever current Flash-tier model AI Studio shows as free when you build (the specific model name and exact RPM/RPD numbers shift every few months — check `https://ai.google.dev/gemini-api/docs/rate-limits` for the live numbers on the day you build, don't trust an old screenshot).
- **Important correction to the earlier plan:** rate limits are applied **per Google Cloud project, not per API key.** Generating two API keys inside the *same* project does **not** double your throughput — both keys draw from one shared quota. If you genuinely need more headroom for the demo, the correct move is to create **two separate Google AI Studio / Google Cloud projects** (each gets its own free-tier quota) and assign one to ingestion, one to reasoning — same idea as before, just done at the project level, not the key level.
- **Practical mitigation either way:** cache results aggressively (don't re-parse the same RSS item twice), batch multiple small extraction tasks into one prompt, and rely on deterministic Python for anything that doesn't need language understanding (the graph traversal, the Monte Carlo simulation).

### 3.7 Backend / Database
- **Supabase** — `https://supabase.com/` — sign up free, create a project (Postgres + auto-generated REST API + free dashboard).
- **Free-tier limits as of now:** 2 active projects, 500 MB database storage, 1 GB file storage, 5 GB bandwidth/egress per month, 50,000 monthly active users (irrelevant for you), no automatic backups.
- **The one gotcha that matters for a hackathon timeline:** free projects auto-pause after 7 days of total inactivity. If you build early and demo weeks later, ping the project (or set a free scheduled job to hit it) every few days so it isn't paused the morning of your submission.

### 3.8 Orchestration & Frontend
- **LangGraph** — open-source Python library, `pip install langgraph` — no account needed, just a pip install. Docs: `https://langchain-ai.github.io/langgraph/`.
- **Streamlit** — open-source Python library, `pip install streamlit` — no account needed to build locally. Free hosting for your demo via **Streamlit Community Cloud** (`https://streamlit.io/cloud`) — connect a GitHub repo, deploy free, no credit card.

### 3.9 Account-Creation Checklist (do these first, before writing any code)
1. Google AI Studio account → Gemini API key (5 minutes)
2. UN Comtrade developer account → subscribe to free "comtrade - v1" product → subscription key (15–20 minutes, includes email verification)
3. ACLED myACLED account → verify email → accept Terms of Use → generate access key (can take longer than expected — start this on day one, not the night before a demo)
4. Supabase account → new project (5 minutes)
5. aisstream.io account → API key (5 minutes) — only if you're building the maritime stretch goal
6. GitHub repo + Streamlit Community Cloud connection (10 minutes) — only needed when you're ready to deploy the demo publicly

No payment method is required for anything on this list.
