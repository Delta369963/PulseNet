"""Probabilistic chain-reaction modeling — prompt §4.

Confidence of a downstream domino event E_n:

    Confidence(E_n) = ( PROD_{i=1..n} P(E_i | E_{i-1}) ) * ( 1 - 1/SRI_target )

We build the cascade as a Directed Acyclic Graph (networkx). Each edge carries a
conditional probability P(child | parent); each node's confidence is the product
of edge probabilities along its path from the root, scaled by the recuperation
factor (1 - 1/SRI) of the impacted nation.

Pure math: no I/O, no LLM. The LLM only supplies the causal *variables*; this
module computes the equilibrium.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx


def recuperation_factor(sri: float) -> float:
    """Resilience factor derived from SRI.

    The prompt's formula uses (1 - 1/SRI_target) which requires SRI > 1 to be
    non-negative. Our SRI is normalised to [0.05, 1.0], so we rescale it to
    [1, 5] first (sri_scaled = 1 + sri * 4) before applying the formula.

    Results:
        SRI=0.0  → 0.0   (no resilience)
        SRI=0.5  → 0.667 (moderate)
        SRI=1.0  → 0.80  (high resilience)
    """
    sri_scaled = max(1.0, 1.0 + max(0.0, sri) * 4.0)
    return round(max(0.0, min(1.0, 1.0 - 1.0 / sri_scaled)), 4)



@dataclass
class CascadeNode:
    """One event in the cascade tree."""

    id: str
    label: str
    cond_prob: float = 1.0  # P(this | parent)
    sri: float = 1.0        # SRI of the impacted target (root uses 1.0)
    confidence: float = 1.0  # computed
    parent: str | None = None


@dataclass
class CascadeDag:
    nodes: list[CascadeNode] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "condProb": round(n.cond_prob, 4),
                    "sri": round(n.sri, 3),
                    "confidence": round(n.confidence, 4),
                    "parent": n.parent,
                }
                for n in self.nodes
            ],
            "edges": [{"from": a, "to": b} for a, b in self.edges],
        }


def build_cascade(
    root: CascadeNode,
    children: list[CascadeNode],
) -> CascadeDag:
    """Build a one-level cascade (root -> each child) with computed confidences.

    The confidence formula multiplies the path probability by the child's
    recuperation factor. SRI is interpreted so that a *less* resilient nation
    (low SRI) yields a *higher* downstream-shortage confidence: we use
    (1 - recuperation_factor) as the vulnerability multiplier.
    """
    g = nx.DiGraph()
    root.confidence = 1.0
    g.add_node(root.id, label=root.label)
    nodes = [root]
    edges: list[tuple[str, str]] = []

    for child in children:
        vulnerability = 1.0 - recuperation_factor(child.sri)
        child.parent = root.id
        # path probability from root = root(1.0) * P(child|root)
        child.confidence = round(child.cond_prob * vulnerability, 4)
        g.add_node(child.id, label=child.label)
        g.add_edge(root.id, child.id, prob=child.cond_prob)
        nodes.append(child)
        edges.append((root.id, child.id))

    # Guard: a cascade must be acyclic.
    assert nx.is_directed_acyclic_graph(g), "cascade graph must be a DAG"
    return CascadeDag(nodes=nodes, edges=edges)


def path_confidence(cond_probs: list[float], sri_target: float) -> float:
    """Confidence(E_n) for a single chain of conditional probabilities.

    Implements the prompt §4 formula directly:
        (PROD cond_probs) * (1 - 1/SRI_target)
    """
    product = 1.0
    for p in cond_probs:
        product *= max(0.0, min(1.0, p))
    return round(product * recuperation_factor(sri_target), 4)
