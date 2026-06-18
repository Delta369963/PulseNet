"""LangGraph pipeline orchestrating the three-agent workflow."""

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.ingestion import ingest_event
from src.agents.graph_explorer import explore_graph
from src.agents.ripple_evaluator import evaluate_ripple
from src.database import (
    mark_event_processed,
    save_event,
    save_ripple_results,
    save_reroute_suggestions,
)


class PipelineState(TypedDict, total=False):
    raw_events: List[Dict]
    structured_events: List[Dict]
    current_event: Dict
    exposed_regions: List[Dict]
    ripple_results: List[Dict]
    reroute_suggestions: List[Dict]
    errors: List[str]
    status: str


def ingest_node(state: PipelineState) -> PipelineState:
    raw_events = state.get("raw_events", [])
    structured = []
    errors = list(state.get("errors", []))

    for raw in raw_events:
        try:
            event = ingest_event(raw)
            save_event(event)
            structured.append(event)
        except Exception as e:
            errors.append(f"Ingestion failed for {raw.get('event_id')}: {e}")

    return {
        **state,
        "structured_events": structured,
        "errors": errors,
        "status": "ingested",
    }


def graph_explore_node(state: PipelineState) -> PipelineState:
    structured = state.get("structured_events", [])
    if not structured:
        return {**state, "status": "no_events"}

    # Process the most severe event first
    event = sorted(
        structured,
        key=lambda e: {"red": 0, "orange": 1, "green": 2, "unknown": 3}.get(e.get("severity", "unknown"), 4),
    )[0]

    try:
        exposed = explore_graph(event)
    except Exception as e:
        return {
            **state,
            "current_event": event,
            "errors": state.get("errors", []) + [f"Graph explore failed: {e}"],
            "status": "graph_error",
        }

    return {
        **state,
        "current_event": event,
        "exposed_regions": exposed,
        "status": "graph_explored",
    }


def ripple_evaluate_node(state: PipelineState) -> PipelineState:
    event = state.get("current_event")
    exposed = state.get("exposed_regions", [])

    if not event or not exposed:
        return {**state, "status": "no_ripple_data"}

    try:
        result = evaluate_ripple(event, exposed)
        event_id = event.get("event_id")

        save_ripple_results(event_id, result["ripple_results"])
        save_reroute_suggestions(event_id, result["reroute_suggestions"])
        mark_event_processed(event_id)

        return {
            **state,
            "ripple_results": result["ripple_results"],
            "reroute_suggestions": result["reroute_suggestions"],
            "status": "complete",
        }
    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"Ripple evaluation failed: {e}"],
            "status": "ripple_error",
        }


def build_pipeline():
    workflow = StateGraph(PipelineState)
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("graph_explore", graph_explore_node)
    workflow.add_node("ripple_evaluate", ripple_evaluate_node)

    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "graph_explore")
    workflow.add_edge("graph_explore", "ripple_evaluate")
    workflow.add_edge("ripple_evaluate", END)

    return workflow.compile()


def run_pipeline(raw_events: List[Dict]) -> Dict[str, Any]:
    pipeline = build_pipeline()
    initial_state: PipelineState = {
        "raw_events": raw_events,
        "structured_events": [],
        "errors": [],
        "status": "starting",
    }
    return pipeline.invoke(initial_state)
