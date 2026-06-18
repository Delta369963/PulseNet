# PulseNet — Walkthrough

A practical guide to running and operating PulseNet, the predictive decision-support
dashboard for critical resource shortages (LPG, diesel, wheat, pharma).

PulseNet predicts *where the next shortage will hit — before it hits* — by fusing live
shock signals (USGS earthquakes, web-searched supply-chain news) with a public trade
dependency graph, then handing a human administrator a one-click way to stop it.
**Decision-support only. No autonomous execution.**

---

## 1. Quick start (3 steps)

```bash
# 1. Install dependencies (already done in this environment, but for reference)
bun install

# 2. Create the database schema + seed the demo trade graph
bun run db:push
bun run prisma/seed.ts

# 3. Start the dev server
bun run dev
```

The app runs on **http://localhost:3000** and is visible in the **Preview Panel**
on the right side of this interface. Use **"Open in New Tab"** above the preview
for a full-window view.

> **Do not** run `bun run build` — this sandbox uses the auto dev server on port 3000 only.

---

## 2. What's pre-loaded (the demo state)

Running `prisma/seed.ts` loads a realistic starting point so the dashboard is alive
the moment you open it:

| Layer | Contents |
|---|---|
| **Trade graph** | 20 countries (South Asia, Middle East, East Asia, Europe, Africa, Eurasia), each tagged with an **equity-weighted monitoring density** score (0–1) |
| **Commodities** | 4 critical commodities — LPG, Refined Diesel, Wheat, Pharmaceuticals |
| **Trade edges** | ~44 directional supplier→consumer relationships with volume + import-share |
| **Shock event #1** | *Persian Gulf seismic event (replay)* — already evaluated, showing exposures across India / Bangladesh / Japan / Kenya / South Korea + 4 reroutes (1 approved, 1 rejected in audit trail) |
| **Shock event #2** | *Black Sea port closure (replay)* — left in `new` state so you can run the full pipeline yourself |
| **Audit trail** | Seeded history of prior ingest / evaluate / approve / reject decisions |

---

## 3. The golden-path demo (90 seconds)

This is the headline flow — do this first to see PulseNet work end-to-end:

### Step 1 — Open the dashboard
The landing page shows the ops dashboard:
- **Header**: PulseNet branding, live UTC clock, "FEEDS LIVE" badge, and a green **Run Ingestion** button
- **Stats bar**: 6 headline metrics (live shocks, exposed regions, pending reroutes, low-confidence count, countries, audit entries)
- **3-column grid**:
  - Left → **Live Shock Feed**
  - Center → **Global Threat Board** (world map) + **Exposed Regions** list
  - Right → **Reroute Queue** (human-approval controls)
- Below → **Responsible AI** governance panel + **Decision Log** audit trail
- **Sticky footer** with data sources + governance disclaimers

### Step 2 — Run the live ingestion agent
Click **Run Ingestion** (top-right, green button).

What happens behind the scenes:
1. The agent fetches the **real USGS earthquakes GeoJSON feed** (events ≥ M4.5 from the last day) — no API key needed.
2. It runs **web search** for current supply-chain disruption news ("port closure shipping disruption", "fuel shortage LPG diesel wheat").
3. It sends the raw news snippets to the **LLM ingestion filter** in a single batched prompt, which returns structured JSON events (type, severity, location, coordinates, affected supplier countries).
4. New events are deduplicated by `externalId` and inserted; the audit trail records each ingestion.

You'll see a toast: *"Ingested N new event(s) · M USGS + K news scanned · D deduped."*
The Live Shock Feed updates with the new events (look for `USGS` and `WebSearch` source badges).

### Step 3 — Select a shock and evaluate its ripple
1. Click the **"Black Sea grain port closures"** card in the Live Shock Feed (status: `NEW`).
2. Its epicenter appears on the threat board with a pulsing ring.
3. Click the **Evaluate Ripple** button (green, center-top).

What happens behind the scenes:
1. The **graph explorer** traverses every trade edge where an affected country (Russia/Ukraine) is the supplier, aggregating downstream consumers by commodity.
2. For each exposed (consumer, commodity) pair, it computes:
   - **Exposure share** — what % of the consumer's imports of that commodity come from the shocked supplier(s)
   - **Time-to-shortage** — estimated days until the deficit materializes
   - **Risk score** (0–100) — exposure share × severity weight
   - **Confidence** — capped by the consumer's monitoring density (equity weighting)
3. The **ripple evaluator** runs a **Monte Carlo simulation** (4,000 trials) on each candidate reroute, producing a shortage-window distribution and success probability.
4. The **LLM** writes concrete, approvable reroute titles + rationales (e.g. *"Pakistan Wheat: Shift from Russia/Ukraine to India"*) — with a deterministic fallback if the LLM is unavailable.
5. The shock's status flips to `EVALUATED`.

