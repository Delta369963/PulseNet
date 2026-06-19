"""Multi-agent consensus layer.

Alpha (Gemini Key A) and Beta (Gemini Key B) independently parse the same raw feed
text into structured shocks. Gamma judges their agreement (Byzantine delta) and
emits the validated payload. Every agent's raw output is logged to the ledger.
"""
