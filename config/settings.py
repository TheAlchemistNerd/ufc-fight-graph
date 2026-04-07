"""
UFC Fight Graph - Domain Configuration.

All application settings, constants, and configuration live here.
No business logic, no I/O.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASS", "password"))
    database: str = "neo4j"
    max_connection_lifetime: int = 3600
    connection_timeout: int = 30


@dataclass(frozen=True)
class ScraperConfig:
    base_url: str = "http://ufcstats.com"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    delay_range: tuple = (0.5, 2.0)


@dataclass(frozen=True)
class DaskConfig:
    n_workers: int = int(os.getenv("DASK_WORKERS", "4"))
    threads_per_worker: int = int(os.getenv("DASK_THREADS", "2"))
    memory_limit: str = os.getenv("DASK_MEMORY", "4GB")
    dashboard_address: str = os.getenv("DASK_DASHBOARD", "localhost:8787")


@dataclass(frozen=True)
class CrawlConfig:
    batch_size: int = 50
    checkpoint_file: str = "logs/crawl_checkpoint.json"
    progress_file: str = "logs/crawl_progress.json"
    max_workers: int = 10
    delay: float = 1.0


@dataclass(frozen=True)
class AppConfig:
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    dask: DaskConfig = field(default_factory=DaskConfig)
    crawl: CrawlConfig = field(default_factory=CrawlConfig)
