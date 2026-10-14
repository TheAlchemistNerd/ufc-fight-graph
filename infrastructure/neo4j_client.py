"""Neo4j connection lifecycle and schema shared by all entry points."""

import logging

from neo4j import GraphDatabase

from config.settings import Neo4jConfig

logger = logging.getLogger(__name__)


class Neo4jConnection:
    def __init__(self, config: Neo4jConfig):
        self.config = config
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
                connection_timeout=10,
                connection_acquisition_timeout=15,
            )
        return self._driver

    def close(self):
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def run_query(self, query, params=None):
        with self.driver.session(database=self.config.database) as session:
            return session.execute_read(lambda tx: tx.run(query, params or {}).data())

    def run_write(self, query, params=None):
        with self.driver.session(database=self.config.database) as session:
            return session.execute_write(lambda tx: tx.run(query, params or {}).data())

    def test_connection(self):
        try:
            return True, self.run_query("MATCH (n) RETURN count(n) AS c")[0]["c"]
        except Exception as exc:
            # Keep the Cloud logs useful without printing exception text that
            # could contain connection details or credentials.
            code = getattr(exc, "code", None) or "unavailable"
            logger.warning(
                "Neo4j connection check failed (%s, code=%s)",
                type(exc).__name__,
                code,
            )
            return False, 0

    def setup_schema(self):
        legacy = self.run_query(
            "SHOW CONSTRAINTS YIELD name WHERE name = 'fighter_name' RETURN name"
        )
        if legacy:
            raise ValueError(
                "Legacy name-keyed fighter schema: export a backup and use a fresh database for the URL-keyed rebuild"
            )
        for label, key in (
            ("Fighter", "url"),
            ("Event", "name"),
            ("Fight", "url"),
            ("WeightClass", "name"),
            ("Referee", "name"),
            ("Location", "name"),
            ("Judge", "name"),
        ):
            self.run_write(
                f"CREATE CONSTRAINT {label.lower()}_{key} IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"
            )
