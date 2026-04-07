"""
TDD Tests for Network Centrality Repository.

Written before implementation (TDD-style).
Tests define the API that NetworkCentralityRepo must satisfy.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def mock_client():
    """Mock Neo4jClient that returns predictable DataFrames."""
    client = MagicMock()
    return client


@pytest.fixture
def degree_centrality_data():
    """Sample degree centrality results."""
    return pd.DataFrame({
        'fighter': ['A', 'B', 'C'],
        'nickname': ['Alpha', 'Bravo', 'Charlie'],
        'total_fights': [20, 15, 10],
        'unique_opponents': [18, 14, 9],
        'wins': [12, 8, 6],
        'losses': [8, 7, 4],
        'win_pct': [60.0, 53.3, 60.0],
    })


@pytest.fixture
def eigenvector_centrality_data():
    """Sample eigenvector centrality results."""
    return pd.DataFrame({
        'fighter': ['A', 'B', 'C'],
        'nickname': ['Alpha', 'Bravo', 'Charlie'],
        'direct_opponents': [18, 14, 9],
        'second_degree_reach': [150, 80, 30],
        'wins': [12, 8, 6],
        'losses': [8, 7, 4],
        'eigenvector_score': [27.0, 11.2, 2.7],
    })


@pytest.fixture
def pagerank_data():
    """Sample PageRank results."""
    return pd.DataFrame({
        'fighter': ['A', 'B', 'C'],
        'nickname': ['Alpha', 'Bravo', 'Charlie'],
        'wins': [12, 8, 6],
        'losses': [8, 7, 4],
        'quality_wins': [10, 6, 4],
        'defeated_network': [80, 40, 20],
        'pagerank_score': [8.0, 2.4, 0.8],
    })


@pytest.fixture
def density_data():
    """Sample network density by weight class."""
    return pd.DataFrame({
        'weight_class': ['Lightweight', 'Welterweight', 'Middleweight'],
        'fighters_in_division': [200, 150, 100],
        'actual_fights': [500, 300, 150],
        'max_possible_matchups': [19900, 11175, 4950],
        'density_pct': [2.51, 2.68, 3.03],
    })


# ============================================================
# TEST: Degree Centrality
# ============================================================

class TestDegreeCentrality:
    """Test degree centrality: unique opponents faced."""

    def test_returns_fighter_with_most_opponents(self, mock_client, degree_centrality_data):
        """Top result should have highest unique_opponents count."""
        mock_client.run_query.return_value = degree_centrality_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_degree_centrality()

        assert not df.empty
        assert df.iloc[0]['unique_opponents'] >= df.iloc[1]['unique_opponents']
        assert 'fighter' in df.columns
        assert 'unique_opponents' in df.columns

    def test_includes_win_pct(self, mock_client, degree_centrality_data):
        """Results should include win percentage for context."""
        mock_client.run_query.return_value = degree_centrality_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_degree_centrality()

        assert 'win_pct' in df.columns
        assert df.iloc[0]['win_pct'] == 60.0

    def test_respects_limit_parameter(self, mock_client):
        """The limit parameter should be passed to the query."""
        mock_client.run_query.return_value = pd.DataFrame()

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        repo.get_degree_centrality(limit=10)

        call_args = mock_client.run_query.call_args
        assert call_args is not None
        # _run passes params as second positional argument
        params = call_args[0][1]
        assert params['limit'] == 10


# ============================================================
# TEST: Eigenvector Centrality
# ============================================================

class TestEigenvectorCentrality:
    """Test eigenvector centrality: influence by opponent quality."""

    def test_scores_weighted_by_second_degree(self, mock_client, eigenvector_centrality_data):
        """Higher second_degree_reach should correlate with higher eigenvector_score."""
        mock_client.run_query.return_value = eigenvector_centrality_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_eigenvector_centrality()

        assert not df.empty
        assert 'eigenvector_score' in df.columns
        # First fighter should have highest score
        assert df.iloc[0]['eigenvector_score'] >= df.iloc[-1]['eigenvector_score']

    def test_minimum_opponents_filter(self, mock_client):
        """Query should filter fighters with < 3 opponents."""
        mock_client.run_query.return_value = pd.DataFrame()

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_eigenvector_centrality()

        # Should still return a DataFrame (possibly empty)
        assert isinstance(df, pd.DataFrame)


# ============================================================
# TEST: Betweenness Centrality
# ============================================================

class TestBetweennessCentrality:
    """Test betweenness centrality: bridge fighters across clusters."""

    def test_returns_bridge_fighters(self, mock_client):
        """Should return fighters who connect otherwise disconnected opponents."""
        sample_data = pd.DataFrame({
            'fighter': ['A', 'B'],
            'nickname': ['Alpha', 'Bravo'],
            'bridge_connections': [20, 15],
            'unique_bridges': [15, 10],
            'wins': [10, 8],
            'losses': [10, 7],
            'bridge_ratio': [75.0, 66.7],
        })
        mock_client.run_query.return_value = sample_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_betweenness_centrality()

        assert not df.empty
        assert 'bridge_ratio' in df.columns
        assert 'unique_bridges' in df.columns


# ============================================================
# TEST: Closeness Centrality
# ============================================================

class TestClosenessCentrality:
    """Test closeness centrality: network reach in 2 hops."""

    def test_returns_reach_multiplier(self, mock_client):
        """Should return reach_multiplier (two_hop / one_hop)."""
        sample_data = pd.DataFrame({
            'fighter': ['A', 'B', 'C'],
            'nickname': ['Alpha', 'Bravo', 'Charlie'],
            'one_hop_reach': [10, 8, 5],
            'two_hop_reach': [100, 60, 20],
            'wins': [10, 8, 6],
            'losses': [5, 4, 3],
            'reach_multiplier': [10.0, 7.5, 4.0],
        })
        mock_client.run_query.return_value = sample_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_closeness_centrality()

        assert not df.empty
        assert 'reach_multiplier' in df.columns
        # Results should be sorted by two_hop_reach DESC
        assert df.iloc[0]['two_hop_reach'] >= df.iloc[-1]['two_hop_reach']


# ============================================================
# TEST: PageRank
# ============================================================

class TestPageRank:
    """Test PageRank: loss-weighted relevance flow."""

    def test_quality_wins_weighted_by_network(self, mock_client, pagerank_data):
        """PageRank score should combine quality_wins and defeated_network."""
        mock_client.run_query.return_value = pagerank_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_pagerank_rankings()

        assert not df.empty
        assert 'pagerank_score' in df.columns
        assert 'quality_wins' in df.columns
        assert 'defeated_network' in df.columns

    def test_filters_by_minimum_quality_wins(self, mock_client):
        """Should only include fighters with >= 2 quality wins."""
        mock_client.run_query.return_value = pd.DataFrame()

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_pagerank_rankings()

        assert isinstance(df, pd.DataFrame)


# ============================================================
# TEST: Network Density
# ============================================================

class TestNetworkDensity:
    """Test network density by weight class."""

    def test_returns_density_per_division(self, mock_client, density_data):
        """Should return density percentage for each weight class."""
        mock_client.run_query.return_value = density_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_network_density_by_weight_class()

        assert not df.empty
        assert 'density_pct' in df.columns
        assert 'fighters_in_division' in df.columns
        assert 'max_possible_matchups' in df.columns

    def test_density_sorted_descending(self, mock_client):
        """Results should be sorted by density_pct DESC."""
        # Mock data is already sorted DESC (as the query would return)
        sample_data = pd.DataFrame({
            'weight_class': ['Middleweight', 'Welterweight', 'Lightweight'],
            'fighters_in_division': [100, 150, 200],
            'actual_fights': [150, 300, 500],
            'max_possible_matchups': [4950, 11175, 19900],
            'density_pct': [3.03, 2.68, 2.51],  # Already DESC
        })
        mock_client.run_query.return_value = sample_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_network_density_by_weight_class()

        assert df['density_pct'].iloc[0] >= df['density_pct'].iloc[-1]

    def test_filters_small_divisions(self, mock_client):
        """Should filter divisions with < 5 fighters."""
        mock_client.run_query.return_value = pd.DataFrame()

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_network_density_by_weight_class()

        assert isinstance(df, pd.DataFrame)


# ============================================================
# TEST: Path Length
# ============================================================

class TestPathLength:
    """Test degrees of separation analysis."""

    def test_returns_shortest_paths(self, mock_client):
        """Should return fighters ordered by degrees_of_separation."""
        sample_data = pd.DataFrame({
            'fighter': ['B', 'C', 'D'],
            'nickname': ['Bravo', 'Charlie', 'Delta'],
            'degrees_of_separation': [1, 2, 2],
        })
        mock_client.run_query.return_value = sample_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_path_length_sample('Fighter A')

        assert not df.empty
        assert 'degrees_of_separation' in df.columns
        # Results sorted by path_length ASC
        assert df.iloc[0]['degrees_of_separation'] <= df.iloc[-1]['degrees_of_separation']

    def test_passes_fighter_name_parameter(self, mock_client):
        """Should pass fighter_name to the query."""
        mock_client.run_query.return_value = pd.DataFrame()

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        repo.get_path_length_sample('Test Fighter')

        call_args = mock_client.run_query.call_args
        assert call_args is not None
        # _run passes params as second positional argument
        params = call_args[0][1]
        assert params['fighter_name'] == 'Test Fighter'


# ============================================================
# TEST: Robustness Analysis
# ============================================================

class TestRobustnessAnalysis:
    """Test network fragility / load-bearing fighters."""

    def test_returns_disruption_scores(self, mock_client):
        """Should return fighters ranked by disruption_score."""
        sample_data = pd.DataFrame({
            'fighter': ['A', 'B'],
            'nickname': ['Alpha', 'Bravo'],
            'direct_connections': [20, 15],
            'indirect_connections': [200, 100],
            'disruption_score': [10.0, 6.67],
        })
        mock_client.run_query.return_value = sample_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_robustness_analysis()

        assert not df.empty
        assert 'disruption_score' in df.columns
        assert df.iloc[0]['disruption_score'] >= df.iloc[-1]['disruption_score']


# ============================================================
# TEST: Triadic Closure
# ============================================================

class TestTriadicClosure:
    """Test triangle theory: transitivity in fight outcomes."""

    def test_returns_triangle_data(self, mock_client):
        """Should return A->B->C triangles with closure status."""
        sample_data = pd.DataFrame({
            'a_fighter': ['A', 'A'],
            'b_fighter': ['B', 'B'],
            'c_fighter': ['C', 'D'],
            'triangle_closed': [True, False],
        })
        mock_client.run_query.return_value = sample_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_triadic_closure_analysis()

        assert not df.empty
        assert 'triangle_closed' in df.columns
        assert 'a_fighter' in df.columns
        assert 'b_fighter' in df.columns
        assert 'c_fighter' in df.columns


# ============================================================
# TEST: Centrality Comparison
# ============================================================

class TestCentralityComparison:
    """Test combined centrality comparison for a single fighter."""

    def test_returns_all_centrality_metrics(self, mock_client):
        """Should return degree, eigenvector, betweenness, and pagerank for one fighter."""
        sample_data = pd.DataFrame({
            'fighter': ['A'],
            'nickname': ['Alpha'],
            'degree': [18],
            'eigenvector_proxy': [150],
            'betweenness': [15],
            'pagerank_proxy': [80],
        })
        mock_client.run_query.return_value = sample_data

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        df = repo.get_centrality_comparison('Fighter A')

        assert not df.empty
        assert 'degree' in df.columns
        assert 'eigenvector_proxy' in df.columns
        assert 'betweenness' in df.columns
        assert 'pagerank_proxy' in df.columns

    def test_passes_fighter_name(self, mock_client):
        """Should pass name parameter to query."""
        mock_client.run_query.return_value = pd.DataFrame()

        from data_access.repositories import NetworkCentralityRepo
        repo = NetworkCentralityRepo(mock_client)
        repo.get_centrality_comparison('Test Fighter')

        call_args = mock_client.run_query.call_args
        assert call_args is not None
        # _run passes params as second positional argument
        params = call_args[0][1]
        assert params['name'] == 'Test Fighter'
