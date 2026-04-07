"""
UFC Fight Graph - Dask Compute Backend.

Handles heavy computation: analytics aggregations, centrality calculations,
ML feature engineering. Pure compute - no I/O, no Neo4j, no HTTP.
"""

from __future__ import annotations
import logging
from typing import Optional
import pandas as pd
from dask import delayed
import dask.dataframe as dd
import dask
from config.settings import DaskConfig

logger = logging.getLogger(__name__)


# ==================== DELAYED TASKS ====================

@delayed
def compute_degree_centrality(df: pd.DataFrame) -> pd.DataFrame:
    """Compute degree centrality: unique opponents per fighter."""
    return df.groupby("fighter").agg(
        unique_opponents=("opponent", "nunique"),
        total_fights=("opponent", "count"),
    ).reset_index().sort_values("unique_opponents", ascending=False)


@delayed
def compute_eigenvector_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """Approximate eigenvector centrality via two-hop reach."""
    # Build adjacency
    adj = df[["fighter", "opponent"]].drop_duplicates()
    # Two-hop: fighter -> opponent -> opponent's opponent
    two_hop = adj.merge(adj, left_on="opponent", right_on="fighter", suffixes=("", "_2"))
    result = two_hop.groupby("fighter").agg(
        direct_opponents=("opponent", "nunique"),
        second_degree_reach=("opponent_2", "nunique"),
    ).reset_index()
    result["eigenvector_score"] = (
        result["direct_opponents"] * result["second_degree_reach"] / 100.0
    ).round(2)
    return result.sort_values("eigenvector_score", ascending=False)


@delayed
def compute_network_density(df: pd.DataFrame) -> pd.DataFrame:
    """Compute network density by weight class."""
    wc_fights = df.dropna(subset=["weight_class"])
    wc_counts = wc_fights.groupby("weight_class").agg(
        actual_fights=("fight_url", "nunique"),
        fighters_in_division="fighter",
    ).reset_index()
    wc_counts["fighter_count"] = wc_counts["fighters_in_division"].apply(
        lambda x: len(set(x)) if isinstance(x, list) else 1
    )
    wc_counts["max_possible"] = wc_counts["fighter_count"] * (wc_counts["fighter_count"] - 1) / 2
    wc_counts["density_pct"] = (
        wc_counts["actual_fights"] / wc_counts["max_possible"].replace(0, 1) * 100
    ).round(2)
    return wc_counts[["weight_class", "fighter_count", "actual_fights", "max_possible", "density_pct"]].sort_values(
        "density_pct", ascending=False
    )


@delayed
def compute_judge_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze judge scorecard agreement patterns."""
    if df.empty or "judge_name" not in df.columns:
        return pd.DataFrame()
    # Group by fight and judge
    fight_judges = df.groupby(["fight_url", "judge_name"]).agg(
        score=("score", "first"),
    ).reset_index()
    # Find fights with multiple judges
    multi_judge = fight_judges.groupby("fight_url").filter(lambda x: len(x) >= 2)
    # Count agreements per judge
    agreements = []
    for _, group in multi_judges.groupby("fight_url"):
        scores = group.set_index("judge_name")["score"]
        for judge, score in scores.items():
            match_count = (scores == score).sum() - 1  # Exclude self
            agreements.append({
                "judge": judge,
                "fight_url": group.name,
                "agreements": match_count,
            })
    if not agreements:
        return pd.DataFrame()
    agg_df = pd.DataFrame(agreements)
    return agg_df.groupby("judge").agg(
        total_agreements=("agreements", "sum"),
        fights_judged=("fight_url", "nunique"),
    ).reset_index().sort_values("total_agreements", ascending=False)


@delayed
def compute_finishing_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Compute finish rates by method, location, era."""
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["is_finish"] = df["method"].str.upper().str.contains("KO|TKO|SUB", na=False)
    return df.groupby(["weight_class"]).agg(
        total_fights=("fight_url", "nunique"),
        finishes=("is_finish", "sum"),
    ).reset_index().assign(
        finish_pct=lambda x: (x["finishes"] / x["total_fights"].replace(0, 1) * 100).round(1)
    ).sort_values("finish_pct", ascending=False)


# ==================== DASK CLUSTER MANAGER ====================

class DaskComputeEngine:
    """Manages Dask cluster for heavy analytics computation."""

    def __init__(self, config: DaskConfig):
        self._config = config
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from dask.distributed import Client
            self._client = Client(
                n_workers=self._config.n_workers,
                threads_per_worker=self._config.threads_per_worker,
                memory_limit=self._config.memory_limit,
                dashboard_address=self._config.dashboard_address,
            )
            logger.info(
                f"Dask cluster started: {self._config.n_workers} workers, "
                f"dashboard at {self._config.dashboard_address}"
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Dask cluster shut down.")

    def run_analytics_pipeline(self, fights_df: pd.DataFrame) -> dict:
        """
        Run full analytics pipeline using Dask delayed computations.
        Returns dict of results with DataFrames.
        """
        # Build task graph
        degree_task = compute_degree_centrality(fights_df)
        eigen_task = compute_eigenvector_proxy(fights_df)
        density_task = compute_network_density(fights_df)
        finish_task = compute_finishing_rates(fights_df)

        if "judge_name" in fights_df.columns:
            judge_task = compute_judge_consistency(fights_df)
            results = dask.compute(
                degree_task, eigen_task, density_task, finish_task, judge_task
            )
            return {
                "degree_centrality": results[0],
                "eigenvector_centrality": results[1],
                "network_density": results[2],
                "finishing_rates": results[3],
                "judge_consistency": results[4],
            }

        results = dask.compute(degree_task, eigen_task, density_task, finish_task)
        return {
            "degree_centrality": results[0],
            "eigenvector_centrality": results[1],
            "network_density": results[2],
            "finishing_rates": results[3],
        }

    def run_on_dataframe(self, df: pd.DataFrame, func, *args) -> pd.DataFrame:
        """
        Run a delayed function on a DataFrame through Dask.
        Useful for arbitrary compute operations.
        """
        task = delayed(func)(df, *args)
        return task.compute()
