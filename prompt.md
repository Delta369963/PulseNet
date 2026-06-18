### 1. Unified Inventory of Feeds, Datasets, and Peer Platform Tech Stacks

To build a globally competent, predictive logistics engine, we must bypass the generic web-scraping layer and directly tap the specialized, programmatic data pipelines utilized by advanced open-source threat intelligence dashboards and closed-source enterprise platforms.

#### Live Event Ingestion & Threat Feeds (The "Shocks")

* **GDELT Project (Global Dataset of Events, Language, and Tone):** A massive, open data ecosystem that monitors global broadcast, print, and web news in over 100 languages, updating every 15 minutes. GDELT uses advanced NLP to automatically extract spatial locations, actors, themes, and underlying sentiment metrics (such as the *Goldstein Scale* and *Tone*). This serves as the primary open-source intelligence feed for macroeconomic and socio-political friction points.
* **GDACS (Global Disaster Alert and Coordination System):** Jointly managed by the United Nations and the European Commission. It offers live XML, RSS, and structured GeoJSON endpoints delivering real-time telemetry on earthquakes, floods, tsunamis, and tropical cyclones. Crucially, it provides pre-calculated impact metrics, including affected populations and direct structural severity indexing.
* **ACLED (Armed Conflict Location & Event Data Project):** Highly accurate, disaggregated data stream for political violence and kinetic events. It maps precise latitude/longitude coordinates, dates, fatalities, and specific actor classification (e.g., state forces vs. rebel groups), ideal for tracking trade-route blockades or civil infrastructure interruptions.
* **AIS (Automatic Identification System) Open Hubs:** Open maritime data hubs tracking vessel coordinates and port-entry logs. Platforms like the *OpenSky Network* handle open-source aviation data; for maritime choke points (Suez Canal, Panama Canal, Bab-el-Mandeb), public scraping of marine port congestion metrics from regional port authority APIs provides the exact real-time delay vector.

#### Macroeconomic Baselines & Dependency Matrices (The "Trade Graph")

* **UN Comtrade API:** The gold standard for global trade statistics. It exposes an API providing comprehensive, structured bilateral trade data categorized by HS (Harmonized System) commodity codes. This gives the exact volume, financial value, and structural direction of essential commodities (such as LPG, wheat, or semiconductor-grade neon gas) passing between nations.
* **OEC (Observatory of Economic Complexity) API:** Transforms raw trade data into advanced relational graphs. It calculates indicators like the *Economic Complexity Index (ECI)* and product proximity scores, helping you determine how easily a nation can substitute a severed import link with an alternative trading partner.
* **World Bank & IMF API Matrix:** Exposes vital country-level macroeconomic structural parameters. We ingest metrics like GDP per capita, electrical grid density, and fiscal resilience reserves to parameterize the **Sovereign Recuperation Index (SRI)**, which models a nation's capacity to stabilize after an infrastructural blow.

#### Core Technologies of Inferred Platforms

* **Conflictly / Palantir Foundry Architecture:** Relies on an **Ontology Layer**. In Palantir, real-world assets (such as a specific oil refinery, an LPG shipping lane, or a regional rail corridor) are mapped as interconnected digital objects with states, relationships, and histories. Data tracking uses distributed processing engines (such as Apache Spark) coupled with a Graph Database (like Neo4j) to compute real-time path analysis.
* **GlobalThreatMap (OSS Stack):** Next.js with Mapbox GL JS for smooth client-side rendering of global coordinates. Its local implementations scrape local and regional RSS feeds across nearly 100 countries in native languages, using LLMs to run translation and schema formatting (`Zod` validation) before projecting the JSON payload onto geospatial layers.

---

### 2. Architecture A: Geo-Agentic Dependency & Ontology Network

This architecture mimics the Palantir Foundry/Aladdin model by defining an explicit real-world ontology using Python backend services, stateful agent routing, and a client-side geospatial rendering engine. It optimizes for visual impact, depth of reasoning, and centralized multi-country dependency graphing.

