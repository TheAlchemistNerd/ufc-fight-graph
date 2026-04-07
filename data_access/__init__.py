"""
Data Access Layer - Neo4j connection and query repositories.

All database queries live here. The UI layer imports repositories
and calls methods - zero Cypher in UI code.
"""

from data_access.repositories import (
    Neo4jClient,
    Repository,
    OverviewRepo,
    FighterRepo,
    RefereeRepo,
    GeographyRepo,
    WeightClassRepo,
    NetworkRepo,
    EvolutionRepo,
    StrikingRepo,
    ChampionshipRepo,
    FightPaceRepo,
    CareerRepo,
    StyleMatchupRepo,
    FinishRepo,
    BettingRepo,
    NetworkCentralityRepo,
)

__all__ = [
    "Neo4jClient",
    "Repository",
    "OverviewRepo",
    "FighterRepo",
    "RefereeRepo",
    "GeographyRepo",
    "WeightClassRepo",
    "NetworkRepo",
    "EvolutionRepo",
    "StrikingRepo",
    "ChampionshipRepo",
    "FightPaceRepo",
    "CareerRepo",
    "StyleMatchupRepo",
    "FinishRepo",
    "BettingRepo",
    "NetworkCentralityRepo",
]
