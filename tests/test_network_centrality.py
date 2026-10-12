"""Repository boundary tests; graph calculations run in test_neo4j_integration."""

from unittest.mock import Mock

import pytest

from data_access.repositories import NetworkCentralityRepo, NetworkRepo


@pytest.mark.parametrize(
    "method",
    [
        "get_degree_centrality",
        "get_eigenvector_centrality",
        "get_betweenness_centrality",
        "get_closeness_centrality",
        "get_pagerank_rankings",
        "get_robustness_analysis",
    ],
)
def test_network_rankings_bind_the_requested_limit(method):
    db = Mock()
    db.run_query.return_value = []
    frame = getattr(NetworkCentralityRepo(db), method)(limit=7)
    assert frame.empty
    assert db.run_query.call_args.args[1] == {"limit": 7}


def test_fighter_names_are_bound_parameters():
    db = Mock()
    db.run_query.return_value = []
    name = "Fighter ' MATCH (n) DETACH DELETE n //"
    NetworkCentralityRepo(db).get_path_length_sample(name, limit=4)
    query, params = db.run_query.call_args.args
    assert name not in query
    assert params == {"fighter_name": name, "limit": 4}
    NetworkRepo(db).get_common_opponents(name, "Second fighter")
    assert db.run_query.call_args.args[1] == {"f1": name, "f2": "Second fighter"}
