"""
pipeline.py — ETL pipeline orchestrator.
Selects the correct extractor via EXTRACTOR_REGISTRY, runs the transform chain
(cleaner → chunker), embeds chunks, and delegates to the configured loader.
This file is the only place that knows which concrete implementations are active.
"""

# TODO: implemented in Prompt 1B
