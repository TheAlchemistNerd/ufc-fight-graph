"""Read queries for the dashboard. Graph writes live in data_access/loader.py."""

from __future__ import annotations

import pandas as pd

from infrastructure.neo4j_client import Neo4jConnection

_TWO_HOP_COUNTS = """
    MATCH (f:Fighter)-[:FOUGHT]->(:Fight)<-[:FOUGHT]-(opponent:Fighter)
    WHERE f <> opponent
    OPTIONAL MATCH (opponent)-[:FOUGHT]->(:Fight)<-[:FOUGHT]-(second:Fighter)
    WHERE second <> f AND second <> opponent
    WITH f, count(DISTINCT opponent) AS direct_opponents,
         count(DISTINCT second) AS second_degree_reach
"""


class BaseRepo:
    """Read queries return DataFrames; database errors propagate to the caller."""

    def __init__(self, db: Neo4jConnection):
        self._db = db

    def _query(self, cypher: str, params: dict | None = None) -> pd.DataFrame:
        return pd.DataFrame(self._db.run_query(cypher, params))


class OverviewRepo(BaseRepo):
    """Dashboard overview metrics."""

    def get_node_counts(self) -> dict:
        df = self._query("""
            MATCH (n)
            WITH labels(n)[0] AS label, count(n) AS cnt
            RETURN label, cnt
        """)
        if df.empty:
            return {}
        return dict(zip(df["label"], df["cnt"]))

    def get_top_active_fighters(self, limit: int = 10) -> pd.DataFrame:
        return self._query(
            """
            MATCH (f:Fighter)-[r:FOUGHT]->(fight)
            WITH f, count(r) AS fights
            RETURN f.name AS name, fights
            ORDER BY fights DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_top_ko_artists(self, limit: int = 10) -> pd.DataFrame:
        return FinishRepo(self._db).get_ko_kings(limit)

    def get_events_over_time(self) -> pd.DataFrame:
        df = self._query("""
            MATCH (e:Event)
            WHERE e.date IS NOT NULL
            RETURN e.date AS date
            ORDER BY date
        """)
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
        df["year"] = df["date"].dt.year
        return df.groupby("year").size().reset_index(name="events")

    def get_recent_events(self, limit: int = 10) -> pd.DataFrame:
        return self._query(
            """
            MATCH (e:Event)-[:HELD_AT]->(loc:Location)
            RETURN e.name AS event, e.date AS date, loc.name AS location
            ORDER BY e.date DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )


class ExplorerRepo(BaseRepo):
    """One row per fight, with nested participants and officials for interactive browsing."""

    def get_fights(self) -> pd.DataFrame:
        return self._query("""
            MATCH (fight:Fight)
            OPTIONAL MATCH (fight)-[:PART_OF]->(event:Event)
            OPTIONAL MATCH (event)-[:HELD_AT]->(location:Location)
            WITH fight, head(collect(DISTINCT event)) AS event,
                 head(collect(DISTINCT location.name)) AS location
            OPTIONAL MATCH (fighter:Fighter)-[result:FOUGHT]->(fight)
            WITH fight, event, location,
                 collect(DISTINCT {name: fighter.name, url: fighter.url, result: result.result})
                 AS fighters
            OPTIONAL MATCH (fight)-[:IN_WEIGHT_CLASS]->(division:WeightClass)
            WITH fight, event, location, fighters, collect(DISTINCT division.name) AS divisions
            OPTIONAL MATCH (fight)-[:OFFICIATED_BY]->(referee:Referee)
            WITH fight, event, location, fighters, divisions,
                 head(collect(DISTINCT referee.name)) AS referee
            OPTIONAL MATCH (fight)-[score:SCORED_BY]->(judge:Judge)
            RETURN fight.url AS fight_url, coalesce(fight.date, event.date) AS date,
                   event.name AS event, event.url AS event_url, location,
                   fight.method AS method, fight.round AS round, fight.time AS time,
                   fight.time_format AS time_format, fight.finish_details AS finish_details,
                   coalesce(fight.is_title_fight, false) AS title_fight,
                   fighters, divisions, referee,
                   [card IN collect(DISTINCT {judge: judge.name, score: score.score})
                    WHERE card.judge IS NOT NULL] AS judges
            ORDER BY date DESC, event, fight_url
        """)


