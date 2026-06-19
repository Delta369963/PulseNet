# PulseNet Engine — API Keys Guide

## Required keys (2 total — all from free tiers)

### GEMINI_API_KEY_A and GEMINI_API_KEY_B

Used by: Agent Alpha (Key A) + Agent Beta (Key B) for parallel consensus parsing.

**How to get (takes ~2 min each):**
1. Go to https://aistudio.google.com
2. Click "Get API key" → "Create API key in new project"
3. Copy the key into `.env` as `GEMINI_API_KEY_A`
4. Log into a **different** Google account (or create a new Google Cloud project)
5. Repeat to get `GEMINI_API_KEY_B`

**Why two keys?** Free tier is ~15 RPM per key. Running Alpha and Beta in parallel means both parse the same batch simultaneously — without burning double the RPM, since they each get a different role. Combined budget ≈ 30 RPM, enough for real-time ingestion.

**Model:** `gemini-2.5-flash` (default) — best cost/context balance on free tier.

---

## Optional keys (engine works without them)

### SEARCH_API_KEY (TS fallback web-search only)

Only needed if you run ingestion WITHOUT the Python engine. The Python engine uses RSS feeds (keyless). The TS fallback only needs this for web-search; USGS always works without any key.

**Options (all have free tiers):**
- **Serper.dev** — https://serper.dev → "Sign up" → copy API key → 2,500 free queries/month
- **Tavily** — https://tavily.com → API section → 1,000 free queries/month
- **Bing Search API** — Azure portal, free tier 1,000/month

### ACLED_KEY + ACLED_EMAIL (conflict feed)

Used for: ACLED disaggregated political violence data (kinetic events, trade-route blockades).

**How to get (takes 1–3 days for approval):**
1. Go to https://acleddata.com/access/
2. Click "Register for access"
3. Fill in institutional/research context
4. Wait for email approval
5. Set both `ACLED_KEY` and `ACLED_EMAIL` in `.env`

The engine is env-gated on ACLED — it stays dark if these are missing (GDELT + GDACS + ReliefWeb cover the gap).

### COMTRADE_KEY (optional rate-limit upgrade)

UN Comtrade works keyless at low volume. A free API key just raises your rate limit.
- https://comtradeplus.un.org → Register → copy key → set `COMTRADE_KEY`

---

## Keyless data sources (already wired, no signup needed)

| Source | Endpoint | Used for |
|---|---|---|
| USGS | earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson | Seismic shocks |
| GDACS | gdacs.org/xml/rss.xml | Disasters (earthquakes, floods, cyclones) |
| ReliefWeb | reliefweb.int/updates/rss.xml | Humanitarian crises |
| GDELT | api.gdeltproject.org | Global news (port closures, supply shocks) |
| Al Jazeera RSS | aljazeera.com/xml/rss/all.xml | Regional news |
| World Bank API | api.worldbank.org/v2 | SRI inputs (GDP, grid) |