```
                    [ GDELT / GDACS / ACLED Live APIs ]
                                     │
                                     ▼
                ┌─────────────────────────────────────────┐
                │   Ingestion Service (FastAPI Cron)      │
                └────────────────────┬────────────────────┘
                                     │
                                     ▼
                ┌─────────────────────────────────────────┐
                │ LangGraph Multi-Agent Consensus Engine  │
                │ ├─ Agent Alpha (Primary Key - Ingest)   │
                │ ├─ Agent Beta  (Secondary Key - Ingest) │
                │ └─ Agent Gamma (Partner Key - Validate) │
                └────────────────────┬────────────────────┘
                                     │
                                     ▼
                ┌─────────────────────────────────────────┐
                │   Supabase Graph/Vector Layer (Postgres) │
                │   ├─ UN Comtrade / OEC Static Graph     │
                │   └─ Dynamic Active Threat Schema       │
                └────────────────────┬────────────────────┘
                                     │
                                     ▼
                ┌─────────────────────────────────────────┐
                │   FastAPI WebSocket / REST Gateways     │
                └────────────────────┬────────────────────┘
                                     │
                                     ▼
                ┌─────────────────────────────────────────┐
                │ Next.js Client Layer (Mapbox GL + Deck.gl)│
                └─────────────────────────────────────────┘

```

#### Detailed Backend Flow

1. **Ingestion:** A FastAPI background service runs an asynchronous cron loop every 15 minutes, pulling the latest XML/JSON payloads from GDELT, GDACS, and ACLED.
2. **Stateful Orchestration (LangGraph):** The raw unstructured string data is passed to a LangGraph multi-agent network.
* **Agent Alpha & Agent Beta** execute parallel requests using your two separate Gemini API keys. They isolate the coordinates, date, threat level (1–10), and the exact physical assets or commodities impacted.
* **Agent Gamma** acts as the Byzantine Consensus Judge, computing the overlap of their predictions. If consensus is reached, it outputs a validated `pydantic` JSON payload.


3. **Ontology Database Mapping:** The backend reads the payload and queries the static UN Comtrade/OEC graph tables stored in Supabase. It matches the impacted country or asset with its global export dependencies. If an earthquake hits a major LPG processing zone, the system queries: *Which nations rely on this node? What are their secondary supply options?*
4. **Causal Graph Generation:** The system uses Python's `networkx` library to build a Directed Acyclic Graph (DAG) detailing the downstream chain reactions with calculated decay probabilities.
5. **Streaming Interface:** The DAG and active threats are exposed via FastAPI WebSockets to the Next.js frontend, where Mapbox GL JS and Deck.gl render 3D flight paths, arc layers, and geographic blast radii over an interactive globe.

---

### 3. Architecture B: Event-Driven Decentralized Reactive Engine

This design is a highly optimized, lean pipeline. It avoids a complex frontend stack and heavy centralized infrastructure, focusing instead on rapid computational throughput, low latency, and deterministic python processing loops. It runs seamlessly on free-tier microservices or a local cluster.

```
                  [ GDELT / GDACS Real-Time Feeds ]
                                  │
                                  ▼
                ┌───────────────────────────────────┐
                │   FastAPI Python Event Receiver   │
                └─────────────────┬─────────────────┘
                                  │
                                  ▼
                ┌───────────────────────────────────┐
                │  Asynchronous Pipeline Manager    │
                │  (Load-Balanced Gemini API Hooks) │
                └─────────────────┬─────────────────┘
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
┌─────────────────────────────────┐               ┌─────────────────────────────────┐
│ Causal Analyzer (Gemini Pro)   │               │ Structural Math Processor       │
│ - Long-Context Matrix Ingestion │               │ - Deterministic Matrix Crunching│
└────────────────┬────────────────┘               └────────────────┬────────────────┘
                 │                                                 │
                 └────────────────────────┬────────────────────────┘
                                          │
                                          ▼
                ┌───────────────────────────────────┐
                │ Supabase Unified Key-Value Store  │
                └─────────────────┬─────────────────┘
                                  │
                                  ▼
                ┌───────────────────────────────────┐
                │ Streamlit Operational Dashboard   │
                └───────────────────────────────────┘

```

#### Detailed Backend Flow

