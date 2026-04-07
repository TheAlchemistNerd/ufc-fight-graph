"""
Data Access Layer — Neo4j Connection + Query Repositories.

All database logic lives here. The UI layer imports repositories
and calls methods — zero Cypher queries in UI code.
"""

from neo4j import GraphDatabase
import pandas as pd
import os
from typing import Optional


# ===================== CONNECTION =====================

class Neo4jClient:
    """Manages the Neo4j driver connection."""

    _instance: Optional["Neo4jClient"] = None

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASS", "password")
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    def run_query(self, query: str, params: dict = None) -> pd.DataFrame:
        """Execute a Cypher query and return results as a DataFrame."""
        with self.driver.session() as session:
            result = session.run(query, params or {})
            records = [dict(r) for r in result]
            return pd.DataFrame(records)

    def test_connection(self) -> tuple[bool, int]:
        """Returns (success, node_count)."""
        try:
            df = self.run_query("MATCH (n) RETURN count(n) AS c")
            return True, int(df.iloc[0, 0])
        except Exception as e:
            return False, str(e)


# ===================== BASE REPOSITORY =====================

class Repository:
    """Base repository providing query execution."""

    def __init__(self, client: Neo4jClient):
        self.client = client

    def _run(self, query: str, params: dict = None) -> pd.DataFrame:
        return self.client.run_query(query, params)


# ===================== OVERVIEW REPOSITORY =====================

class OverviewRepo(Repository):
    """High-level metrics and dashboard overview data."""

    def get_node_counts(self) -> dict:
        """Return counts of each node type."""
        df = self._run("""
            MATCH (n)
            WITH labels(n)[0] AS label, count(n) AS cnt
            RETURN label, cnt
        """)
        if df.empty:
            return {}
        return dict(zip(df["label"], df["cnt"]))

    def get_top_active_fighters(self, limit: int = 10) -> pd.DataFrame:
        df = self._run("""
            MATCH (f:Fighter)-[r:FOUGHT]->(fight)
            WITH f.name AS name, count(r) AS fights
            ORDER BY fights DESC
            LIMIT $limit
        """, {"limit": limit})
        return df

    def get_top_ko_artists(self, limit: int = 10) -> pd.DataFrame:
        df = self._run("""
            MATCH (f:Fighter)-[r:FOUGHT {result: "win"}]->(fight)
            WHERE toUpper(fight.method) CONTAINS "KO" OR toUpper(fight.method) CONTAINS "TKO"
            WITH f.name AS name, count(fight) AS ko_wins
            ORDER BY ko_wins DESC
            LIMIT $limit
        """, {"limit": limit})
        return df

    def get_events_over_time(self) -> pd.DataFrame:
        df = self._run("""
            MATCH (e:Event)
            WHERE e.date IS NOT NULL
            RETURN e.date AS date, e.name AS name
            ORDER BY date
        """)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["year"] = df["date"].dt.year
            return df.groupby("year").size().reset_index(name="events")
        return df

    def get_recent_events(self, limit: int = 10) -> pd.DataFrame:
        return self._run("""
            MATCH (e:Event)-[:HELD_AT]->(loc:Location)
            RETURN e.name AS event, e.date AS date, loc.name AS location
            ORDER BY e.date DESC
            LIMIT $limit
        """, {"limit": limit})


# ===================== FIGHTER REPOSITORY =====================

