"""Streamlit dashboard — human review layer with HITL controls."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from src.config import COUNTRY_NAMES, COUNTRY_COORDS, USE_GEMINI
from src.database import (
    init_db,
    get_events,
    get_ripple_results,
    get_reroute_suggestions,
    get_decisions,
    update_suggestion_status,
)
from src.feeds.connectors import fetch_all_feeds
from src.pipeline.workflow import run_pipeline
from scripts.seed_database import main as seed_db

# Page config
st.set_page_config(
    page_title="PulseNet",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1a1a2e; }
    .sub-header { color: #666; font-size: 1rem; margin-bottom: 1.5rem; }
    .confidence-low { background: #fff3cd; border: 1px solid #ffc107; padding: 8px 12px; border-radius: 6px; }
    .confidence-high { background: #d4edda; border: 1px solid #28a745; padding: 8px 12px; border-radius: 6px; }
    .decision-log { font-size: 0.85rem; color: #555; }
    .badge-red { color: #dc3545; font-weight: bold; }
    .badge-orange { color: #fd7e14; font-weight: bold; }
    .badge-green { color: #28a745; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


def ensure_db():
    init_db()
    from src.database import get_trade_edges
    if not get_trade_edges():
        seed_db()


def severity_badge(severity: str) -> str:
    colors = {"red": "🔴", "orange": "🟠", "green": "🟢", "unknown": "⚪"}
    return f"{colors.get(severity, '⚪')} {severity.upper()}"


def confidence_badge(confidence: float, low_flag: bool = False) -> str:
    if low_flag or confidence < 0.45:
        return "⚠️ LOW CONFIDENCE — verify manually"
    if confidence >= 0.7:
        return f"✅ High confidence ({confidence:.0%})"
    return f"🔶 Medium confidence ({confidence:.0%})"


def render_heatmap(ripple_results: list):
    if not ripple_results:
        st.info("No ripple data to display. Run the pipeline first.")
        return

    rows = []
    for r in ripple_results:
        code = r["country_code"]
        coords = COUNTRY_COORDS.get(code)
        if coords:
            rows.append({
                "country": COUNTRY_NAMES.get(code, code),
                "country_code": code,
                "lat": coords[0],
                "lon": coords[1],
                "days_to_shortage": r["time_to_shortage_days"],
                "commodity": r["commodity"],
                "confidence": r["confidence"],
                "low_confidence": r.get("low_confidence_flag", False),
            })

    if not rows:
        st.warning("No mappable regions in results.")
        return

    df = pd.DataFrame(rows)

    fig = px.scatter_geo(
        df,
        lat="lat",
        lon="lon",
        color="days_to_shortage",
        size="days_to_shortage",
        hover_name="country",
        hover_data={
            "commodity": True,
            "days_to_shortage": ":.1f",
            "confidence": ":.0%",
            "country_code": True,
            "lat": False,
            "lon": False,
        },
        color_continuous_scale="RdYlGn_r",
        title="Time-to-Shortage Heatmap (days)",
        size_max=25,
    )
    fig.update_geos(showcountries=True, showcoastlines=True, projection_type="natural earth")
    fig.update_layout(height=450, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # Table with confidence badges
    display_df = df[["country", "country_code", "commodity", "days_to_shortage", "confidence", "low_confidence"]].copy()
    display_df["confidence_label"] = display_df.apply(
        lambda row: confidence_badge(row["confidence"], row["low_confidence"]), axis=1
    )
    st.dataframe(
        display_df[["country", "commodity", "days_to_shortage", "confidence_label"]],
        use_container_width=True,
        hide_index=True,
    )


def render_reroute_suggestions(suggestions: list, event_id: str):
    if not suggestions:
        st.info("No reroute suggestions yet.")
        return

    for s in suggestions:
        status = s.get("status", "pending")
        status_icon = {"pending": "⏳", "approved": "✅", "rejected": "❌", "adjusted": "🔧"}.get(status, "⏳")

        with st.container():
            st.markdown(f"### {status_icon} Rank #{s.get('rank', '?')}: {s.get('commodity', '')} reroute")
            st.markdown(f"**Route:** {s.get('route_description', 'N/A')}")
            st.markdown(
                f"Supplier: **{COUNTRY_NAMES.get(s.get('alternative_supplier', ''), s.get('alternative_supplier', ''))}** "
                f"→ Destination: **{COUNTRY_NAMES.get(s.get('to_country', ''), s.get('to_country', ''))}**"
            )
            col1, col2, col3 = st.columns(3)
            col1.metric("Est. delay", f"{s.get('estimated_delay_days', 0):.0f} days")
            col2.metric("Success probability", f"{s.get('success_probability', 0):.0%}")
            col3.metric("Confidence", f"{s.get('confidence', 0):.0%}")

            low_flag = s.get("low_confidence_flag") or s.get("confidence", 1) < 0.45
            badge_class = "confidence-low" if low_flag else "confidence-high"
            st.markdown(
                f'<div class="{badge_class}">{confidence_badge(s.get("confidence", 0), low_flag)}</div>',
                unsafe_allow_html=True,
            )

            if status == "pending":
                note_key = f"note_{s['id']}"
                note = st.text_input("Reviewer note (optional)", key=note_key, placeholder="Reason for decision...")
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    if st.button("✅ Approve", key=f"approve_{s['id']}", type="primary"):
                        update_suggestion_status(s["id"], "approved", note)
                        st.success("Approved — decision logged.")
                        st.rerun()
                with btn_col2:
                    if st.button("❌ Reject", key=f"reject_{s['id']}"):
                        update_suggestion_status(s["id"], "rejected", note)
                        st.warning("Rejected — decision logged.")
                        st.rerun()
                with btn_col3:
                    if st.button("🔧 Adjust", key=f"adjust_{s['id']}"):
                        update_suggestion_status(s["id"], "adjusted", note)
                        st.info("Marked for adjustment — decision logged.")
                        st.rerun()
            else:
                st.caption(f"Status: {status} | Reviewed: {s.get('reviewed_at', 'N/A')}")
                if s.get("reviewer_note"):
                    st.caption(f"Note: {s['reviewer_note']}")

            st.divider()


def main():
    ensure_db()

    # Sidebar
    with st.sidebar:
        st.markdown("## PulseNet")
        st.caption("Predictive Decision-Support for Critical Resource Shortages")
        st.divider()

        gemini_status = "🟢 Active" if USE_GEMINI else "🟡 Rule-based fallback"
        st.markdown(f"**LLM:** {gemini_status}")
        st.markdown("**Mode:** Decision support only — no autonomous execution")

        st.divider()
        st.markdown("### Actions")

        if st.button("🔄 Fetch Live Feeds & Run Pipeline", type="primary", use_container_width=True):
            with st.spinner("Fetching GDACS, USGS, Reuters..."):
                raw_events = fetch_all_feeds()
                if not raw_events:
                    st.error("No events fetched from feeds.")
                else:
                    with st.spinner(f"Processing {len(raw_events)} events through agent pipeline..."):
                        result = run_pipeline(raw_events)
                        status = result.get("status", "unknown")
                        if status == "complete":
                            st.success(f"Pipeline complete! {len(result.get('ripple_results', []))} regions analyzed.")
                        else:
                            st.warning(f"Pipeline status: {status}")
                            if result.get("errors"):
                                for err in result["errors"]:
                                    st.error(err)
            st.rerun()

        if st.button("🗑️ Clear session", use_container_width=True):
            st.rerun()

        st.divider()
        st.markdown("### Data Sources")
        st.caption("• GDACS disaster alerts")
        st.caption("• USGS earthquake feed")
        st.caption("• Reuters World News RSS")
        st.caption("• UN Comtrade trade graph (static)")

    # Main content
    st.markdown('<p class="main-header">🌐 PulseNet Dashboard</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Predicts where the next shortage will hit — before it hits. '
        'Human administrator approves every action.</p>',
        unsafe_allow_html=True,
    )

    # Recent events
    events = get_events(limit=10)
    selected_event_id = None

    if events:
        st.subheader("📡 Recent Shock Events")

        # Prefer events that already have ripple analysis
        def event_sort_key(e):
            ripple_count = len(get_ripple_results(e["event_id"]))
            severity_rank = {"red": 0, "orange": 1, "green": 2, "unknown": 3}.get(e.get("severity", "unknown"), 4)
            return (0 if ripple_count > 0 else 1, severity_rank)

        events_sorted = sorted(events, key=event_sort_key)

        event_options = {}
        for e in events_sorted:
            ripple_count = len(get_ripple_results(e["event_id"]))
            processed_tag = " ✓ analyzed" if ripple_count > 0 else ""
            label = f"{e['source']} | {severity_badge(e.get('severity', 'unknown'))} | {e.get('title', 'N/A')[:55]}{processed_tag}"
            event_options[label] = e["event_id"]

        selected_label = st.selectbox("Select event to analyze", list(event_options.keys()))
        selected_event_id = event_options[selected_label]

        event = next(e for e in events if e["event_id"] == selected_event_id)
        with st.expander("Event details", expanded=False):
            st.markdown(f"**Type:** {event.get('event_type', 'N/A')}")
            st.markdown(f"**Severity:** {severity_badge(event.get('severity', 'unknown'))}")
            st.markdown(f"**Country:** {COUNTRY_NAMES.get(event.get('country_code', ''), event.get('country_code', 'Unknown'))}")
            st.markdown(f"**Source:** {event.get('source', 'N/A')}")
            st.markdown(f"**Description:** {event.get('description', 'N/A')}")
            if event.get("latitude") and event.get("longitude"):
                st.markdown(f"**Coordinates:** {event['latitude']:.2f}, {event['longitude']:.2f}")
    else:
        st.info("No events yet. Click **Fetch Live Feeds & Run Pipeline** in the sidebar.")

    st.divider()

    # Ripple heatmap
    st.subheader("🗺️ Ripple Analysis — Time-to-Shortage Heatmap")
    if selected_event_id:
        ripple = get_ripple_results(selected_event_id)
        render_heatmap(ripple)
    else:
        st.info("Select an event to view ripple analysis.")

    st.divider()

    # Reroute suggestions with HITL
    st.subheader("🚢 Ranked Reroute Suggestions")
    st.caption("Review each suggestion and approve, reject, or mark for adjustment. No action is executed automatically.")
    if selected_event_id:
        suggestions = get_reroute_suggestions(selected_event_id)
        render_reroute_suggestions(suggestions, selected_event_id)
    else:
        st.info("Select an event to view reroute suggestions.")

    st.divider()

    # Decision log
    st.subheader("📋 Decision Log")
    decisions = get_decisions(limit=10)
    if decisions:
        for d in decisions:
            action_icon = {"approved": "✅", "rejected": "❌", "adjusted": "🔧"}.get(d["action"], "📝")
            st.markdown(
                f'<p class="decision-log">{action_icon} <strong>{d["action"].upper()}</strong> '
                f'— Event {d.get("event_id", "N/A")} — {d.get("created_at", "")}'
                f'{" — Note: " + d["note"] if d.get("note") else ""}</p>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No decisions logged yet.")

    # Footer
    st.divider()
    st.caption(
        "PulseNet — Decision support only. At no point does this system act on its own. "
        "Low-confidence regions are flagged for manual verification, not silently treated as safe."
    )


if __name__ == "__main__":
    main()
