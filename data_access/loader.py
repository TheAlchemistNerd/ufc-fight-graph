"""Idempotent graph writes. Sparse records never erase populated properties."""

from domain.normalization import iso_date, result, text, weight_class

DETAILS_VERSION = 1


def properties(data, keys):
    return {
        key: data[key]
        for key in keys
        if key in data
        and data[key] is not None
        and (not isinstance(data[key], str) or text(data[key]) is not None)
    }


class Neo4jLoader:
    def __init__(self, connection):
        self.db = connection

    def create_fighter(self, data):
        if not text(data.get("name")) or not text(data.get("url")):
            raise ValueError("Fighter name and source URL are required")
        props = properties(
            data,
            (
                "nickname",
                "record",
                "height",
                "weight",
                "reach",
                "stance",
                "dob",
                "slpm",
                "str_acc",
                "sapm",
                "str_def",
                "td_avg",
                "td_acc",
                "td_def",
                "sub_avg",
                "wins",
                "losses",
                "draws",
                "nc",
                "height_inches",
                "weight_lbs",
                "reach_inches",
            ),
        )
        self.db.run_write(
            """
            MERGE (f:Fighter {url: $url}) SET f.name = $name, f += $props, f.profile_updated_at = datetime()
        """,
            {"name": text(data["name"]), "url": data["url"], "props": props},
        )

    def create_event(self, data):
        if not text(data.get("name")):
            raise ValueError("Event name is required")
        props = properties({**data, "date": iso_date(data.get("date"))}, ("url", "date"))
        self.db.run_write(
            """
            MERGE (e:Event {name: $name}) SET e += $props
            FOREACH (location IN $locations |
                MERGE (loc:Location {name: location}) MERGE (e)-[:HELD_AT]->(loc))
        """,
            {
                "name": text(data["name"]),
                "props": props,
                "locations": [text(data["location"])] if text(data.get("location")) else [],
            },
        )

    def create_fight(self, data, *, enriched=False):
        fighters = data.get("fighters", [])
        if (
            not text(data.get("url"))
            or not text(data.get("event"))
            or len(fighters) != 2
            or not all(text(f) for f in fighters)
        ):
            raise ValueError("Fight URL, event and two distinct fighters are required")
        props = properties(
            {**data, "date": iso_date(data.get("date"))},
            (
                "date",
                "method",
                "round",
                "time",
                "time_format",
                "finish_details",
                "is_title_fight",
            ),
        )
        referee = text(data.get("referee"))
        if enriched:
            props.update(
                details_version=DETAILS_VERSION,
                referee_status="available" if referee else "unavailable",
            )
        urls = data.get("fighter_urls", [])
        if len(urls) != 2 or not all(text(u) for u in urls) or urls[0] == urls[1]:
            raise ValueError("Two distinct fighter source URLs are required")
        participants = []
        for i, name in enumerate(fighters):
            participants.append(
                {
                    "name": text(name),
                    "url": urls[i],
                    "result": properties(
                        {"result": result(data.get(f"f{i + 1}_result"))}, ("result",)
                    ),
                }
            )
        judges = [
            {"name": text(j.get("name")), "score": text(j.get("score"))}
            for j in data.get("judges", [])
            if text(j.get("name")) and text(j.get("score"))
        ]
        self.db.run_write(
            """
            MERGE (e:Event {name: $event}) SET e += $event_props
            MERGE (fight:Fight {url: $url}) SET fight += $props
            MERGE (fight)-[:PART_OF]->(e)
            FOREACH (p IN $participants |
                MERGE (fighter:Fighter {url: p.url}) SET fighter.name = p.name
                MERGE (fighter)-[r:FOUGHT]->(fight) SET r += p.result)
            FOREACH (wc IN $weight_classes |
                MERGE (division:WeightClass {name: wc})
                MERGE (fight)-[:IN_WEIGHT_CLASS]->(division))
            FOREACH (ref IN $referees |
                MERGE (official:Referee {name: ref})
                MERGE (fight)-[:OFFICIATED_BY]->(official)
                SET fight.referee = ref)
            FOREACH (j IN $judges |
                MERGE (judge:Judge {name: j.name})
                MERGE (fight)-[s:SCORED_BY]->(judge) SET s.score = j.score)
            FOREACH (checked IN $checked | SET fight.details_checked_at = datetime())
            WITH fight
            OPTIONAL MATCH (fight)-[old:OFFICIATED_BY]->(r:Referee)
            WHERE size($referees) > 0 AND r.name <> $referees[0]
            DELETE old
        """,
            {
                "url": data["url"],
                "event": text(data["event"]),
                "props": props,
                "event_props": properties(
                    {"url": data.get("event_url"), "date": iso_date(data.get("date"))},
                    ("url", "date"),
                ),
                "participants": participants,
                "referees": [referee] if referee else [],
                "weight_classes": [weight_class(data["weight_class"])]
                if text(data.get("weight_class"))
                else [],
                "judges": judges,
                "checked": [True] if enriched else [],
            },
        )

    def backfill_candidates(self, after="", limit=100, refresh=False):
        return self.db.run_query(
            """
            MATCH (fight:Fight)
            WHERE fight.url > $after AND (
                $refresh OR coalesce(fight.details_version, 0) < $version OR
                (NOT EXISTS { MATCH (fight)-[:OFFICIATED_BY]->(:Referee) }
                 AND coalesce(fight.referee_status, '') <> 'unavailable'))
            OPTIONAL MATCH (fight)-[:PART_OF]->(event:Event)
            WITH fight, head(collect(event.date)) AS event_date
            RETURN fight.url AS url, coalesce(fight.date, event_date) AS date
            ORDER BY url LIMIT $limit
        """,
            {"after": after, "limit": limit, "version": DETAILS_VERSION, "refresh": refresh},
        )

    def repair_local_metadata(self):
        """Normalize legacy dates and reconnect stored referee names without HTTP."""
        updates = 0
        for label, key, field in (
            ("Event", "name", "date"),
            ("Fight", "url", "date"),
            ("Fighter", "url", "dob"),
        ):
            rows = self.db.run_query(
                f"MATCH (n:{label}) WHERE n.{field} IS NOT NULL RETURN n.{key} AS key, n.{field} AS value"
            )
            values = [
                {"key": row["key"], "value": iso_date(row["value"])}
                for row in rows
                if iso_date(row["value"]) and iso_date(row["value"]) != row["value"]
            ]
            if values:
                self.db.run_write(
                    f"UNWIND $rows AS row MATCH (n:{label} {{{key}: row.key}}) SET n.{field} = row.value",
                    {"rows": values},
                )
                updates += len(values)
        self.db.run_write("""
            MATCH (fight:Fight)-[:PART_OF]->(e:Event)
            WHERE (fight.date IS NULL OR trim(fight.date) = '') AND e.date IS NOT NULL
            SET fight.date = e.date
        """)
        rows = self.db.run_query(
            "MATCH (fight:Fight) WHERE fight.referee IS NOT NULL RETURN fight.url AS url, fight.referee AS referee"
        )
        refs = [
            {"url": row["url"], "referee": text(row["referee"])}
            for row in rows
            if text(row["referee"])
        ]
        if refs:
            self.db.run_write(
                """
                UNWIND $rows AS row MATCH (fight:Fight {url: row.url})
                WHERE NOT EXISTS { MATCH (fight)-[:OFFICIATED_BY]->(:Referee) }
                MERGE (ref:Referee {name: row.referee}) MERGE (fight)-[:OFFICIATED_BY]->(ref)
            """,
                {"rows": refs},
            )
        return updates

    def coverage(self):
        return self.db.run_query(
            """
            MATCH (fight:Fight)
            RETURN count(fight) AS fights,
                   count(CASE WHEN EXISTS { MATCH (fight)-[:OFFICIATED_BY]->(:Referee) } THEN 1 END) AS with_referee,
                   count(CASE WHEN fight.referee_status = 'unavailable' THEN 1 END) AS unavailable_at_source,
                   count(CASE WHEN coalesce(fight.details_version, 0) >= $version THEN 1 END) AS checked
        """,
            {"version": DETAILS_VERSION},
        )[0]