class FighterRepo(Repository):
    """Fighter profiles, search, fight history, similarity."""

    def get_all_fighter_names(self) -> list[str]:
        df = self._run("MATCH (f:Fighter) RETURN f.name AS name ORDER BY f.name")
        return df["name"].tolist() if not df.empty else []

    def get_fighter_profile(self, name: str) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter {name: $name})
            RETURN f.name AS name, f.nickname AS nickname,
                   f.record AS record, f.stance AS stance,
                   f.height AS height, f.reach AS reach, f.weight AS weight,
                   f.wins AS wins, f.losses AS losses, f.draws AS draws
        """, {"name": name})

    def get_fighter_history(self, name: str) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter {name: $name})-[r:FOUGHT]->(fight)-[:PART_OF]->(e:Event)
            OPTIONAL MATCH (fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
            RETURN r.result AS result, fight.method AS method,
                   fight.round AS round, fight.time AS time,
                   fight.date AS date, wc.name AS weight_class,
                   e.name AS event
            ORDER BY fight.date DESC
        """, {"name": name})

    def get_similar_fighters(self, name: str, limit: int = 10) -> pd.DataFrame:
        return self._run("""
            MATCH (target:Fighter {name: $name})
            WHERE target.slpm IS NOT NULL
            MATCH (f:Fighter)
            WHERE f <> target AND f.slpm IS NOT NULL
            WITH f, target,
                 abs(toFloat(f.slpm) - toFloat(target.slpm)) +
                 abs(toFloat(coalesce(f.str_acc,0)) - toFloat(coalesce(target.str_acc,0))) +
                 abs(toFloat(coalesce(f.sapm,0)) - toFloat(coalesce(target.sapm,0))) AS distance
            ORDER BY distance ASC
            LIMIT $limit
            RETURN f.name AS fighter, f.nickname AS nickname,
                   f.slpm, f.str_acc, f.sapm,
                   round(distance, 3) AS distance
        """, {"name": name, "limit": limit})


# ===================== REFEREE REPOSITORY =====================

class RefereeRepo(Repository):
    """Referee analysis: finish rates, volume, patterns."""

    def get_referee_finish_rates(self, min_fights: int = 3) -> pd.DataFrame:
        return self._run("""
            MATCH (ref:Referee)<-[:OFFICIATED_BY]-(fight)
            WITH ref.name AS referee,
                 count(fight) AS total_fights,
                 count(CASE WHEN toUpper(fight.method) CONTAINS "KO" OR toUpper(fight.method) CONTAINS "TKO" THEN 1 END) AS ko_finishes,
                 count(CASE WHEN toUpper(fight.method) CONTAINS "SUB" THEN 1 END) AS sub_finishes,
                 count(CASE WHEN toUpper(fight.method) CONTAINS "DEC" THEN 1 END) AS decisions
            WHERE total_fights >= $min_fights
            RETURN referee,
                   total_fights,
                   round(toFloat(ko_finishes) / total_fights * 100, 1) AS ko_pct,
                   round(toFloat(sub_finishes) / total_fights * 100, 1) AS sub_pct,
                   round(toFloat(decisions) / total_fights * 100, 1) AS decision_pct
            ORDER BY ko_pct DESC
        """, {"min_fights": min_fights})

    def get_top_referees(self, limit: int = 10) -> pd.DataFrame:
        return self._run("""
            MATCH (ref:Referee)<-[:OFFICIATED_BY]-(fight)
            RETURN ref.name AS referee, count(fight) AS fights
            ORDER BY fights DESC
            LIMIT $limit
        """, {"limit": limit})


# ===================== GEOGRAPHY REPOSITORY =====================

class GeographyRepo(Repository):
    """Location-based event analysis."""

    def get_events_by_location(self, limit: int = 15) -> pd.DataFrame:
        return self._run("""
            MATCH (e:Event)-[:HELD_AT]->(loc:Location)
            RETURN loc.name AS location,
                   count(DISTINCT e) AS events,
                   count(DISTINCT (e)<-[:PART_OF]-(:Fight)) AS total_fights
            ORDER BY events DESC
            LIMIT $limit
        """, {"limit": limit})

    def get_fight_outcomes_by_location(self, limit: int = 20) -> pd.DataFrame:
        return self._run("""
            MATCH (e:Event)-[:HELD_AT]->(loc:Location)
            MATCH (fight)-[:PART_OF]->(e)
            MATCH (f:Fighter)-[r:FOUGHT]->(fight)
            RETURN loc.name AS location,
                   r.result AS result,
                   count(fight) AS count
            ORDER BY count DESC
            LIMIT $limit
        """, {"limit": limit})


# ===================== WEIGHT CLASS REPOSITORY =====================

