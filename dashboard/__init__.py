"""
UFC Knowledge Graph Dashboard — Streamlit UI Layer.

Thin UI: imports repositories (data access) and chart generators (visualizations).
Zero Cypher queries, zero data manipulation logic.
"""

from dashboard.app import main

__all__ = ["main"]
