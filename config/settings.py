"""Environment configuration shared by the crawler and dashboard."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI") or "bolt://localhost:7687")
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER") or "neo4j")
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASS") or "password")
    database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE") or "neo4j")


def load_config(env_file=None):
    load_dotenv(dotenv_path=env_file or ".env", override=False)
    return Neo4jConfig()