class WeightClassRepo(Repository):
    """Weight class dominance, distribution, breakdowns."""

    def get_all_weight_classes(self) -> list[str]:
        df = self._run("MATCH (w:WeightClass) RETURN w.name AS name ORDER BY w.name")
        return df["name"].tolist() if not df.empty else []

    def get_win_rates(self, weight_class: str = None, min_fights: int = 3) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter)-[r:FOUGHT]->(fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
            WHERE wc.name = $wc OR $wc IS NULL
            WITH f, wc,
                 count(r) AS total_fights,
                 count(CASE WHEN r.result = "win" THEN 1 END) AS wins
            WITH f, wc, total_fights, wins,
                 CASE WHEN total_fights > 0 THEN toFloat(wins) / toFloat(total_fights) * 100 ELSE 0 END AS win_pct
            WHERE total_fights >= $min_fights
            RETURN f.name AS fighter, f.nickname AS nickname,
                   wc.name AS weight_class, wins, total_fights,
                   round(win_pct, 1) AS win_percentage
            ORDER BY win_pct DESC, wins DESC
            LIMIT 50
        """, {"wc": weight_class, "min_fights": min_fights})


# ===================== NETWORK REPOSITORY =====================

class NetworkRepo(Repository):
    """Graph relationships: transitive wins, common opponents, network data."""

    def get_transitive_wins(self, fighter_name: str, limit: int = 30) -> pd.DataFrame:
        return self._run("""
            MATCH (target:Fighter {name: $name})<-[:FOUGHT]-(fight1)<-[:FOUGHT {result: "win"}]-(beaten_by:Fighter)
            WHERE beaten_by <> target
            WITH DISTINCT beaten_by
            MATCH (beaten_by)-[:FOUGHT {result: "win"}]->(fight2)<-[:FOUGHT]-(i_beat_them:Fighter)
            WHERE i_beat_them <> target
            RETURN DISTINCT i_beat_them.name AS fighter,
                   beaten_by.name AS via
            LIMIT $limit
        """, {"name": fighter_name, "limit": limit})

    def get_common_opponents(self, f1_name: str, f2_name: str) -> pd.DataFrame:
        return self._run("""
            MATCH (a:Fighter {name: $f1})-[:FOUGHT]->(fight1)<-[:FOUGHT]-(o:Fighter),
                  (b:Fighter {name: $f2})-[:FOUGHT]->(fight2)<-[:FOUGHT]-(o)
            WHERE a <> b AND a <> o AND b <> o
            RETURN DISTINCT o.name AS opponent
        """, {"f1": f1_name, "f2": f2_name})

    def get_network_sample(self, limit: int = 50) -> pd.DataFrame:
        return self._run("""
            MATCH (f1:Fighter)-[:FOUGHT]->(fight)<-[:FOUGHT]-(f2:Fighter)
            MATCH (fight)-[:PART_OF]->(e:Event)
            RETURN f1.name AS f1, f2.name AS f2, e.name AS event
            LIMIT $limit
        """, {"limit": limit})


# ===================== EVOLUTION REPOSITORY =====================

class EvolutionRepo(Repository):
    """Physical and statistical trends across eras."""

    def get_physical_by_era(self) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter)
            WHERE f.height_inches IS NOT NULL AND f.reach_inches IS NOT NULL
            WITH f,
                 CASE
                   WHEN toInteger(f.dob) < 1980 THEN "Pre-1980"
                   WHEN toInteger(f.dob) < 1990 THEN "1980s"
                   WHEN toInteger(f.dob) < 2000 THEN "1990s"
                   ELSE "2000s"
                 END AS era
            RETURN era,
                   count(f) AS fighters,
                   round(avg(f.height_inches), 1) AS avg_height,
                   round(avg(f.reach_inches), 1) AS avg_reach
            ORDER BY era
        """)

    def get_striking_by_era(self) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter)
            WHERE f.slpm IS NOT NULL AND f.dob IS NOT NULL
            WITH f,
                 CASE
                   WHEN toInteger(f.dob) < 1980 THEN "Pre-1980"
                   WHEN toInteger(f.dob) < 1990 THEN "1980s"
                   WHEN toInteger(f.dob) < 2000 THEN "1990s"
                   ELSE "2000s"
                 END AS era
            RETURN era,
                   count(f) AS fighters,
                   round(avg(toFloat(f.slpm)), 2) AS avg_slpm
            ORDER BY era
        """)


# ===================== STRIKING EFFICIENCY REPOSITORY =====================

class StrikingRepo(Repository):
    """Striking and grappling efficiency metrics."""

    def get_striking_efficiency(self, min_slpm: float = 2.0) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter)
            WHERE f.slpm IS NOT NULL AND f.sapm IS NOT NULL AND toFloat(f.sapm) > 0
            WITH f.name AS fighter, f.nickname AS nickname,
                   toFloat(f.slpm) AS slpm, toFloat(f.sapm) AS sapm,
                   toFloat(f.slpm) / toFloat(f.sapm) AS strike_ratio
            WHERE toFloat(f.slpm) >= $min_slpm
            RETURN fighter, nickname,
                   round(slpm, 2) AS slpm, round(sapm, 2) AS sapm,
                   round(strike_ratio, 2) AS strike_ratio
            ORDER BY strike_ratio DESC
            LIMIT 20
        """, {"min_slpm": min_slpm})

    def get_reach_advantage(self) -> pd.DataFrame:
        return self._run("""
            MATCH (f1:Fighter)-[r1:FOUGHT]->(fight)<-[r2:FOUGHT]-(f2:Fighter)
            WHERE f1.reach_inches IS NOT NULL AND f2.reach_inches IS NOT NULL
              AND r1.result = "win" AND f1 <> f2
            WITH toFloat(f1.reach_inches) - toFloat(f2.reach_inches) AS reach_diff,
                   count(fight) AS fights,
                   count(CASE WHEN reach_diff > 0 THEN 1 END) AS longer_reach_wins
            RETURN round(reach_diff, 1) AS reach_advantage_inches,
                   fights,
                   round(toFloat(longer_reach_wins) / fights * 100, 1) AS longer_reach_win_pct
            ORDER BY reach_advantage_inches
        """)


