"""
UFC Fight Graph - Infrastructure Layer.

External I/O: Neo4j, HTTP, Dask compute.
Depends on domain models, but domain depends on nothing.
"""

from __future__ import annotations
import logging
from typing import Optional
from neo4j import GraphDatabase
from config.settings import Neo4jConfig

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """Manages Neo4j driver lifecycle. Single responsibility: connection only."""

    def __init__(self, config: Neo4jConfig):
        self._config = config
        self._driver: Optional[GraphDatabase.driver] = None

    @property
    def driver(self) -> GraphDatabase.driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self._config.uri,
                auth=(self._config.user, self._config.password),
            )
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def test_connection(self) -> tuple[bool, int]:
        try:
            with self.driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) AS c").single()
                return True, result["c"] if result else 0
        except Exception as e:
            logger.error(f"Neo4j connection test failed: {e}")
            return False, 0

    def run_query(self, query: str, params: dict = None):
        """Execute a read query and return a list of record dicts."""
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [dict(record) for record in result]

    def run_write(self, query: str, params: dict = None):
        """Execute a write query."""
        with self.driver.session() as session:
            session.run(query, params or {})

    def setup_schema(self) -> None:
        constraints = [
            "CREATE CONSTRAINT fighter_name IF NOT EXISTS FOR (f:Fighter) REQUIRE f.name IS UNIQUE",
            "CREATE CONSTRAINT event_name IF NOT EXISTS FOR (e:Event) REQUIRE e.name IS UNIQUE",
            "CREATE CONSTRAINT fight_url IF NOT EXISTS FOR (f:Fight) REQUIRE f.url IS UNIQUE",
            "CREATE CONSTRAINT weightclass_name IF NOT EXISTS FOR (w:WeightClass) REQUIRE w.name IS UNIQUE",
            "CREATE CONSTRAINT referee_name IF NOT EXISTS FOR (r:Referee) REQUIRE r.name IS UNIQUE",
            "CREATE CONSTRAINT location_name IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE",
            "CREATE CONSTRAINT judge_name IF NOT EXISTS FOR (j:Judge) REQUIRE j.name IS UNIQUE",
        ]
        with self.driver.session() as session:
            for constraint in constraints:
                session.run(constraint)
        logger.info("Schema constraints created/verified.")