You'll see:
- **Exposed Regions** list populates (Egypt wheat risk 76, Kenya wheat 61, Pakistan diesel 51, …) — low-monitoring regions show a red `⚠ LOW CONFIDENCE — VERIFY` flag
- **Threat board** draws dashed ripple-flow lines from the shock epicenter to each exposure dot
- **Reroute Queue** fills with ranked reroute cards, each showing: from→to suppliers, success probability, shortage window (median + p95), cost increase, time-to-add, feasibility, MC trials

### Step 4 — Make a human-in-the-loop decision
On any pending reroute card, click one of:
- **Approve** — logs the decision, moves the card to the "Decided" section
- **Adjust** — opens a textarea for an administrator note, then logs as `adjusted`
- **Reject** — logs as rejected

A toast confirms: *"Reroute approved — logged to audit trail. No autonomous execution."*
The **Decision Log** at the bottom updates with the new entry (action, summary, actor, timestamp).

> **Key principle**: PulseNet never executes a reroute. It only predicts, explains, and proposes. Every action ends at a human.

### Step 5 — Inspect the responsible-AI layer
Scroll to the **RESPONSIBLE AI · GOVERNANCE STANCE** panel. It shows:
- **Decision-support only** — no autonomous execution
- **Equity-weighted** — the current count of low-confidence regions (those with sparse monitoring data that are explicitly flagged rather than silently treated as "no risk")
- **Explainable by design** — LLMs parse chaos; deterministic code does the math; every number is traceable to a source citation

This is the concrete answer to the equity gap: marginalized/under-monitored regions are *not* silently treated as "no risk" — they get an explicit flag so the human reviews exactly where the AI is weakest.

---

## 4. Feature reference

### Header controls
| Control | Action |
|---|---|
| **Run Ingestion** | Pulls live USGS + web-search signals, LLM-parses them into structured shock events |
| **Theme toggle** (moon/sun icon) | Switches dark/light mode (dark is default) |
| Live clock | UTC time, updates every second |
| `FEEDS LIVE` badge | Indicates the ingestion polling is active |

### Live Shock Feed (left panel)
Each card shows: shock-type icon, severity badge, status badge (NEW / EVALUATED / DISMISSED), title, location, description, source badge (USGS / WebSearch), exposure + reroute counts, ingestion confidence, and time-ago.

Click any card to select it and load its full detail into the center + right panels.

### Global Threat Board (center-top)
A dark world-map background with:
- **Pulsing epicenter markers** for each geolocated shock (color = severity: red=severe, orange=high, amber=moderate)
- **Exposure dots** for the selected shock's downstream regions (color = risk level)
- **Dashed ripple-flow lines** from the selected epicenter to each exposure
- **Legend** (bottom-left) and **plotted count** (top-right)
- Click any epicenter to select that shock

### Exposed Regions list (center-bottom)
For the selected shock, every downstream-exposed (country, commodity) pair with:
- Country name + region + commodity code
- Risk-score bar (color-coded: red ≥75, orange ≥55, amber ≥40, emerald <40)
- Time-to-shortage estimate
- Confidence badge (high/moderate/low)
- `⚠ LOW CONFIDENCE — VERIFY` flag for monitoring-density < 0.55
- The causal exposure path (e.g. *"Black Sea port closures → Russia (50% share) export halt → Egypt (50% of wheat imports)"*)

### Reroute Queue (right panel)
Ranked reroute suggestions, each with:
- LLM-written title + rationale
- From → To supplier swap
- **6 metrics**: success probability (from Monte Carlo), shortage window (median + p95), cost increase %, time-to-add days, feasibility %, MC trial count
- Source-citation link
- **HITL buttons**: Approve / Adjust (with note) / Reject
- Decided reroutes collapse into a "Decided" section showing who decided, when, and any note

### Decision Log (bottom)
A complete audit trail of every action: ingest, evaluate, approve, reject, adjust, dismiss. Each entry shows action icon, summary, actor (`system` / `ingestion-agent` / `ripple-agent` / `administrator`), and timestamp. Capped at 60 entries.

---

## 5. API reference (for developers)