# ===================== CHAMPIONSHIP REPOSITORY =====================

class ChampionshipRepo(Repository):
    """Title fight analysis and championship patterns."""

    def get_title_vs_regular_finish_rates(self) -> pd.DataFrame:
        return self._run("""
            MATCH (fight)-[:PART_OF]->(e:Event)
            WHERE toUpper(e.name) CONTAINS "TITLE" OR toUpper(e.name) CONTAINS "CHAMPION"
            WITH count(fight) AS title_fights,
                 count(CASE WHEN toUpper(fight.method) CONTAINS "KO" OR toUpper(fight.method) CONTAINS "TKO" OR toUpper(fight.method) CONTAINS "SUB" THEN 1 END) AS title_finishes
            MATCH (fight2)
            WITH title_fights, title_finishes,
                 count(fight2) AS total_fights,
                 count(CASE WHEN toUpper(fight2.method) CONTAINS "KO" OR toUpper(fight2.method) CONTAINS "TKO" OR toUpper(fight2.method) CONTAINS "SUB" THEN 1 END) AS total_finishes
            RETURN round(toFloat(title_finishes) / CASE WHEN title_fights > 0 THEN title_fights ELSE 1 END * 100, 1) AS title_finish_pct,
                   round(toFloat(total_finishes) / total_fights * 100, 1) AS overall_finish_pct,
                   title_fights, total_fights
        """)


# ===================== FIGHT PACE REPOSITORY =====================

class FightPaceRepo(Repository):
    """Fight duration, card structure, pace analysis."""

    def get_duration_by_weight_class(self) -> pd.DataFrame:
        return self._run("""
            MATCH (fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
            WHERE fight.round IS NOT NULL AND fight.time IS NOT NULL
            WITH wc.name AS weight_class, fight,
                 toInteger(fight.round) AS round_num,
                 split(fight.time, ":") AS time_parts
            WITH weight_class,
                 (round_num - 1) * 300 +
                 toInteger(time_parts[0]) * 60 + toInteger(time_parts[1]) AS fight_duration_seconds,
                 fight
            WHERE fight_duration_seconds > 0
            RETURN weight_class,
                   round(avg(fight_duration_seconds), 0) AS avg_duration_sec,
                   round(avg(fight_duration_seconds) / 60, 1) AS avg_duration_min,
                   count(fight) AS fights
            ORDER BY avg_duration_sec ASC
        """)

    def get_finish_rate_by_year(self) -> pd.DataFrame:
        return self._run("""
            MATCH (fight)-[:PART_OF]->(e:Event)
            WHERE e.date IS NOT NULL
            WITH e.date AS event_date, fight,
                 toInteger(split(e.date, ",")[1]) AS year
            WHERE year IS NOT NULL AND year > 1900
            WITH year,
                   count(fight) AS total_fights,
                   count(CASE WHEN toUpper(fight.method) CONTAINS "KO" OR toUpper(fight.method) CONTAINS "TKO" OR toUpper(fight.method) CONTAINS "SUB" THEN 1 END) AS finishes
            RETURN year,
                   total_fights, finishes,
                   round(toFloat(finishes) / total_fights * 100, 1) AS finish_pct
            ORDER BY year ASC
        """)


