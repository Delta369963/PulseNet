# PulseNet v2: Debugging & Architecture

## Known Issues Addressed in this Branch

### 1. Re-Evaluation "0 Exposed Regions / 0 Routes" Bug
**The Issue:**
When evaluating the supply chain ripple for certain ingested events, the UI would silently return `0 exposed regions, 0 reroutes proposed`, making it appear as though the calculations were broken.
**The Root Cause:**
- **Cache Masking:** Next.js was heavily caching the `/api/shocks/[id]` route. When an evaluation finished, the UI fetched the updated state, but Next.js instantly returned the old, un-evaluated JSON from memory.
- **Missing Toy Data:** The backend operates on a 20-country toy trade graph (`seed.ts`). If an event (e.g., an earthquake in Argentina) occurred outside these 20 countries, the graph traversal safely exited and returned `note: "No mapped supplier countries for this event."` However, the UI ignored this note and gave zero feedback.
**The Fix:**
- Added `{ cache: 'no-store' }` to the frontend fetch to guarantee real-time updates.
- Added a UI toast notification to explicitly display the engine's `note` when 0 exposures are generated, so users know *why* the evaluation stopped.

### 2. Ingestion Sparseness ("Nothing New Added")
**The Issue:**
Clicking "Ingest" often resulted in very few events appearing, or simply did nothing, despite feeds like Reuters having hundreds of articles.
**The Root Cause:**
- **Batch Constraints:** To prevent LLM rate-limiting, the system was constrained to `max_feed_items = 14`. Because it pulls from 10+ feeds concurrently, a high-volume feed like Reuters might only get 1 or 2 articles into the batch.
- **Silent Deduplication:** If the news hadn't updated, the system successfully downloaded the feeds, identified them as duplicates using `externalId`, and silently skipped them.
**The Fix:**
- Built an **Ingestion Debugger Architecture**. The UI now features a targeted ingestion strip (`[USGS] [GDACS] [ReliefWeb] [Reuters-Biz] [ACLED]`).
- The Next.js proxy and Python backend now accept a `?source=` parameter. When targeted, the engine drops all other feeds, isolates the target source, and temporarily bumps the limit to 20 items, allowing you to flood the AI with a single source's data.
- Updated the UI to explicitly notify the user if duplicates were skipped (e.g., `"Feed up to date: No new real-world events detected (14 duplicates skipped)."`).

### 3. Database Ghost Sessions
**The Issue:**
Running `make reset` cleared the main tables but left the `SystemicConsensusLedger` intact, causing the Responsible AI panel to display ghost logs from previous sessions.
**The Fix:**
- Added `await db.systemicConsensusLedger.deleteMany()` to the teardown phase of `prisma/seed.ts`.

---

## Brief Architecture Overview for Teammates

PulseNet v2 is a predictive decision-support engine divided into two tiers:

1. **The Python Engine (FastAPI)**
   - **Ingestion (`services/ingest_service.py`)**: Fetches raw data concurrently from RSS feeds, USGS GeoJSON, and ACLED APIs. Uses Gemini LLMs to structure unstructured news into `ShockEvent` objects (conflict, earthquake, etc.).
   - **Evaluation (`services/ripple_service.py`)**: Takes a `ShockEvent`, maps it to the toy trade graph (SQLite), and calculates downstream supply shortages using the Systemic Risk Index (SRI). It then proposes humanitarian inbound supply routes or outbound export reroutes using a Monte Carlo simulation.

2. **The Frontend (Next.js App Router)**
   - **UI Component Layer**: Provides the visual Threat Board, Feed, and Responsible AI logging panel.
   - **API Proxies (`src/app/api`)**: Connects the UI to the Python engine while wrapping requests in fail-safes and fallback Typescript evaluators.

### How to use the Debug Architecture
When working on the Python agents, always use the **Targeted Ingest** strip below the UI header to test specific feeds in isolation. If you modify the `seed.ts` trade graph, run `make reset` to obliterate the SQLite database and start fresh.

> **Note**: This branch includes the `.env` file explicitly pushed so that the team can access the necessary API keys and database configuration without setup overhead.

## Testing & Debugging Report
During active backend testing, the following edge cases and bugs were discovered and addressed:

1. **Massive Geography Haversine Failures (USGS Ingestion)**
   - **Error:** Earthquakes in far eastern Russia (e.g., Kamchatka) were consistently returning `[]` for mapped countries, resulting in `0 exposed regions`.
   - **Root Cause:** The `nearest_countries` logic uses a `max_km = 1500.0` radius from a country's centroid. Russia's single centroid in the database is in central Siberia. Kamchatka is >3000km away, causing the geo-tagger to fail.
   - **Status:** Documented. Future fix requires either increasing the radius, using bounding boxes, or relying on the LLM to parse the `location_name` string instead of purely mathematical centroids.

2. **Missing Humanitarian Reroutes for UKR**
   - **Error:** Ingesting a UKR conflict event generated outbound export reroutes (Wheat) but no inbound humanitarian aid (Pharma).
   - **Root Cause:** The `seed.ts` toy database had 0 inbound edges mapped to `UKR`. The engine correctly halted inbound evaluation because it didn't know who supplied UKR.
   - **Status:** **Fixed**. Added `DEU->UKR` and `FRA->UKR` Pharma edges to the seed database.

3. **Confusing Humanitarian Aid Phrasing**
   - **Error:** When generating an inbound humanitarian route, the engine used the outbound template, resulting in confusing titles like: `Reroute Ukraine Pharmaceuticals: Ukraine → France`.
   - **Root Cause:** The `_build_reroutes` function did not fork its string templates based on the `is_inbound` flag.
   - **Status:** **Fixed**. Added conditional logic. Inbound aid routes now read: `Humanitarian Surge Ukraine Pharmaceuticals: France → Ukraine`.

4. **Rate Limiting vs Target Ingestion**
   - **Status:** The new `Targeted Ingest` UI strip correctly bypasses the `max_feed_items = 14` limit by pushing `20` items exclusively from a single source. This successfully solved the ingestion sparseness issue during testing.

5. **"Country Unresolvable" Edge Case**
   - **Error:** When the LLM was rate-limited or failed to extract an ISO-3 country code from events like *"[CONFLICT] India Faces LPG Shortage"* the engine gave up and returned `0 exposures`.
   - **Fix:** Implemented a deterministic text-matching fallback in `ripple_service.py` that scans the shock title for names present in the SQLite `Country` table. This acts as a robust safety net when the LLM is dark.

6. **Broken Cascade Chain Verification**
   - **Error:** Exposure paths for *inbound* humanitarian needs lacked the `→` arrow, breaking the cascade graph generation.
   - **Fix:** Unified the path formatting across both inbound and outbound logic, ensuring proper causal chain detection.

7. **Audit Trail Overwrite (HITL)**
   - **Error:** The human-in-the-loop (HITL) approve/reject actions were being pushed out of the `/api/decisions` 60-item limit by hundreds of rapid `evaluate` records.
   - **Fix:** Upgraded the API to support `?actor=...` filtering, allowing the frontend to pull specific audit records reliably.

## Getting Started

1. Ensure Python 3.11+ and Node.js are installed.
2. The `.env` file is included in this repository branch for immediate access.
3. Run `make install` to initialize the database and install dependencies.
4. Run `make dev` to boot both the Next.js frontend and the FastAPI Python engine simultaneously.
