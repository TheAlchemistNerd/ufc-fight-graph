"""Portable archives validate before restore and round-trip the complete graph."""

import hashlib
import json
import os
import zipfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest
from neo4j.exceptions import ConstraintError
from neo4j.time import Date, DateTime, Duration, Time

from config.settings import Neo4jConfig
from infrastructure.neo4j_client import Neo4jConnection
from run_backup import backup, decode_property, encode, restore


@pytest.fixture
def graph():
    return {
        "nodes": [
            {"id": "old-fight", "labels": ["Fight"], "properties": {"url": "fight", "round": 3}},
            {"id": "old-ref", "labels": ["Referee"], "properties": {"name": "Referee"}},
        ],
        "relationships": [
            {"start": "old-fight", "end": "old-ref", "type": "OFFICIATED_BY", "properties": {}},
        ],
    }


def write_archive(path, graph, **overrides):
    payload = json.dumps(encode(graph)).encode()
    manifest = {
        "format_version": 2,
        "nodes": len(graph["nodes"]),
        "relationships": len(graph["relationships"]),
        "sha256": hashlib.sha256(payload).hexdigest(),
        **overrides,
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("graph.json", payload)
        archive.writestr("manifest.json", json.dumps(manifest))
    return path


def test_backup_publishes_verified_archive(tmp_path, graph):
    db = Mock()
    db.run_query.return_value = [graph]
    path = backup(db, tmp_path)
    assert path.suffix == ".zip"
    with zipfile.ZipFile(path) as archive:
        payload = archive.read("graph.json")
        manifest = json.loads(archive.read("manifest.json"))
        assert json.loads(payload) == graph
        assert manifest["nodes"] == 2
        assert manifest["relationships"] == 1
        assert hashlib.sha256(payload).hexdigest() == manifest["sha256"]
    assert list(tmp_path.iterdir()) == [path]


def test_failed_publish_cleans_partial_archive(tmp_path, graph):
    db = Mock()
    db.run_query.return_value = [graph]
    with patch.object(Path, "replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            backup(db, tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "overrides",
    [{"format_version": 99}, {"sha256": "damaged"}, {"nodes": 99}, {"relationships": 99}],
)
def test_invalid_manifest_rejected_before_database_access(tmp_path, graph, overrides):
    db = Mock()
    with pytest.raises(ValueError):
        restore(db, write_archive(tmp_path / "bad.zip", graph, **overrides))
    assert not db.mock_calls


@pytest.mark.parametrize("damage", ["dangling", "duplicate", "label", "relationship", "properties"])
def test_invalid_graph_rejected_before_database_access(tmp_path, graph, damage):
    if damage == "dangling":
        graph["relationships"][0]["end"] = "absent"
    elif damage == "duplicate":
        graph["nodes"].append(deepcopy(graph["nodes"][0]))
    elif damage == "label":
        graph["nodes"][0]["labels"] = ["Unexpected"]
    elif damage == "relationship":
        graph["relationships"][0]["type"] = "Unexpected"
    else:
        graph["nodes"][0]["properties"] = []
    db = Mock()
    with pytest.raises(ValueError):
        restore(db, write_archive(tmp_path / "bad.zip", graph))
    assert not db.mock_calls


def test_restore_refuses_existing_data_without_schema_changes(tmp_path, graph):
    db = Mock()
    db.run_query.return_value = [{"count": 1}]
    with pytest.raises(ValueError, match="empty database"):
        restore(db, write_archive(tmp_path / "graph.zip", graph))
    db.setup_schema.assert_not_called()
    db.driver.session.assert_not_called()


def test_restore_rechecks_empty_database_inside_write_transaction(tmp_path, graph):
    db = MagicMock()
    db.run_query.return_value = [{"count": 0}]
    session = db.driver.session.return_value.__enter__.return_value
    tx = Mock()
    tx.run.return_value.single.return_value = {"count": 1}
    session.execute_write.side_effect = lambda write: write(tx)
    with pytest.raises(ValueError, match="empty database"):
        restore(db, write_archive(tmp_path / "graph.zip", graph))
    assert tx.run.call_count == 1


@pytest.mark.parametrize("version", [1, 2])
def test_empty_initial_snapshot_is_restorable(tmp_path, version):
    db = MagicMock()
    db.run_query.return_value = [{"count": 0}]
    tx = Mock()
    tx.run.return_value.single.return_value = {"count": 0}
    db.driver.session.return_value.__enter__.return_value.execute_write.side_effect = lambda write: (
        write(tx)
    )
    path = write_archive(
        tmp_path / "empty.zip", {"nodes": [], "relationships": []}, format_version=version
    )
    assert restore(db, path)["nodes"] == 0
    db.setup_schema.assert_called_once()
    assert tx.run.call_count == 1


@pytest.mark.parametrize(
    "value",
    [
        Date(2024, 1, 2),
        DateTime(2024, 1, 2, 3, 4, 5, 123456789),
        Time(3, 4, 5, 123456789),
        Duration(months=2, days=3, seconds=4),
    ],
)
def test_temporal_properties_preserve_type_and_precision(value):
    restored = decode_property(json.loads(json.dumps(encode([value]))))[0]
    assert type(restored) is type(value)
    assert restored == value


def canonical_graph(graph):
    nodes = {
        node["id"]: (
            tuple(sorted(node["labels"])),
            json.dumps(encode(node["properties"]), sort_keys=True),
        )
        for node in graph["nodes"]
    }
    edges = [
        (
            nodes[edge["start"]],
            nodes[edge["end"]],
            edge["type"],
            json.dumps(encode(edge["properties"]), sort_keys=True),
        )
        for edge in graph["relationships"]
    ]
    return sorted(nodes.values()), sorted(edges)


@pytest.mark.integration
def test_real_graph_roundtrip_and_constraint_failure_are_atomic(tmp_path):
    uri = os.getenv("TEST_NEO4J_URI")
    if not uri:
        pytest.skip("TEST_NEO4J_URI is required for disposable-database integration tests")
    config = Neo4jConfig(
        uri=uri,
        user=os.getenv("TEST_NEO4J_USER", "neo4j"),
        password=os.getenv("TEST_NEO4J_PASS", "password"),
        database=os.getenv("TEST_NEO4J_DATABASE", "neo4j"),
    )
    prefix = "ufc-backup-test-" + uuid4().hex + "-"
    with Neo4jConnection(config) as db:
        if db.run_query("MATCH (n) RETURN count(n) AS count")[0]["count"]:
            pytest.fail("Backup integration test requires an EMPTY disposable Neo4j database")

        def clear_fixture():
            db.run_write(
                "MATCH (n) WHERE n.name STARTS WITH $prefix OR n.url STARTS WITH $prefix "
                "DETACH DELETE n",
                {"prefix": prefix},
            )

        try:
            db.run_write(
                """
                CREATE (a:Fighter {name: $prefix + 'A', url: $prefix + 'A', _restore_id: 'original', active: true}),
                       (b:Fighter {name: $prefix + 'B', url: $prefix + 'B', ratings: [1.5, 2.5]}),
                       (f:Fight {url: $prefix + 'Fight', date: date('2024-01-02'),
                                 elapsed: duration('P2M3DT4.000000001S'),
                                 checked: datetime('2024-01-02T03:04:05.123456789Z')}),
                       (e:Event {name: $prefix + 'Event'}),
                       (w:WeightClass {name: $prefix + 'Class'}),
                       (r:Referee {name: $prefix + 'Referee'}),
                       (j:Judge {name: $prefix + 'Judge'}),
                       (l:Location {name: $prefix + 'Location'}),
                       (a)-[:FOUGHT {result: 'win'}]->(f),
                       (b)-[:FOUGHT {result: 'loss'}]->(f),
                       (f)-[:PART_OF]->(e), (e)-[:HELD_AT]->(l),
                       (f)-[:IN_WEIGHT_CLASS]->(w), (f)-[:OFFICIATED_BY]->(r),
                       (f)-[:SCORED_BY {score: '30 - 27'}]->(j)
            """,
                {"prefix": prefix},
            )
            archive = backup(db, tmp_path)
            with zipfile.ZipFile(archive) as source:
                expected = json.loads(source.read("graph.json"))
            clear_fixture()
            manifest = restore(db, archive)
            assert manifest["nodes"] == 8
            assert manifest["relationships"] == 7
            with zipfile.ZipFile(backup(db, tmp_path)) as restored:
                assert canonical_graph(json.loads(restored.read("graph.json"))) == canonical_graph(
                    expected
                )
            assert db.run_query("MATCH (f:Fight) RETURN f.date AS date")[0]["date"] == Date(
                2024, 1, 2
            )
            clear_fixture()

            duplicate = {
                "nodes": [
                    {
                        "id": str(i),
                        "labels": ["Fighter"],
                        "properties": {
                            "url": prefix + "duplicate",
                            "name": prefix + "duplicate",
                        },
                    }
                    for i in range(2)
                ],
                "relationships": [],
            }
            with pytest.raises(ConstraintError):
                restore(db, write_archive(tmp_path / "duplicate.zip", duplicate))
            assert db.run_query("MATCH (n) RETURN count(n) AS count")[0]["count"] == 0
        finally:
            clear_fixture()
