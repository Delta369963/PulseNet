"""Feed connectors — RSS-first, keyless open-data sources.

Each source implements FeedSource.fetch() -> list[RawItem]. Network failures are
isolated per-source: one dead feed never breaks the whole ingestion run.
"""
