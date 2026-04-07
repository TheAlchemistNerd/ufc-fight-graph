"""
Graph Analytics Queries for the UFC Neo4j Database.
Demonstrates centrality, win/loss network analysis, and fighter similarity.
"""

from neo4j import GraphDatabase

class UfcAnalytics:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    # ===================== TASK 14: Graph Centrality =====================

    def fighter_degree_centrality(self, limit=20):
        """
        Degree centrality: fighters with the most connections (fights).
        High degree = active/veteran fighters.
        """
        query = """
        MATCH (f:Fighter)-[r:FOUGHT]->(fight)
        WITH f, count(r) AS degree
        RETURN f.name AS fighter,
               f.nickname AS nickname,
               f.wins AS wins,
               f.losses AS losses,
               degree AS total_fights
        ORDER BY degree DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            return [dict(record) for record in result]

    def fight_betweenness_centrality(self, limit=10):
        """
        Betweenness-style: events that connect the most fighters.
        High betweenness events are pivotal in the network.
        """
        query = """
        MATCH (fight:Fight)-[:PART_OF]->(e:Event)
        MATCH (f1:Fighter)-[:FOUGHT]->(fight)<-[:FOUGHT]-(f2:Fighter)
        WITH e, count(DISTINCT f1) + count(DISTINCT f2) AS fighter_count
        RETURN e.name AS event,
               e.date AS date,
               fighter_count AS fighters_involved
        ORDER BY fighter_count DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            return [dict(record) for record in result]

    def referee_centrality(self, limit=10):
        """
        Which referees officiate the most fights?
        """
        query = """
        MATCH (ref:Referee)<-[:OFFICIATED_BY]-(fight)
        WITH ref, count(fight) AS fights_officiated,
             collect(DISTINCT (fight).method) AS methods
        RETURN ref.name AS referee,
               fights_officiated,
               methods
        ORDER BY fights_officiated DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            return [dict(record) for record in result]

    # ===================== TASK 15: Win/Loss Network Analysis =====================

    def transitive_wins(self, fighter_name, depth=2):
        """
        Find all fighters who are transitively connected through wins.
        E.g., fighters who beat someone who beat the target fighter.
        """
        query = """
        MATCH (target:Fighter {name: $fighter_name})<-[:FOUGHT]-(fight1)<-[:FOUGHT {result: "win"}]-(beaten_by:Fighter)
        WHERE beaten_by <> target
        WITH DISTINCT beaten_by, target
        MATCH (beaten_by)-[:FOUGHT {result: "win"}]->(fight2)<-[:FOUGHT]-(i_beat_them:Fighter)
        WHERE i_beat_them <> target
        RETURN DISTINCT i_beat_them.name AS fighter,
               beaten_by.name AS via,
               i_beat_them.wins AS their_wins,
               i_beat_them.losses AS their_losses
        ORDER BY their_wins DESC
        LIMIT 50
        """
        with self.driver.session() as session:
            result = session.run(query, fighter_name=fighter_name)
            return [dict(record) for record in result]

    def common_opponents(self, fighter1_name, fighter2_name):
        """
        Find all common opponents between two fighters.
        """
        query = """
        MATCH (a:Fighter {name: $fighter1})-[:FOUGHT]->(fight1)<-[:FOUGHT]-(o:Fighter),
              (b:Fighter {name: $fighter2})-[:FOUGHT]->(fight2)<-[:FOUGHT]-(o)
        WHERE a <> b AND a <> o AND b <> o
        RETURN DISTINCT o.name AS common_opponent,
               o.wins AS opponent_wins,
               o.losses AS opponent_losses
        ORDER BY opponent_wins DESC
        """
        with self.driver.session() as session:
            result = session.run(query, fighter1=fighter1_name, fighter2=fighter2_name)
            return [dict(record) for record in result]

    def win_streak_analysis(self, fighter_name):
        """
        Get the fight history of a fighter ordered by fight date.
        """
        query = """
        MATCH (f:Fighter {name: $fighter_name})-[r:FOUGHT]->(fight)
        OPTIONAL MATCH (fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
        OPTIONAL MATCH (fight)-[:PART_OF]->(e:Event)
        RETURN fight.url AS fight_url,
               fight.method AS method,
               fight.round AS round,
               fight.time AS time,
               fight.date AS date,
               r.result AS result,
               wc.name AS weight_class,
               e.name AS event
        ORDER BY fight.date DESC
        """
        with self.driver.session() as session:
            result = session.run(query, fighter_name=fighter_name)
            return [dict(record) for record in result]

    def knockout_kings(self, limit=10):
        """
        Fighters with the most KO/TKO wins.
        """
        query = """
        MATCH (f:Fighter)-[r:FOUGHT {result: "win"}]->(fight)
        WHERE toUpper(fight.method) CONTAINS "KO" OR toUpper(fight.method) CONTAINS "TKO"
        RETURN f.name AS fighter,
               f.nickname AS nickname,
               count(fight) AS ko_wins
        ORDER BY ko_wins DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            return [dict(record) for record in result]

    def submission_specialists(self, limit=10):
        """
        Fighters with the most submission wins.
        """
        query = """
        MATCH (f:Fighter)-[r:FOUGHT {result: "win"}]->(fight)
        WHERE toUpper(fight.method) CONTAINS "SUB"
        RETURN f.name AS fighter,
               f.nickname AS nickname,
               count(fight) AS sub_wins
        ORDER BY sub_wins DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            return [dict(record) for record in result]

    # ===================== TASK 16: Fighter Similarity Clustering =====================

    def fighter_stats_for_clustering(self):
        """
        Export fighter stats suitable for clustering (KMeans, HDBSCAN, etc.).
        Returns normalized numerical features for each fighter.
        """
        query = """
        MATCH (f:Fighter)
        WHERE f.slpm IS NOT NULL OR f.wins IS NOT NULL
        RETURN f.name AS name,
               f.nickname AS nickname,
               f.height_inches AS height_inches,
               f.weight_lbs AS weight_lbs,
               f.reach_inches AS reach_inches,
               f.slpm AS slpm,
               f.str_acc AS str_acc,
               f.sapm AS sapm,
               f.str_def AS str_def,
               f.td_avg AS td_avg,
               f.td_acc AS td_acc,
               f.td_def AS td_def,
               f.sub_avg AS sub_avg,
               f.wins AS wins,
               f.losses AS losses,
               f.stance AS stance
        """
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record) for record in result]

    def striking_style_similarity(self, fighter_name, limit=10):
        """
        Find fighters with similar striking profiles (SLpM, Str Acc, Str Def).
        Simple distance-based similarity.
        """
        query = """
        MATCH (target:Fighter {name: $fighter_name})
        WHERE target.slpm IS NOT NULL
        MATCH (f:Fighter)
        WHERE f <> target AND f.slpm IS NOT NULL
        WITH f, target,
             abs(toFloat(f.slpm) - toFloat(target.slpm)) AS slpm_diff,
             abs(toFloat(coalesce(f.str_acc, 0)) - toFloat(coalesce(target.str_acc, 0))) AS acc_diff,
             abs(toFloat(coalesce(f.sapm, 0)) - toFloat(coalesce(target.sapm, 0))) AS sapm_diff,
             abs(toFloat(coalesce(f.str_def, 0)) - toFloat(coalesce(target.str_def, 0))) AS def_diff
        WITH f, target,
             slpm_diff + acc_diff + sapm_diff + def_diff AS total_distance
        ORDER BY total_distance ASC
        LIMIT $limit
        RETURN f.name AS similar_fighter,
               f.nickname AS nickname,
               f.slpm AS slpm,
               f.str_acc AS str_acc,
               f.str_def AS str_def,
               f.sapm AS sapm,
               round(total_distance, 3) AS distance
        """
        with self.driver.session() as session:
            result = session.run(query, fighter_name=fighter_name, limit=limit)
            return [dict(record) for record in result]

    def weight_class_dominance(self, weight_class=None):
        """
        Analyze win rates within a weight class.
        """
        query = """
        MATCH (f:Fighter)-[r:FOUGHT]->(fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
        WHERE wc.name = $weight_class OR $weight_class IS NULL
        WITH f, wc,
             count(r) AS total_fights,
             count(CASE WHEN r.result = "win" THEN 1 END) AS wins
        WITH f, wc, total_fights, wins,
             CASE WHEN total_fights > 0 THEN toFloat(wins) / toFloat(total_fights) * 100 ELSE 0 END AS win_pct
        WHERE total_fights >= 3
        RETURN f.name AS fighter,
               f.nickname AS nickname,
               wc.name AS weight_class,
               wins,
               total_fights,
               round(win_pct, 1) AS win_percentage
        ORDER BY win_pct DESC, wins DESC
        LIMIT 50
        """
        with self.driver.session() as session:
            result = session.run(query, weight_class=weight_class)
            return [dict(record) for record in result]

    def geographic_event_analysis(self):
        """
        Analyze which locations host the most events and which weight classes fight there.
        """
        query = """
        MATCH (e:Event)-[:HELD_AT]->(loc:Location)
        OPTIONAL MATCH (fight:Fight)-[:PART_OF]->(e)
        OPTIONAL MATCH (fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
        RETURN loc.name AS location,
               count(DISTINCT e) AS events,
               count(DISTINCT fight) AS total_fights,
               count(DISTINCT wc) AS weight_classes_represented
        ORDER BY events DESC
        LIMIT 20
        """
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record) for record in result]


def print_results(title, results):
    """Pretty-print query results."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    if not results:
        print("  No results found.")
        return
    for i, row in enumerate(results):
        print(f"\n  [{i+1}] ", end="")
        for k, v in row.items():
            print(f"{k}: {v}  ", end="")
        print()


if __name__ == "__main__":
    analytics = UfcAnalytics("bolt://localhost:7687", "neo4j", "password")

    try:
        # Task 14: Centrality
        print_results("TOP 10 FIGHTERS BY DEGREE CENTRALITY",
                      analytics.fighter_degree_centrality(10))

        print_results("TOP 5 EVENTS BY FIGHTER INVOLVEMENT",
                      analytics.fight_betweenness_centrality(5))

        print_results("TOP 5 KNOCKOUT KINGS",
                      analytics.knockout_kings(5))

        # Task 15: Win/Loss Network
        print_results("KNOCKOUT SPECIALISTS",
                      analytics.knockout_kings(10))

        print_results("SUBMISSION SPECIALISTS",
                      analytics.submission_specialists(10))

        # Task 16: Fighter Similarity
        print_results("SIMILAR STRIKERS TO LEON EDWARDS",
                      analytics.striking_style_similarity("Leon Edwards", 5))

        # Export data for external clustering (e.g., Python sklearn)
        fighter_data = analytics.fighter_stats_for_clustering()
        print(f"\nExported {len(fighter_data)} fighters for clustering analysis.")

        print_results("WEIGHT CLASS DOMINANCE (Welterweight)",
                      analytics.weight_class_dominance("Welterweight"))

        print_results("GEOGRAPHIC EVENT ANALYSIS",
                      analytics.geographic_event_analysis())

    finally:
        analytics.close()