# ===================== CAREER REPOSITORY =====================

class CareerRepo(Repository):
    """Career trajectory, longevity, layoff analysis."""

    def get_career_lengths(self) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter)
            WHERE f.wins IS NOT NULL AND f.losses IS NOT NULL
            WITH f.name AS fighter, f.nickname AS nickname,
                   toInteger(f.wins) + toInteger(f.losses) AS total_fights,
                   toInteger(f.wins) AS wins, toInteger(f.losses) AS losses
            WHERE total_fights >= 5
            RETURN fighter, nickname, total_fights, wins, losses,
                   round(toFloat(wins) / total_fights * 100, 1) AS win_pct
            ORDER BY total_fights DESC
            LIMIT 30
        """)

    def get_underdog_analysis(self) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter)-[r:FOUGHT {result: "win"}]->(fight)
            WHERE toInteger(f.wins) < toInteger(f.losses)
            WITH f.name AS fighter, f.wins AS career_wins, f.losses AS career_losses,
                   count(fight) AS upset_wins,
                   collect(distinct fight.method) AS upset_methods
            RETURN fighter, career_wins, career_losses, upset_wins,
                   size(upset_methods) AS different_methods
            ORDER BY upset_wins DESC
            LIMIT 15
        """)


# ===================== STYLE MATCHUP REPOSITORY =====================

