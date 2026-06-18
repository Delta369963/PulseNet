"""Seed database with trade graph data."""

import sys
from pathlib import Path

# Allow running as script from pulsnet root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.trade_graph_seed import TRADE_EDGES
from src.database import init_db, seed_trade_graph


def main():
    init_db()
    seed_trade_graph(TRADE_EDGES)
    print(f"Seeded {len(TRADE_EDGES)} trade edges.")


if __name__ == "__main__":
    main()
