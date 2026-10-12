"""Export a portable graph archive or restore one into an empty database."""

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from neo4j.time import Date, DateTime, Duration, Time

from config.settings import load_config
from infrastructure.neo4j_client import Neo4jConnection

LABELS = {"Fighter", "Fight", "Event", "WeightClass", "Referee", "Judge", "Location"}
RELATIONSHIPS = {"FOUGHT", "PART_OF", "HELD_AT", "IN_WEIGHT_CLASS", "OFFICIATED_BY", "SCORED_BY"}
TEMPORAL_TYPES = {kind.__name__: kind for kind in (Date, DateTime, Duration, Time)}


def encode(value):
    if type(value).__name__ in TEMPORAL_TYPES:
        return {"neo4j_type": type(value).__name__, "value": value.iso_format()}
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode(item) for item in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError(f"Unsupported backup property: {type(value).__name__}")


def decode_property(value):
    if isinstance(value, list):
        return [decode_property(item) for item in value]
    if isinstance(value, dict):
        if set(value) != {"neo4j_type", "value"} or value["neo4j_type"] not in TEMPORAL_TYPES:
            raise ValueError("Invalid typed property in backup")
        return TEMPORAL_TYPES[value["neo4j_type"]].from_iso_format(value["value"])
    return value


def validate(graph, manifest=None):
    """Reject incomplete or non-project graphs before writing files or database rows."""
    try:
        nodes, relationships = graph["nodes"], graph["relationships"]
        if not isinstance(nodes, list) or not isinstance(relationships, list):
            raise ValueError("Invalid graph in backup")
        ids = {n["id"] for n in nodes}
        if len(ids) != len(nodes) or any(not isinstance(key, str) or not key for key in ids):
            raise ValueError("Invalid backup node identities")
        if any(len(n["labels"]) != 1 or n["labels"][0] not in LABELS for n in nodes):
            raise ValueError("Unexpected node labels in backup")
        if any(
            r["type"] not in RELATIONSHIPS or r["start"] not in ids or r["end"] not in ids
            for r in relationships
        ):
            raise ValueError("Invalid relationship in backup")
        if any(not isinstance(item["properties"], dict) for item in nodes + relationships):
            raise ValueError("Invalid properties in backup")
        if manifest and (
            len(nodes) != manifest["nodes"] or len(relationships) != manifest["relationships"]
        ):
            raise ValueError("Invalid backup counts")
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid graph in backup") from exc


def backup(db, directory="backups"):
    graph = db.run_query("""
        MATCH (n)
        WITH collect({id: elementId(n), labels: labels(n), properties: properties(n)}) AS nodes
        CALL {
            MATCH (a)-[r]->(b)
            RETURN collect({start: elementId(a), end: elementId(b), type: type(r), properties: properties(r)}) AS relationships
        }
        RETURN nodes, relationships
    """)[0]
    validate(graph)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"ufc-graph-{timestamp}.zip"
    payload = json.dumps(encode(graph), ensure_ascii=False).encode("utf-8")
    manifest = {
        "format_version": 2,
        "created_utc": timestamp,
        "nodes": len(graph["nodes"]),
        "relationships": len(graph["relationships"]),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    temporary = destination.with_suffix(".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("graph.json", payload)
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def restore(db, path):
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        payload = archive.read("graph.json")
    if manifest.get("format_version") not in (1, 2) or hashlib.sha256(
        payload
    ).hexdigest() != manifest.get("sha256"):
        raise ValueError("Unsupported or damaged backup")
    graph = json.loads(payload)
    validate(graph, manifest)
    nodes, relationships = graph["nodes"], graph["relationships"]
    if manifest["format_version"] == 2:
        for item in nodes + relationships:
            item["properties"] = {
                key: decode_property(value) for key, value in item["properties"].items()
            }
    if db.run_query("MATCH (n) RETURN count(n) AS count")[0]["count"]:
        raise ValueError("Restore requires an empty database")
    # Install constraints first so duplicates fail within the atomic data transaction.
    db.setup_schema()

    def write(tx):
        if tx.run("MATCH (n) RETURN count(n) AS count").single()["count"]:
            raise ValueError("Restore requires an empty database")
        restored_ids = {}
        for label in sorted(LABELS):
            batch = [n for n in nodes if label in n["labels"]]
            if batch:
                rows = tx.run(
                    f"UNWIND $nodes AS n CREATE (v:{label}) SET v = n.properties "
                    "RETURN n.id AS original_id, elementId(v) AS restored_id",
                    nodes=batch,
                )
                restored_ids.update((row["original_id"], row["restored_id"]) for row in rows)
        for kind in sorted(RELATIONSHIPS):
            edges = [
                {**r, "start": restored_ids[r["start"]], "end": restored_ids[r["end"]]}
                for r in relationships
                if r["type"] == kind
            ]
            if not edges:
                continue
            # Element-ID seeks avoid scanning every node for every relationship and
            # preserve all original properties without temporary labels or fields.
            tx.run(
                f"""UNWIND $edges AS r
                MATCH (a) WHERE elementId(a) = r.start
                MATCH (b) WHERE elementId(b) = r.end
                CREATE (a)-[edge:{kind}]->(b) SET edge = r.properties""",
                edges=edges,
            ).consume()

    with db.driver.session(database=db.config.database) as session:
        session.execute_write(write)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file")
    parser.add_argument("--output-dir", default="backups")
    parser.add_argument("--restore", type=Path)
    args = parser.parse_args(argv)
    with Neo4jConnection(load_config(args.env_file)) as db:
        if args.restore:
            print(json.dumps(restore(db, args.restore), indent=2))
        else:
            print(backup(db, args.output_dir).resolve())


if __name__ == "__main__":
    main()