class StyleMatchupRepo(Repository):
    """Stance matchups, style-based analysis."""

    def get_stance_matchups(self) -> pd.DataFrame:
        return self._run("""
            MATCH (f1:Fighter)-[r1:FOUGHT {result: "win"}]->(fight)<-[r2:FOUGHT]-(f2:Fighter)
            WHERE f1.stance IS NOT NULL AND f2.stance IS NOT NULL
              AND f1.stance <> f2.stance
            WITH f1.stance AS winner_stance, f2.stance AS loser_stance,
                   count(fight) AS wins
            RETURN winner_stance, loser_stance, wins
            ORDER BY wins DESC
        """)

    def get_gym_output(self, min_fights: int = 10) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter)-[r:FOUGHT]->(fight)
            WHERE f.gym IS NOT NULL
            WITH f.gym AS gym,
                   count(r) AS total_fights,
                   count(CASE WHEN r.result = "win" THEN 1 END) AS gym_wins,
                   count(DISTINCT f) AS active_fighters
            WHERE total_fights >= $min_fights
            RETURN gym,
                   round(toFloat(gym_wins) / total_fights * 100, 1) AS win_pct,
                   gym_wins, total_fights, active_fighters
            ORDER BY gym_wins DESC
            LIMIT 20
        """, {"min_fights": min_fights})


# ===================== KO / SUB SPECIALISTS REPOSITORY =====================

class FinishRepo(Repository):
    """Knockout and submission specialist analysis."""

    def get_ko_kings(self, limit: int = 20) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter)-[r:FOUGHT {result: "win"}]->(fight)
            WHERE toUpper(fight.method) CONTAINS "KO" OR toUpper(fight.method) CONTAINS "TKO"
            WITH f.name AS name, f.nickname AS nickname,
                 count(fight) AS ko_wins
            ORDER BY ko_wins DESC
            LIMIT $limit
        """, {"limit": limit})

    def get_sub_specialists(self, limit: int = 20) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter)-[r:FOUGHT {result: "win"}]->(fight)
            WHERE toUpper(fight.method) CONTAINS "SUB"
            WITH f.name AS name, f.nickname AS nickname,
                 count(fight) AS sub_wins
            ORDER BY sub_wins DESC
            LIMIT $limit
        """, {"limit": limit})


# ===================== BETTING INSIGHTS REPOSITORY =====================

class BettingRepo(Repository):
    """Betting-relevant patterns and upset detection."""

    def get_post_loss_rebound(self, limit: int = 20) -> pd.DataFrame:
        return self._run("""
            MATCH (f:Fighter)-[r1:FOUGHT {result: "loss"}]->(fight1),
                  (f)-[r2:FOUGHT]->(fight2)
            WHERE fight1 <> fight2
            WITH f.name AS fighter, count(r2) AS fights_after_loss,
                   count(CASE WHEN r2.result = "win" THEN 1 END) AS wins_after_loss
            WHERE fights_after_loss > 0
            RETURN fighter, fights_after_loss, wins_after_loss,
                   round(toFloat(wins_after_loss) / fights_after_loss * 100, 1) AS rebound_pct
            ORDER BY fights_after_loss DESC
            LIMIT $limit
        """, {"limit": limit})


# ===================== NETWORK CENTRALITY REPOSITORY =====================

class NetworkCentralityRepo(Repository):
    """
    Advanced network centrality metrics for UFC fighter analysis.

    Based on research from:
    - "Network Dynamics in Mixed Martial Arts" (arXiv, 2025)
    - PageRank for MMA Rankings
    - Complex Systems analysis of UFC matchmaking

    Metrics implemented:
    - Degree Centrality: Unique opponents faced
    - Eigenvector Centrality: Influence based on opponent quality
    - Betweenness Centrality: Bridge fighters across clusters
    - Closeness Centrality: Steps to reach any other fighter
    - PageRank: Loss-weighted relevance flow
    - Network Density: Division interconnectedness
    - Average Path Length: Degrees of separation
    - Network Robustness: Load-bearing fighters
    - Triadic Closure: Triangle theory analysis
    """

    def get_degree_centrality(self, limit: int = 30) -> pd.DataFrame:
        """
        Degree centrality: total unique opponents faced.
        Identifies gatekeepers and long-tenured veterans.
        Research: Highly active fighters act as major network hubs.
        """
        return self._run("""
            MATCH (f:Fighter)-[r:FOUGHT]->(fight)<-[r2:FOUGHT]-(opponent)
            WHERE f <> opponent
            WITH f.name AS fighter, f.nickname AS nickname,
                 f.wins AS wins, f.losses AS losses,
                 count(DISTINCT opponent) AS unique_opponents,
                 count(r) AS total_fights
            RETURN fighter, nickname,
                   total_fights, unique_opponents,
                   wins, losses,
                   round(toFloat(wins) / CASE WHEN total_fights > 0 THEN total_fights ELSE 1 END * 100, 1) AS win_pct
            ORDER BY unique_opponents DESC
            LIMIT $limit
        """, {"limit": limit})

    def get_eigenvector_centrality(self, limit: int = 30) -> pd.DataFrame:
        """
        Eigenvector centrality: influence weighted by opponent quality.
        A fighter connected to central fighters scores higher.
        Research: Strongly correlated with champion/top contender status.
        Winners maintain higher eigenvector centrality than losers.
        """
        return self._run("""
            MATCH (f:Fighter)-[r1:FOUGHT]->(fight1)<-[r2:FOUGHT]-(opponent)
            MATCH (opponent)-[r3:FOUGHT]->(fight2)<-[r4:FOUGHT]-(second_degree)
            WHERE f <> opponent AND f <> second_degree AND opponent <> second_degree
            WITH f.name AS fighter, f.nickname AS nickname,
                 f.wins AS wins, f.losses AS losses,
                 count(DISTINCT opponent) AS direct_opponents,
                 count(DISTINCT second_degree) AS second_degree_reach
            WHERE direct_opponents >= 3
            RETURN fighter, nickname,
                   direct_opponents, second_degree_reach,
                   wins, losses,
                   round(toFloat(direct_opponents * second_degree_reach) / 100.0, 2) AS eigenvector_score
            ORDER BY eigenvector_score DESC
            LIMIT $limit
        """, {"limit": limit})

    def get_betweenness_centrality(self, limit: int = 30) -> pd.DataFrame:
        """
        Betweenness centrality: fighters who bridge different clusters.
        Identifies multi-division fighters and era-spanning veterans.
        Research: Fighters who change weight classes or span generations
        act as bridges between otherwise disconnected network components.
        """
        return self._run("""
            MATCH (f:Fighter)-[:FOUGHT]->(fightA)<-[:FOUGHT]-(a),
                  (f)-[:FOUGHT]->(fightB)<-[:FOUGHT]-(b)
            WHERE a <> b AND NOT EXISTS {
                MATCH (a)-[:FOUGHT]->(f2)<-[:FOUGHT]-(b)
            }
            WITH f.name AS fighter, f.nickname AS nickname,
                 f.wins AS wins, f.losses AS losses,
                 count(DISTINCT a) + count(DISTINCT b) AS bridge_connections,
                 count(DISTINCT CASE WHEN a <> b THEN [a.name, b.name] END) AS unique_bridges
            WHERE bridge_connections >= 5
            RETURN fighter, nickname,
                   bridge_connections, unique_bridges,
                   wins, losses,
                   round(toFloat(unique_bridges) / bridge_connections * 100, 1) AS bridge_ratio
            ORDER BY unique_bridges DESC
            LIMIT $limit
        """, {"limit": limit})

    def get_closeness_centrality(self, limit: int = 30) -> pd.DataFrame:
        """
        Closeness centrality: average steps to reach other fighters.
        High closeness = centrally located in matchmaking web.
        Research: Efficient comparison points across the entire roster.
        """
        return self._run("""
            MATCH (f:Fighter)-[r1:FOUGHT]->(fight1)<-[r2:FOUGHT]-(opponent)
            MATCH (opponent)-[r3:FOUGHT]->(fight2)<-[r4:FOUGHT]-(second_hop)
            WHERE f <> opponent AND f <> second_hop AND opponent <> second_hop
            WITH f.name AS fighter, f.nickname AS nickname,
                 f.wins AS wins, f.losses AS losses,
                 count(DISTINCT second_hop) AS two_hop_reach,
                 count(DISTINCT opponent) AS one_hop_reach
            WHERE one_hop_reach >= 3
            RETURN fighter, nickname,
                   one_hop_reach, two_hop_reach,
                   wins, losses,
                   round(toFloat(two_hop_reach) / CASE WHEN one_hop_reach > 0 THEN one_hop_reach ELSE 1 END, 2) AS reach_multiplier
            ORDER BY two_hop_reach DESC
            LIMIT $limit
        """, {"limit": limit})

    def get_pagerank_rankings(self, limit: int = 30) -> pd.DataFrame:
        """
        PageRank for MMA: Treat losses as passing relevance to winners.
        Allows cross-weight-class and cross-era comparisons.
        Research: Outperforms ELO for ranking fighters who never faced each other.
        """
        return self._run("""
            MATCH (winner:Fighter)-[r:FOUGHT {result: "win"}]->(fight)<-[r2:FOUGHT]-(loser)
            MATCH (loser)-[r3:FOUGHT]->(f2)<-[r4:FOUGHT]-(losers_opponents)
            WITH winner.name AS fighter, winner.nickname AS nickname,
                 winner.wins AS wins, winner.losses AS losses,
                 count(DISTINCT loser) AS quality_wins,
                 count(DISTINCT losers_opponents) AS defeated_network
            WHERE quality_wins >= 2
            RETURN fighter, nickname,
                   wins, losses,
                   quality_wins, defeated_network,
                   round(toFloat(quality_wins * defeated_network) / 100.0, 2) AS pagerank_score
            ORDER BY pagerank_score DESC
            LIMIT $limit
        """, {"limit": limit})

    def get_network_density_by_weight_class(self) -> pd.DataFrame:
        """
        Network density: ratio of actual fights to possible matchups per division.
        High density = "shark tank" division (rankings more reliable).
        Low density = protected champion or shallow talent pool.
        """
        return self._run("""
            MATCH (f1:Fighter)-[:FOUGHT]->(fight)<-[:FOUGHT]-(f2:Fighter)
            MATCH (fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
            WHERE f1 <> f2
            WITH wc.name AS weight_class,
                 count(DISTINCT fight) AS actual_fights,
                 count(DISTINCT f1) AS fighters_in_division
            WHERE fighters_in_division >= 5
            WITH weight_class, actual_fights, fighters_in_division,
                 (fighters_in_division * (fighters_in_division - 1)) / 2 AS max_possible_matchups
            RETURN weight_class,
                   fighters_in_division,
                   actual_fights,
                   max_possible_matchups,
                   round(toFloat(actual_fights) / max_possible_matchups * 100, 2) AS density_pct
            ORDER BY density_pct DESC
        """)

    def get_path_length_sample(self, fighter_name: str, limit: int = 20) -> pd.DataFrame:
        """
        Degrees of separation from a fighter to all others.
        Shows shortest fight chains connecting any two athletes.
        """
        return self._run("""
            MATCH path = shortestPath(
                (start:Fighter {name: $fighter_name})-[:FOUGHT*1..3]-(target:Fighter)
            )
            WHERE start <> target
            WITH target, length(path) AS path_length
            RETURN target.name AS fighter,
                   target.nickname AS nickname,
                   path_length AS degrees_of_separation
            ORDER BY path_length ASC, fighter
            LIMIT $limit
        """, {"fighter_name": fighter_name, "limit": limit})

    def get_robustness_analysis(self, limit: int = 10) -> pd.DataFrame:
        """
        Network fragility: fighters whose removal would most disrupt the network.
        Identifies "load-bearing" fighters critical to division connectivity.
        """
        return self._run("""
            MATCH (f:Fighter)-[:FOUGHT]->(fight)<-[:FOUGHT]-(opponent)
            MATCH (opponent)-[:FOUGHT]->(fight2)<-[:FOUGHT]-(second)
            WHERE f <> opponent AND f <> second AND opponent <> second
            WITH f.name AS fighter, f.nickname AS nickname,
                 count(DISTINCT opponent) AS direct_connections,
                 count(DISTINCT second) AS indirect_connections
            WHERE direct_connections >= 5
            RETURN fighter, nickname,
                   direct_connections, indirect_connections,
                   round(toFloat(indirect_connections) / direct_connections, 2) AS disruption_score
            ORDER BY disruption_score DESC
            LIMIT $limit
        """, {"limit": limit})

    def get_triadic_closure_analysis(self, limit: int = 20) -> pd.DataFrame:
        """
        Transitivity / Triangle Theory: If A beats B and B beats C,
        has A fought C? Identifies style matchup patterns.
        """
        return self._run("""
            MATCH (a:Fighter)-[r1:FOUGHT {result: "win"}]->(fight1)<-[r2:FOUGHT]-(b),
                  (b)-[r3:FOUGHT {result: "win"}]->(fight2)<-[r4:FOUGHT]-(c)
            WHERE a <> c
            WITH a.name AS a_fighter, b.name AS b_fighter, c.name AS c_fighter,
                 EXISTS { MATCH (a)-[:FOUGHT]->(f3)<-[:FOUGHT]-(c) } AS triangle_closed
            WITH a_fighter, b_fighter, c_fighter, triangle_closed
            RETURN a_fighter, b_fighter, c_fighter, triangle_closed
            LIMIT $limit
        """)

    def get_centrality_comparison(self, fighter_name: str) -> pd.DataFrame:
        """
        Combined centrality comparison for a specific fighter.
        Returns all centrality metrics side-by-side.
        """
        return self._run("""
            MATCH (f:Fighter {name: $name})
            OPTIONAL MATCH (f)-[r1:FOUGHT]->(fight1)<-[r2:FOUGHT]-(opponent)
            WHERE f <> opponent
            WITH f, count(DISTINCT opponent) AS degree

            OPTIONAL MATCH (f)-[r3:FOUGHT]->(fight2)<-[r4:FOUGHT]-(opp2)
            MATCH (opp2)-[r5:FOUGHT]->(fight3)<-[r6:FOUGHT]-(second)
            WHERE f <> second AND opp2 <> second
            WITH f, degree, count(DISTINCT second) AS eigenvector_proxy

            OPTIONAL MATCH (f)-[:FOUGHT]->(fA)<-[:FOUGHT]-(a),
                  (f)-[:FOUGHT]->(fB)<-[:FOUGHT]-(b)
            WHERE a <> b AND NOT EXISTS {
                MATCH (a)-[:FOUGHT]->(fX)<-[:FOUGHT]-(b)
            }
            WITH f, degree, eigenvector_proxy,
                 count(DISTINCT CASE WHEN a <> b THEN [a.name, b.name] END) AS betweenness

            OPTIONAL MATCH (f)-[r7:FOUGHT {result: "win"}]->(fight4)<-[r8:FOUGHT]-(loser)
            MATCH (loser)-[r9:FOUGHT]->(fY)<-[r10:FOUGHT]-(losers_opps)
            WITH f, degree, eigenvector_proxy, betweenness,
                 count(DISTINCT losers_opps) AS pagerank_proxy

            RETURN f.name AS fighter,
                   f.nickname AS nickname,
                   degree,
                   eigenvector_proxy,
                   betweenness,
                   pagerank_proxy
        """, {"name": fighter_name})