All endpoints are under `/api` and return JSON.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/stats` | Headline dashboard metrics (shock/exposure/reroute/decision counts, low-confidence count) |
| `GET` | `/api/shocks` | List all shock events with exposure + reroute counts |
| `POST` | `/api/shocks/ingest` | Run the ingestion agent (USGS + web-search + LLM parse) |
| `GET` | `/api/shocks/{id}` | Full shock detail: exposures + reroutes + Monte Carlo outcomes |
| `PATCH` | `/api/shocks/{id}` | Update shock status (`{ "status": "dismissed" }`) |
| `POST` | `/api/ripple` | Run the ripple evaluator (`{ "shockId": "..." }`) |
| `GET` | `/api/decisions` | Audit trail (newest 60) |
| `POST` | `/api/decisions` | Record a HITL decision (`{ "suggestionId", "action": "approve"\|"reject"\|"adjust", "note"?, "actor"? }`) |
| `GET` | `/api/graph` | The static trade dependency graph (countries, commodities, edges) |

---

## 6. Architecture overview

```
[ USGS GeoJSON  +  Web-Search News ]
              │
              ▼
   ┌─────────────────────────────┐
   │ Agent 1 — Ingestion Filter   │  LLM parses unstructured news →
   │ (LLM: z-ai-web-dev-sdk)      │  structured shock events
   └─────────────────────────────┘
              │
              ▼
   ┌─────────────────────────────┐
   │ Agent 2 — Graph Explorer     │  Traverses Prisma trade graph for
   │ (deterministic TypeScript)   │  direct + downstream consumers
   └─────────────────────────────┘
              │
              ▼
   ┌─────────────────────────────┐
   │ Agent 3 — Ripple Evaluator   │  Monte Carlo (4k trials) +
   │ (Monte Carlo + LLM reroutes) │  LLM-written reroute rationales
   └─────────────────────────────┘
              │
              ▼
   ┌─────────────────────────────┐
   │ Dashboard — human review     │  Threat map + ranked reroutes +
   │ (Next.js + shadcn/ui)        │  Approve / Reject / Adjust
   └─────────────────────────────┘
```

**Design principle**: LLMs handle the unstructured chaos (text → structured event);
deterministic TypeScript handles the math (graph traversal, Monte Carlo). This keeps
the system explainable and avoids asking a language model to do anything it's bad at.

### Tech stack
- **Framework**: Next.js 16 (App Router) + TypeScript 5
- **Styling**: Tailwind CSS 4 + shadcn/ui (New York) + Lucide icons
- **Database**: Prisma ORM + SQLite
- **AI**: `z-ai-web-dev-sdk` (LLM chat completions + web search) — backend-only
- **Theme**: next-themes (dark default)

### Key source files
| File | Purpose |
|---|---|
| `prisma/schema.prisma` | Data model (Country, Commodity, TradeEdge, ShockEvent, ExposedRegion, RerouteSuggestion, AdminDecision) |
| `prisma/seed.ts` | Seeds the trade graph + 2 replay shock events + audit history |
| `src/lib/pulsenet/zai.ts` | ZAI SDK singleton + LLM/web-search helpers + JSON parser |
| `src/lib/pulsenet/geo.ts` | Haversine distance, nearest-country matching, equirectangular projection |
| `src/lib/pulsenet/ingest.ts` | Ingestion agent (USGS fetch + web-search + LLM parse) |
| `src/lib/pulsenet/ripple.ts` | Ripple evaluator (graph traversal + Monte Carlo + LLM reroutes) |
| `src/app/api/...` | All API routes (see §5) |
| `src/app/page.tsx` | Main dashboard orchestrator |
| `src/components/pulsenet/*` | Dashboard components (ThreatMap, ShockFeed, RerouteQueue, etc.) |

---

## 7. Resetting the demo

If you want to return to the clean pre-loaded state (Persian Gulf pre-evaluated + Black Sea awaiting evaluation):

```bash
bun run prisma/seed.ts
```

This wipes all runtime data (ingested shocks, evaluations, decisions) and reloads the
seeded trade graph + 2 replay events. Safe to run any time.

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard shows empty feed | Run `bun run prisma/seed.ts` to load demo data, then refresh |
| `Run Ingestion` returns 0 new events | Either USGS had no ≥M4.5 quakes in the last day, or all web-search results were deduped. Try again in a few minutes. |
| `Evaluate Ripple` shows 0 exposures | The shock's affected `countryCodes` don't match any supplier in the trade graph. This is honest output — not a bug. |
| Reroute cards show deterministic text instead of LLM text | The LLM call failed or timed out; the deterministic fallback kicked in. The reroute is still valid. |
| `prisma` errors after schema change | Run `bun run db:push` to sync the schema, then re-seed |
| Port 3000 already in use | The dev server should auto-restart on file changes; if a stale instance is running, kill it and re-run `bun run dev` |

---

## 9. Responsible-AI checklist (built in, not bolted on)

- ✅ **Decision-support only** — no autonomous execution of any reroute, ever
- ✅ **Equity-weighted** — low-monitoring-density regions get an explicit `⚠ LOW CONFIDENCE — VERIFY` flag, never silent "no risk"
- ✅ **Explainable** — every exposure has a causal path string; every reroute has a source citation + Monte Carlo breakdown
- ✅ **Human-in-the-loop** — every reroute ends at an Approve / Reject / Adjust step
- ✅ **Audit trail** — every action (ingest, evaluate, approve, reject, adjust, dismiss) is logged with actor + timestamp
- ✅ **Honest uncertainty** — Monte Carlo reports both median and p95 shortage windows, plus success probability, so the human sees the worst case

---

*PulseNet v0.9 — civic infrastructure, not a corporate or defense product.*
