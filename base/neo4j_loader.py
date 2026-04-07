"""
Neo4j Loader for full UFC Stats data.
Supports: Fighter, Fight, Event, WeightClass, Referee, Location nodes.
"""

from neo4j import GraphDatabase
import logging

class Neo4jLoader:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def close(self):
        self.driver.close()

    def setup_schema(self):
        """Create constraints and indexes for all node types."""
        constraints = [
            "CREATE CONSTRAINT fighter_name IF NOT EXISTS FOR (f:Fighter) REQUIRE f.name IS UNIQUE",
            "CREATE CONSTRAINT event_name IF NOT EXISTS FOR (e:Event) REQUIRE e.name IS UNIQUE",
            "CREATE CONSTRAINT fight_url IF NOT EXISTS FOR (f:Fight) REQUIRE f.url IS UNIQUE",
            "CREATE CONSTRAINT weightclass_name IF NOT EXISTS FOR (w:WeightClass) REQUIRE w.name IS UNIQUE",
            "CREATE CONSTRAINT referee_name IF NOT EXISTS FOR (r:Referee) REQUIRE r.name IS UNIQUE",
            "CREATE CONSTRAINT location_name IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE",
        ]
        with self.driver.session() as session:
            for constraint in constraints:
                session.run(constraint)
        self.logger.info("Schema constraints created.")

    # ===================== FIGHTER =====================

    def create_fighter(self, fighter_data):
        """Create or update a Fighter node with all normalized stats."""
        with self.driver.session() as session:
            session.execute_write(self._create_fighter_node, fighter_data)

    @staticmethod
    def _create_fighter_node(tx, data):
        query = (
            "MERGE (f:Fighter {name: $name}) "
            "SET f.nickname = $nickname, "
            "    f.record = $record, "
            "    f.height = $height, "
            "    f.weight = $weight, "
            "    f.reach = $reach, "
            "    f.stance = $stance, "
            "    f.dob = $dob, "
            "    f.slpm = $slpm, "
            "    f.str_acc = $str_acc, "
            "    f.sapm = $sapm, "
            "    f.str_def = $str_def, "
            "    f.td_avg = $td_avg, "
            "    f.td_acc = $td_acc, "
            "    f.td_def = $td_def, "
            "    f.sub_avg = $sub_avg, "
            "    f.wins = $wins, "
            "    f.losses = $losses, "
            "    f.draws = $draws, "
            "    f.nc = $nc, "
            "    f.height_inches = $height_inches, "
            "    f.weight_lbs = $weight_lbs, "
            "    f.reach_inches = $reach_inches"
        )
        tx.run(query,
               name=data.get('name'),
               nickname=data.get('nickname'),
               record=data.get('record'),
               height=data.get('height'),
               weight=data.get('weight'),
               reach=data.get('reach'),
               stance=data.get('stance'),
               dob=data.get('dob'),
               slpm=data.get('slpm'),
               str_acc=data.get('str_acc'),
               sapm=data.get('sapm'),
               str_def=data.get('str_def'),
               td_avg=data.get('td_avg'),
               td_acc=data.get('td_acc'),
               td_def=data.get('td_def'),
               sub_avg=data.get('sub_avg'),
               wins=data.get('wins'),
               losses=data.get('losses'),
               draws=data.get('draws'),
               nc=data.get('nc'),
               height_inches=data.get('height_inches'),
               weight_lbs=data.get('weight_lbs'),
               reach_inches=data.get('reach_inches'))

    # ===================== EVENT =====================

    def create_event(self, event_data):
        """Create an Event node with location relationship."""
        with self.driver.session() as session:
            session.execute_write(self._create_event_node, event_data)

    @staticmethod
    def _create_event_node(tx, data):
        query = (
            "MERGE (e:Event {name: $name}) "
            "SET e.url = $url, "
            "    e.date = $date "
            "WITH e "
            "MERGE (loc:Location {name: $location}) "
            "MERGE (e)-[:HELD_AT]->(loc)"
        )
        tx.run(query,
               name=data.get('name'),
               url=data.get('url'),
               date=data.get('date'),
               location=data.get('location', 'Unknown'))

    # ===================== FIGHT =====================

    def create_fight(self, fight_details):
        """Create a Fight node with all relationships: Event, Referee, WeightClass, Fighters."""
        with self.driver.session() as session:
            session.execute_write(self._create_fight_node, fight_details)

    @staticmethod
    def _create_fight_node(tx, data):
        fighters = data.get('fighters', [])
        f1_name = fighters[0] if len(fighters) > 0 else "Unknown"
        f2_name = fighters[1] if len(fighters) > 1 else "Unknown"

        query_parts = [
            "MERGE (e:Event {name: $event_name}) ",
            "MERGE (f1:Fighter {name: $f1_name}) ",
            "MERGE (f2:Fighter {name: $f2_name}) ",
            "MERGE (fight:Fight {url: $fight_url}) ",
            "SET fight.date = $date, ",
            "    fight.method = $method, ",
            "    fight.round = $round, ",
            "    fight.time = $time, ",
            "    fight.finish_details = $finish_details, ",
            "    fight.time_format = $time_format ",
            "MERGE (fight)-[:PART_OF]->(e) ",
            "MERGE (f1)-[r1:FOUGHT]->(fight) ",
            "SET r1.result = $f1_result ",
            "MERGE (f2)-[r2:FOUGHT]->(fight) ",
            "SET r2.result = $f2_result ",
        ]

        if data.get('weight_class'):
            query_parts.append("MERGE (wc:WeightClass {name: $weight_class}) ")
            query_parts.append("MERGE (fight)-[:IN_WEIGHT_CLASS]->(wc) ")

        if data.get('referee'):
            query_parts.append("MERGE (ref:Referee {name: $referee}) ")
            query_parts.append("MERGE (fight)-[:OFFICIATED_BY]->(ref) ")

        query = "".join(query_parts)

        tx.run(query,
               event_name=data.get('event'),
               f1_name=f1_name,
               f2_name=f2_name,
               fight_url=data.get('url'),
               date=data.get('date'),
               method=data.get('method'),
               round=data.get('round'),
               time=data.get('time'),
               finish_details=data.get('finish_details'),
               time_format=data.get('time_format'),
               f1_result=data.get('f1_result'),
               f2_result=data.get('f2_result'),
               weight_class=data.get('weight_class'),
               referee=data.get('referee'))

    def create_fight_from_event(self, fighter_name, fight_data, event_name):
        """Create a fight relationship from event data (simpler, no full fight details)."""
        with self.driver.session() as session:
            session.execute_write(self._create_fight_from_event, fighter_name, fight_data, event_name)

    @staticmethod
    def _create_fight_from_event(tx, fighter_name, fight_data, event_name):
        opponent = fight_data['fighter2'] if fight_data.get('fighter1') == fighter_name else fight_data.get('fighter1', 'Unknown')
        result = fight_data.get('result', '')

        query = (
            "MERGE (e:Event {name: $event_name}) "
            "MERGE (f1:Fighter {name: $fighter_name}) "
            "MERGE (f2:Fighter {name: $opponent}) "
            "MERGE (wc:WeightClass {name: $weight_class}) "
            "MERGE (fight:Fight {url: $fight_url}) "
            "SET fight.date = $date, "
            "    fight.method = $method, "
            "    fight.round = $round, "
            "    fight.time = $time "
            "MERGE (fight)-[:PART_OF]->(e) "
            "MERGE (fight)-[:IN_WEIGHT_CLASS]->(wc) "
            "MERGE (f1)-[r1:FOUGHT]->(fight) "
            "SET r1.result = $result "
            "MERGE (f2)-[r2:FOUGHT]->(fight) "
        )
        tx.run(query,
               event_name=event_name,
               fighter_name=fighter_name,
               opponent=opponent,
               weight_class=fight_data.get('weight_class', 'Unknown'),
               fight_url=fight_data.get('url', ''),
               date=None,
               method=fight_data.get('method'),
               round=fight_data.get('round'),
               time=fight_data.get('time'),
               result=result)


if __name__ == "__main__":
    loader = Neo4jLoader("bolt://localhost:7687", "neo4j", "password")
    loader.setup_schema()
    loader.close()
    print("Neo4j schema set up successfully.")