1. **Lightweight Event Routing:** An asynchronous FastAPI application accepts incoming event hooks.
2. **API Load Balancing:** To maximize the free tier's Requests Per Minute (RPM) constraints, incoming tasks are divided into a dual-worker queue using Python's `asyncio`. Worker 1 uses Gemini Key A for initial structural formatting. Worker 2 uses Gemini Key B for downstream reasoning.
3. **Context-Splitting Matrix Processing:** Instead of making multiple small LLM calls that deplete your API limits, Architecture B group-batches events. When a major disruption is logged, the system utilizes Gemini’s 1-million+ context window to run a massive **In-Context Learning (ICL)** operation. It passes the raw event text along with a massive, localized chunk of raw UN Comtrade import/export data directly into the prompt memory.
4. **Deterministic Computation Hybridization:** The AI does not compute the supply-chain equilibrium math; it only extracts the causal variables. The structural data is fed directly into a local Python script running deterministic matrix matrix multiplications (`numpy`/`pandas`) over the trade data to map supply and demand balances across nations, generating precise equilibrium models.
5. **Minimalist Dashboard UI:** The resulting network states are stored in Supabase and instantly visualized using a clean **Streamlit** dashboard. This interface focuses entirely on operational data tables, risk cascade trees, and simple interactive control components.

---

### 4. System Evaluation, Testing, and Documentation Framework

To achieve high academic validity and ensure your predictions are mathematically sound rather than speculative, you must build an automated, backward-chaining evaluation harness.

#### Probabilistic Chain-Reaction Modeling

Every cascade generated by PulseNet is treated as a chain of conditional probabilities bound by the **Sovereign Recuperation Index (SRI)**. The systemic confidence of any downstream domino event ($Event_n$) is computed mathematically:

$$\text{Confidence}(Event_n) = \left( \prod_{i=1}^{n} P(Event_i \mid Event_{i-1}) \right) \times \left( 1 - \frac{1}{\text{SRI}_{\text{target}}} \right)$$

Where the SRI is a function of the nation’s infrastructure and fiscal capabilities:


$$\text{SRI} = w_1(\text{GDP}_{\text{capita}}) + w_2(\text{Grid}_{\text{density}}) - w_3(\text{Historical}_{\text{Volatility}})$$

If Agent Alpha and Beta detect a shock, the cascade branches down the graph:

#### The Backward-Chaining Diagnostic Test

To test the engine’s predictive validity, you will write a validation harness (`/tests/backward_chain_test.py`) that uses historical events as a baseline.

1. **The Seed Target:** You hardcode a historic supply-chain failure into the test environment (e.g., the 2022 global neon gas supply shock causing semiconductor manufacturing pauses).
2. **The Execution:** The system runs a backward-chaining routing prompt through Gemini: *"Identify the necessary upstream industrial components for global semiconductor manufacturing $\rightarrow$ Locate the primary refining sources of high-purity Neon gas $\rightarrow$ Map the transit nodes of that commodity."*
3. **The Verification Layer:** The test harness inputs the raw geopolitical news data from Q1 2022 into the front of the ingestion engine. The forward-facing pipeline runs completely blind. The test passes **only** if the forward pipeline places the `Semiconductor Manufacturing Shortage` into its high-probability prediction output within a specific confidence threshold ($P > 0.45$).

#### Automated Ledger Documentation Schema

To satisfy the USAII "Responsible AI and Interpretability" metric, you will write a utility that automatically documents the internal consensus state of every event directly into Supabase.

```sql
CREATE TABLE systemic_consensus_ledger (
    crisis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source_feed_url TEXT NOT NULL,
    detected_shock_vector JSONB NOT NULL, -- Latitude, Longitude, Severity, Initial Asset
    agent_alpha_raw JSONB NOT NULL,       -- Raw generation probabilities from Key A
    agent_beta_raw JSONB NOT NULL,        -- Raw generation probabilities from Key B
    byzantine_agreement_delta FLOAT,     -- The variance metric between predictions
    calculated_cascade_dag JSONB NOT NULL, -- The resulting prediction tree with confidences
    human_in_the_loop_override BOOLEAN DEFAULT FALSE,
    authorized_by_admin TEXT
);

```

By logging every step of the agent consensus process and the mathematical graph parameters, you can open this database ledger during your hackathon presentation. This demonstrates to the judges a completely transparent, reproducible, and highly rigorous "Decision Support System."