class NetworkCentralityRepo(BaseRepo):
    """Degree and reach metrics; influence/bridge scores are documented proxies."""

    def get_degree_centrality(self, limit: int = 30) -> pd.DataFrame:
        return self._query(
            """
            MATCH (f:Fighter)-[r:FOUGHT]->(fight)<-[r2:FOUGHT]-(opponent)
            WHERE f <> opponent
            WITH f, count(DISTINCT opponent) AS unique_opponents,
                   count(r) AS total_fights,
                   round(100.0 * count(CASE WHEN r.result = "win" THEN 1 END) / count(r), 1) AS win_pct
            RETURN f.name AS fighter, f.nickname AS nickname,
                   f.wins AS wins, f.losses AS losses, unique_opponents, total_fights, win_pct
            ORDER BY unique_opponents DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_eigenvector_centrality(self, limit: int = 30) -> pd.DataFrame:
        return self._query(
            _TWO_HOP_COUNTS
            + """
            WHERE direct_opponents >= 3
            RETURN f.name AS fighter, f.nickname AS nickname,
                   direct_opponents, second_degree_reach,
                   f.wins AS wins, f.losses AS losses,
                   round(toFloat(direct_opponents * second_degree_reach) / 100.0, 2) AS eigenvector_score
            ORDER BY eigenvector_score DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_betweenness_centrality(self, limit: int = 30) -> pd.DataFrame:
        return self._query(
            """
            MATCH (f:Fighter)-[:FOUGHT]->(fightA)<-[:FOUGHT]-(a),
                  (f)-[:FOUGHT]->(fightB)<-[:FOUGHT]-(b)
            WHERE elementId(a) < elementId(b) AND f <> a AND f <> b AND NOT EXISTS {
                MATCH (a)-[:FOUGHT]->(f2)<-[:FOUGHT]-(b)
            }
            WITH f, collect(DISTINCT a) + collect(DISTINCT b) AS endpoints,
                 count(DISTINCT [elementId(a), elementId(b)]) AS unique_bridges
            UNWIND endpoints AS endpoint
            WITH f, unique_bridges,
                 count(DISTINCT endpoint) AS bridge_connections
            WHERE bridge_connections >= 5
            RETURN f.name AS fighter, f.nickname AS nickname,
                   bridge_connections, unique_bridges,
                   f.wins AS wins, f.losses AS losses,
                   round(toFloat(unique_bridges) / bridge_connections * 100, 1) AS bridge_ratio
            ORDER BY unique_bridges DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_closeness_centrality(self, limit: int = 30) -> pd.DataFrame:
        return self._query(
            _TWO_HOP_COUNTS
            + """
            WHERE direct_opponents >= 3
            RETURN f.name AS fighter, f.nickname AS nickname,
                   direct_opponents AS one_hop_reach, second_degree_reach AS two_hop_reach,
                   f.wins AS wins, f.losses AS losses,
                   round(toFloat(second_degree_reach) / direct_opponents, 2) AS reach_multiplier
            ORDER BY two_hop_reach DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_pagerank_rankings(self, limit: int = 30) -> pd.DataFrame:
        return self._query(
            """
            MATCH (winner:Fighter)-[r:FOUGHT {result: "win"}]->(fight)<-[r2:FOUGHT {result: "loss"}]-(loser)
            OPTIONAL MATCH (loser)-[:FOUGHT]->(f2)<-[:FOUGHT]-(losers_opponents)
            WHERE losers_opponents <> winner AND losers_opponents <> loser
            WITH winner, count(DISTINCT loser) AS quality_wins,
                 count(DISTINCT losers_opponents) AS defeated_network
            WHERE quality_wins >= 2
            RETURN winner.name AS fighter, winner.nickname AS nickname,
                   winner.wins AS wins, winner.losses AS losses,
                   quality_wins, defeated_network,
                   round(toFloat(quality_wins * defeated_network) / 100.0, 2) AS pagerank_score
            ORDER BY pagerank_score DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_network_density_by_weight_class(self) -> pd.DataFrame:
        return self._query("""
            MATCH (f1:Fighter)-[:FOUGHT]->(fight)<-[:FOUGHT]-(f2:Fighter)
            MATCH (fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
            WHERE f1 <> f2
            WITH wc.name AS weight_class,
                 count(DISTINCT fight) AS actual_fights,
                 count(DISTINCT CASE WHEN elementId(f1) < elementId(f2) THEN [elementId(f1), elementId(f2)] END) AS unique_matchups,
                 count(DISTINCT f1) AS fighters_in_division
            WHERE fighters_in_division >= 5
            WITH weight_class, actual_fights, unique_matchups, fighters_in_division,
                 (fighters_in_division * (fighters_in_division - 1)) / 2 AS max_possible_matchups
            RETURN weight_class,
                   fighters_in_division,
                   actual_fights,
                   max_possible_matchups,
                   round(toFloat(unique_matchups) / max_possible_matchups * 100, 2) AS density_pct
            ORDER BY density_pct DESC
        """)

    def get_path_length_sample(self, fighter_name: str, limit: int = 20) -> pd.DataFrame:
        return self._query(
            """
            MATCH (start:Fighter), (target:Fighter)
            WHERE (start.url = $fighter_name OR start.name = $fighter_name) AND start <> target
            MATCH path = shortestPath((start)-[:FOUGHT*1..6]-(target))
            RETURN target.name AS fighter,
                   target.nickname AS nickname,
                   length(path) / 2 AS degrees_of_separation
            ORDER BY degrees_of_separation ASC, fighter
            LIMIT $limit
        """,
            {"fighter_name": fighter_name, "limit": limit},
        )

    def get_robustness_analysis(self, limit: int = 10) -> pd.DataFrame:
        return self._query(
            _TWO_HOP_COUNTS
            + """
            WHERE direct_opponents >= 5
            RETURN f.name AS fighter, f.nickname AS nickname,
                   direct_opponents AS direct_connections,
                   second_degree_reach AS indirect_connections,
                   round(toFloat(second_degree_reach) / direct_opponents, 2) AS disruption_score
            ORDER BY disruption_score DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )


class JudgeRepo(BaseRepo):
    """Judge scoring analysis."""

    def get_judge_activity_volume(self, limit: int = 20) -> pd.DataFrame:
        return self._query(
            """
            MATCH (fight)-[r:SCORED_BY]->(j:Judge)
            RETURN j.name AS judge,
                   count(fight) AS fights_scored,
                   count(DISTINCT r.score) AS unique_scorecards_given
            ORDER BY fights_scored DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_judge_widest_margins(self, limit: int = 20) -> pd.DataFrame:
        return self._query(
            """
            MATCH (fight)-[r:SCORED_BY]->(j:Judge)
            WHERE r.score IS NOT NULL
            WITH j.name AS judge, r.score AS scorecard,
                 fight.url AS fight_url, fight.method AS method
            WITH judge, scorecard, fight_url, method,
                 toInteger(trim(split(scorecard, "-")[0])) AS score_a,
                 toInteger(trim(split(scorecard, "-")[1])) AS score_b
            WHERE score_a IS NOT NULL AND score_b IS NOT NULL
            WITH judge, scorecard, fight_url, method,
                 abs(score_a - score_b) AS margin
            RETURN judge, scorecard, margin, fight_url, method
            ORDER BY margin DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_wide_scorecards(self, limit: int = 15) -> pd.DataFrame:
        return self._query(
            """
            MATCH (fight)-[r:SCORED_BY]->(j:Judge)
            WHERE r.score IS NOT NULL
            WITH j.name AS judge, r.score AS scorecard
            WITH judge, scorecard,
                 toInteger(trim(split(scorecard, "-")[0])) AS score_a,
                 toInteger(trim(split(scorecard, "-")[1])) AS score_b
            WHERE score_a IS NOT NULL AND score_b IS NOT NULL
            WITH judge, scorecard, abs(score_a - score_b) AS total_margin
            WHERE total_margin >= 5
            RETURN judge, count(scorecard) AS wide_margins
            ORDER BY wide_margins DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_judge_consistency_analysis(self, limit: int = 20) -> pd.DataFrame:
        return self._query(
            """
            MATCH (fight)-[r1:SCORED_BY]->(j1:Judge),
                  (fight)-[r2:SCORED_BY]->(j2:Judge)
            WHERE j1 <> j2 AND r1.score = r2.score
            RETURN j1.name AS judge,
                   count(fight) AS agreements
            ORDER BY agreements DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_all_judge_names(self) -> list:
        df = self._query("MATCH (j:Judge) RETURN j.name AS name ORDER BY j.name")
        return df["name"].tolist() if not df.empty else []


class FighterRepo(BaseRepo):
    """Fighter profiles, search, fight history, similarity."""

    def get_all_fighter_names(self) -> list:
        return [fighter["name"] for fighter in self.get_fighter_options()]

    def get_fighter_options(self) -> list:
        return self._query(
            "MATCH (f:Fighter) RETURN f.name AS name, f.url AS url ORDER BY name, url"
        ).to_dict("records")

    def get_fighter_profile(self, name: str) -> pd.DataFrame:
        return self._query(
            """
            MATCH (f:Fighter) WHERE f.url = $name OR f.name = $name
            RETURN f.name AS name, f.nickname AS nickname,
                   f.record AS record, f.stance AS stance,
                   f.height AS height, f.reach AS reach, f.weight AS weight,
                   f.wins AS wins, f.losses AS losses, f.draws AS draws,
                   f.url AS url, f.dob AS dob, f.slpm AS slpm, f.sapm AS sapm,
                   f.str_acc AS str_acc, f.str_def AS str_def,
                   f.td_avg AS td_avg, f.td_acc AS td_acc, f.td_def AS td_def,
                   f.sub_avg AS sub_avg
        """,
            {"name": name},
        )

    def get_fighter_history(self, name: str) -> pd.DataFrame:
        return self._query(
            """
            MATCH (f:Fighter) WHERE f.url = $name OR f.name = $name
            MATCH (f)-[r:FOUGHT]->(fight)-[:PART_OF]->(e:Event)
            OPTIONAL MATCH (fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
            OPTIONAL MATCH (fight)-[:OFFICIATED_BY]->(ref:Referee)
            RETURN ref.name AS referee, r.result AS result, fight.method AS method,
                   fight.round AS round, fight.time AS time,
                   fight.date AS date, wc.name AS weight_class,
                   e.name AS event
            ORDER BY fight.date DESC
        """,
            {"name": name},
        )

    def get_similar_fighters(self, name: str, limit: int = 10) -> pd.DataFrame:
        return self._query(
            """
            MATCH (target:Fighter)
            WHERE (target.url = $name OR target.name = $name)
                  AND toFloat(target.slpm) IS NOT NULL AND toFloat(target.str_acc) IS NOT NULL
                  AND toFloat(target.sapm) IS NOT NULL
            MATCH (f:Fighter)
            WHERE f <> target AND toFloat(f.slpm) IS NOT NULL
                  AND toFloat(f.str_acc) IS NOT NULL AND toFloat(f.sapm) IS NOT NULL
            WITH f, target,
                 abs(toFloat(f.slpm) - toFloat(target.slpm)) +
                 abs(toFloat(f.str_acc) - toFloat(target.str_acc)) +
                 abs(toFloat(f.sapm) - toFloat(target.sapm)) AS distance
            ORDER BY distance ASC
            LIMIT $limit
            RETURN f.name AS fighter, f.nickname AS nickname,
                   f.slpm AS slpm, f.str_acc AS str_acc, f.sapm AS sapm,
                   round(distance, 3) AS distance
        """,
            {"name": name, "limit": limit},
        )


class NetworkRepo(BaseRepo):
    """Graph relationships: transitive wins, common opponents, network data."""

    def get_transitive_wins(self, fighter_name: str, limit: int = 30) -> pd.DataFrame:
        """Fighters who beat someone who beat the selected fighter."""
        return self._query(
            """
            MATCH (target:Fighter) WHERE target.url = $name OR target.name = $name
            MATCH (target)-[:FOUGHT {result: "loss"}]->(:Fight)
                  <-[:FOUGHT {result: "win"}]-(middle:Fighter),
                  (middle)-[:FOUGHT {result: "loss"}]->(:Fight)
                  <-[:FOUGHT {result: "win"}]-(winner:Fighter)
            WHERE winner <> target
            RETURN DISTINCT winner.name AS fighter, middle.name AS via,
                            winner.url AS fighter_url, middle.url AS via_url
            ORDER BY fighter, via LIMIT $limit
        """,
            {"name": fighter_name, "limit": limit},
        )

    def get_common_opponents(self, f1_name: str, f2_name: str) -> pd.DataFrame:
        return self._query(
            """
            MATCH (a:Fighter), (b:Fighter)
            WHERE (a.url = $f1 OR a.name = $f1) AND (b.url = $f2 OR b.name = $f2)
            MATCH (a)-[:FOUGHT]->(fight1)<-[:FOUGHT]-(o:Fighter),
                  (b)-[:FOUGHT]->(fight2)<-[:FOUGHT]-(o)
            WHERE a <> b AND a <> o AND b <> o
            RETURN DISTINCT o.name AS opponent, o.url AS opponent_url
        """,
            {"f1": f1_name, "f2": f2_name},
        )

    def get_network_sample(self, limit: int = 50) -> pd.DataFrame:
        return self._query(
            """
            MATCH (f1:Fighter)-[:FOUGHT]->(fight)<-[:FOUGHT]-(f2:Fighter)
            MATCH (fight)-[:PART_OF]->(e:Event)
            WHERE elementId(f1) < elementId(f2)
            RETURN f1.name AS f1, f2.name AS f2, e.name AS event,
                   f1.url AS f1_url, f2.url AS f2_url
            LIMIT $limit
        """,
            {"limit": limit},
        )


class RefereeRepo(BaseRepo):
    """Referee analysis: finish rates, activity volume."""

    def get_coverage(self) -> dict:
        from data_access.loader import Neo4jLoader

        return Neo4jLoader(self._db).coverage()

    def get_referee_finish_rates(self, min_fights: int = 3) -> pd.DataFrame:
        return self._query(
            """
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
        """,
            {"min_fights": min_fights},
        )

    def get_top_referees(self, limit: int = 10) -> pd.DataFrame:
        return self._query(
            """
            MATCH (ref:Referee)<-[:OFFICIATED_BY]-(fight)
            RETURN ref.name AS referee, count(fight) AS fights
            ORDER BY fights DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )


class StrikingRepo(BaseRepo):
    """Striking and grappling efficiency metrics."""

    def get_striking_efficiency(self, min_slpm: float = 2.0) -> pd.DataFrame:
        return self._query(
            """
            MATCH (f:Fighter)
            WHERE f.slpm IS NOT NULL AND f.sapm IS NOT NULL AND toFloat(f.sapm) > 0
            WITH f.name AS fighter, f.nickname AS nickname,
                   toFloat(f.slpm) AS slpm, toFloat(f.sapm) AS sapm,
                   toFloat(f.slpm) / toFloat(f.sapm) AS strike_ratio
            WHERE slpm >= $min_slpm
            RETURN fighter, nickname,
                   round(slpm, 2) AS slpm, round(sapm, 2) AS sapm,
                   round(strike_ratio, 2) AS strike_ratio
            ORDER BY strike_ratio DESC
            LIMIT 20
        """,
            {"min_slpm": min_slpm},
        )

    def get_reach_advantage(self) -> pd.DataFrame:
        return self._query("""
            MATCH (longer:Fighter)-[r:FOUGHT]->(fight:Fight)<-[:FOUGHT]-(shorter:Fighter)
            WHERE longer.reach_inches > shorter.reach_inches AND r.result IN ['win', 'loss']
            WITH longer.reach_inches - shorter.reach_inches AS reach_diff, r
            RETURN round(reach_diff, 1) AS reach_advantage_inches,
                   count(r) AS fights,
                   round(100.0 * count(CASE WHEN r.result = 'win' THEN 1 END) / count(r), 1) AS longer_reach_win_pct
            ORDER BY reach_advantage_inches
        """)


class GeographyRepo(BaseRepo):
    """Location-based event analysis."""

    def get_events_by_location(self, limit: int = 15) -> pd.DataFrame:
        return self._query(
            """
            MATCH (e:Event)-[:HELD_AT]->(loc:Location)
            OPTIONAL MATCH (fight:Fight)-[:PART_OF]->(e)
            RETURN loc.name AS location,
                 count(DISTINCT e) AS events,
                 count(DISTINCT fight) AS total_fights
            ORDER BY events DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_fight_outcomes_by_location(self, limit: int = 20) -> pd.DataFrame:
        return self._query(
            """
            MATCH (e:Event)-[:HELD_AT]->(loc:Location)
            MATCH (fight:Fight)-[:PART_OF]->(e)
            RETURN loc.name AS location,
                   coalesce(fight.method, 'Unknown') AS result,
                   count(fight) AS count
            ORDER BY count DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )


class WeightClassRepo(BaseRepo):
    """Weight class dominance, distribution, breakdowns."""

    def get_all_weight_classes(self) -> list:
        df = self._query("MATCH (w:WeightClass) RETURN w.name AS name ORDER BY w.name")
        return df["name"].tolist() if not df.empty else []

    def get_win_rates(self, weight_class: str | None = None, min_fights: int = 3) -> pd.DataFrame:
        return self._query(
            """
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
        """,
            {"wc": weight_class, "min_fights": min_fights},
        )


class CareerRepo(BaseRepo):
    """Career trajectory, longevity, layoff analysis."""

    def get_career_lengths(self) -> pd.DataFrame:
        return self._query("""
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
        return self._query("""
            MATCH (f:Fighter)-[r:FOUGHT {result: "win"}]->(fight)
            WHERE toInteger(f.wins) < toInteger(f.losses)
            WITH f, count(fight) AS upset_wins,
                   collect(distinct fight.method) AS upset_methods
            RETURN f.name AS fighter, f.wins AS career_wins, f.losses AS career_losses, upset_wins,
                   size(upset_methods) AS different_methods
            ORDER BY upset_wins DESC
            LIMIT 15
        """)

    def get_post_loss_rebound(self, limit: int = 20) -> pd.DataFrame:
        return self._query(
            """
            MATCH (f:Fighter)-[r:FOUGHT]->(fight:Fight)
            WHERE fight.date IS NOT NULL AND r.result IS NOT NULL
            WITH f, fight, r ORDER BY fight.date, fight.url
            WITH f, collect(r.result) AS outcomes
            WHERE size(outcomes) >= 2
            UNWIND range(0, size(outcomes) - 2) AS i
            WITH f, outcomes, i WHERE outcomes[i] = 'loss'
            WITH f, count(*) AS fights_after_loss,
                   count(CASE WHEN outcomes[i+1] = 'win' THEN 1 END) AS wins_after_loss,
                   round(100.0 * count(CASE WHEN outcomes[i+1] = 'win' THEN 1 END) / count(*), 1) AS rebound_pct
            RETURN f.name AS fighter, fights_after_loss, wins_after_loss, rebound_pct
            ORDER BY fights_after_loss DESC LIMIT $limit
        """,
            {"limit": limit},
        )


class EvolutionRepo(BaseRepo):
    """Physical and statistical trends across eras."""

    def get_physical_by_era(self) -> pd.DataFrame:
        return self._query("""
            MATCH (f:Fighter)
            WHERE f.height_inches IS NOT NULL AND f.reach_inches IS NOT NULL
            WITH f, coalesce(toInteger(left(f.dob, 4)), toInteger(trim(last(split(f.dob, ","))))) AS birth_year
            WHERE birth_year IS NOT NULL
            WITH f,
                 CASE
                   WHEN birth_year < 1980 THEN "Pre-1980"
                   WHEN birth_year < 1990 THEN "1980s"
                   WHEN birth_year < 2000 THEN "1990s"
                   ELSE "2000s"
                 END AS era
            RETURN era,
                   count(f) AS fighters,
                   round(avg(f.height_inches), 1) AS avg_height,
                   round(avg(f.reach_inches), 1) AS avg_reach
            ORDER BY era
        """)

    def get_striking_by_era(self) -> pd.DataFrame:
        return self._query("""
            MATCH (f:Fighter)
            WHERE f.slpm IS NOT NULL
            WITH f, coalesce(toInteger(left(f.dob, 4)), toInteger(trim(last(split(f.dob, ","))))) AS birth_year
            WHERE birth_year IS NOT NULL
            WITH f,
                 CASE
                   WHEN birth_year < 1980 THEN "Pre-1980"
                   WHEN birth_year < 1990 THEN "1980s"
                   WHEN birth_year < 2000 THEN "1990s"
                   ELSE "2000s"
                 END AS era
            RETURN era,
                   count(f) AS fighters,
                   round(avg(toFloat(f.slpm)), 2) AS avg_slpm
            ORDER BY era
        """)


class FightPaceRepo(BaseRepo):
    """Fight duration, card structure, pace analysis."""

    def get_duration_by_weight_class(self) -> pd.DataFrame:
        return self._query("""
            MATCH (fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
            WHERE fight.round IS NOT NULL AND fight.time IS NOT NULL
            WITH wc.name AS weight_class, fight,
                 toInteger(fight.round) AS round_num,
                 split(fight.time, ":") AS time_parts,
                 split(split(split(fight.time_format, '(')[1], ')')[0], '-') AS round_minutes
            WITH weight_class,
                 CASE WHEN round_num = 1 THEN 0
                      WHEN size(round_minutes) >= round_num - 1 THEN
                          reduce(seconds = 0, minutes IN round_minutes[..round_num - 1] |
                                 seconds + toInteger(minutes) * 60)
                      WHEN fight.time_format IS NULL THEN (round_num - 1) * 300
                 END +
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
        return self._query("""
            MATCH (fight)-[:PART_OF]->(e:Event)
            WHERE e.date IS NOT NULL
            WITH e.date AS event_date, fight,
                 coalesce(toInteger(left(e.date, 4)), toInteger(trim(last(split(e.date, ","))))) AS year
            WHERE year IS NOT NULL AND year > 1900
            WITH year,
                   count(fight) AS total_fights,
                   count(CASE WHEN toUpper(fight.method) CONTAINS "KO" OR toUpper(fight.method) CONTAINS "TKO" OR toUpper(fight.method) CONTAINS "SUB" THEN 1 END) AS finishes
            RETURN year,
                   total_fights, finishes,
                   round(toFloat(finishes) / total_fights * 100, 1) AS finish_pct
            ORDER BY year ASC
        """)


class StyleMatchupRepo(BaseRepo):
    """Stance matchups, style-based analysis."""

    def get_stance_matchups(self) -> pd.DataFrame:
        return self._query("""
            MATCH (f1:Fighter)-[r1:FOUGHT {result: "win"}]->(fight)<-[r2:FOUGHT]-(f2:Fighter)
            WHERE f1.stance IS NOT NULL AND f2.stance IS NOT NULL
              AND f1.stance <> f2.stance
            WITH f1.stance AS winner_stance, f2.stance AS loser_stance,
                   count(fight) AS wins
            RETURN winner_stance, loser_stance, wins
            ORDER BY wins DESC
        """)


class FinishRepo(BaseRepo):
    """Knockout and submission specialist analysis."""

    def get_ko_kings(self, limit: int = 20) -> pd.DataFrame:
        return self._query(
            """
            MATCH (f:Fighter)-[r:FOUGHT {result: "win"}]->(fight)
            WHERE toUpper(fight.method) CONTAINS "KO" OR toUpper(fight.method) CONTAINS "TKO"
            WITH f, count(fight) AS ko_wins
            RETURN f.name AS name, f.nickname AS nickname, ko_wins
            ORDER BY ko_wins DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )

    def get_sub_specialists(self, limit: int = 20) -> pd.DataFrame:
        return self._query(
            """
            MATCH (f:Fighter)-[r:FOUGHT {result: "win"}]->(fight)
            WHERE toUpper(fight.method) CONTAINS "SUB"
            WITH f, count(fight) AS sub_wins
            RETURN f.name AS name, f.nickname AS nickname, sub_wins
            ORDER BY sub_wins DESC
            LIMIT $limit
        """,
            {"limit": limit},
        )


class ChampionshipRepo(BaseRepo):
    """Title fight analysis and championship patterns."""

    def get_title_vs_regular_finish_rates(self) -> pd.DataFrame:
        return self._query("""
            MATCH (fight:Fight)
            WITH fight, (toUpper(fight.method) CONTAINS 'KO' OR toUpper(fight.method) CONTAINS 'SUB') AS finish
            WITH count(fight) AS total_fights,
                 count(CASE WHEN finish THEN 1 END) AS finishes,
                 count(CASE WHEN fight.is_title_fight THEN 1 END) AS title_fights,
                 count(CASE WHEN fight.is_title_fight AND finish THEN 1 END) AS title_finishes
            RETURN title_fights, total_fights,
                   CASE WHEN title_fights > 0 THEN round(100.0 * title_finishes / title_fights, 1) ELSE null END AS title_finish_pct,
                   CASE WHEN total_fights > 0 THEN round(100.0 * finishes / total_fights, 1) ELSE null END AS overall_finish_pct
        """)
