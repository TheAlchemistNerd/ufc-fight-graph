"""Real Cypher and dashboard tests against an explicitly selected, empty database.

Set TEST_NEO4J_URI, TEST_NEO4J_USER and TEST_NEO4J_PASS to a disposable instance.
Fixtures refuse a populated database and delete only their own prefixed records.
"""

import inspect
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pandas as pd
import pytest
from bs4 import BeautifulSoup
from streamlit.testing.v1 import AppTest

from config.settings import Neo4jConfig
from data_access.loader import Neo4jLoader
from data_access.repositories import (
    CareerRepo,
    ChampionshipRepo,
    ExplorerRepo,
    FighterRepo,
    FightPaceRepo,
    GeographyRepo,
    JudgeRepo,
    NetworkCentralityRepo,
    NetworkRepo,
    RefereeRepo,
    StrikingRepo,
)
from domain.normalization import normalize_fighter
from infrastructure.neo4j_client import Neo4jConnection
from infrastructure.ufcstats import UfcStatsScraper
from web.app import NAVIGATION, PAGES, get_repos

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def graph():
    uri = os.getenv("TEST_NEO4J_URI")
    if not uri:
        pytest.skip("TEST_NEO4J_URI is required for disposable-database integration tests")
    config = Neo4jConfig(
        uri=uri,
        user=os.getenv("TEST_NEO4J_USER", "neo4j"),
        password=os.getenv("TEST_NEO4J_PASS", "password"),
        database=os.getenv("TEST_NEO4J_DATABASE", "neo4j"),
    )
    prefix = "ufc-test-" + uuid4().hex + "-"

    def name(value):
        return prefix + value

    def url(value):
        return name("fighter-" + value)

    with Neo4jConnection(config) as db:
        count = db.run_query("MATCH (n) RETURN count(n) AS count")[0]["count"]
        if count:
            pytest.fail("Integration tests require an EMPTY disposable Neo4j database")
        loader = Neo4jLoader(db)
        try:
            for i, fighter in enumerate("ABCDEFG"):
                loader.create_fighter(
                    normalize_fighter(
                        {
                            "url": url(fighter),
                            "name": name(fighter),
                            "nickname": fighter,
                            "record": "0-8-0" if fighter == "B" else "8-2-0",
                            "height": "6' 0\"",
                            "reach": f'{70 + i}"',
                            "weight": "170 lbs.",
                            "stance": "Southpaw" if i % 2 else "Orthodox",
                            "dob": "Jan 01, 1990",
                            "slpm": "4.0",
                            "sapm": "2.0",
                            "str_acc": "50%",
                        }
                    )
                )
            event = {"name": name("Event"), "date": "2024-01-01", "location": name("Location")}
            loader.create_event(event)
            bouts = [
                ("A", "B", "win", "loss", "KO/TKO", "1", "1:30"),
                ("A", "B", "loss", "win", "SUB", "2", "1:00"),
                ("A", "C", "win", "loss", "U-DEC", "3", "5:00"),
                ("A", "D", "win", "loss", "KO/TKO", "2", "1:00"),
                ("A", "E", "win", "loss", "SUB", "1", "2:00"),
                ("A", "F", "loss", "win", "U-DEC", "3", "5:00"),
                ("B", "C", "loss", "win", "U-DEC", "3", "5:00"),
                ("C", "G", "win", "loss", "KO/TKO", "1", "1:00"),
                ("D", "E", "draw", "draw", "M-DEC", "3", "5:00"),
                ("E", "F", "nc", "nc", "Overturned", "1", "2:00"),
            ]
            fights = []
            for i, (a, b, result_a, result_b, method, round_, time) in enumerate(bouts):
                fight = {
                    "url": name(f"fight-{i}"),
                    "event": name("Event"),
                    "date": f"2024-01-{i + 1:02}",
                    "fighters": [name(a), name(b)],
                    "fighter_urls": [url(a), url(b)],
                    "f1_result": result_a,
                    "f2_result": result_b,
                    "method": method,
                    "round": round_,
                    "time": time,
                    "weight_class": name("Welterweight"),
                    "time_format": "1 Rnd + OT (12-3)" if i == 3 else "3 Rnd (5-5-5)",
                    "referee": name("Referee"),
                    "is_title_fight": i == 2,
                    "judges": [
                        {"name": name(f"Judge {j}"), "score": score}
                        for j, score in enumerate(["30 - 25", "30 - 27", "30 - 27"])
                    ]
                    if method.endswith("DEC")
                    else [],
                }
                loader.create_fight(fight, enriched=True)
                fights.append(fight)
            yield SimpleNamespace(
                db=db, config=config, loader=loader, name=name, url=url, fights=fights
            )
        finally:
            # Both identity fields are scoped to this run; unrelated records remain intact.
            db.run_write(
                "MATCH (n) WHERE n.name STARTS WITH $prefix OR n.url STARTS WITH $prefix "
                "DETACH DELETE n",
                {"prefix": prefix},
            )


def test_every_repository_query_executes_on_neo4j(graph):
    arguments = {
        "name": graph.name("A"),
        "fighter_name": graph.name("A"),
        "f1_name": graph.name("A"),
        "f2_name": graph.name("G"),
    }
    failures = []
    for repo in get_repos(graph.db).values():
        for method_name, method in inspect.getmembers(repo, inspect.ismethod):
            if not method_name.startswith("get_"):
                continue
            kwargs = {
                name: arguments[name]
                for name, parameter in inspect.signature(method).parameters.items()
                if parameter.default is inspect.Parameter.empty
            }
            try:
                result = method(**kwargs)
                assert isinstance(result, (pd.DataFrame, list, dict))
            except Exception as exc:
                failures.append(f"{type(repo).__name__}.{method_name}: {exc}")
    assert not failures, "\n".join(failures)


def test_network_metrics_count_rematches_and_neighbors_correctly(graph):
    repo = NetworkCentralityRepo(graph.db)
    fighter = graph.name("A")
    degree = repo.get_degree_centrality().set_index("fighter").loc[fighter]
    assert degree["total_fights"] == 6
    assert degree["unique_opponents"] == 5
    assert degree["win_pct"] == 66.7
    influence = repo.get_eigenvector_centrality().set_index("fighter").loc[fighter]
    assert influence["direct_opponents"] == 5
    assert influence["second_degree_reach"] == 6
    bridges = repo.get_betweenness_centrality().set_index("fighter").loc[fighter]
    assert bridges["bridge_connections"] == 5
    assert bridges["unique_bridges"] == 7
    density = repo.get_network_density_by_weight_class().iloc[0]
    assert density["actual_fights"] == 10
    assert density["density_pct"] == 42.86  # Nine unique pairs among seven fighters.
    distances = repo.get_path_length_sample(fighter).set_index("fighter")
    assert distances.loc[graph.name("G"), "degrees_of_separation"] == 2
    assert fighter not in distances.index


def test_result_direction_rebounds_and_fight_counts(graph):
    network = NetworkRepo(graph.db)
    transitive = network.get_transitive_wins(graph.name("B"))
    assert set(map(tuple, transitive[["fighter", "via"]].values)) == {
        (graph.name("F"), graph.name("A")),
        (graph.name("A"), graph.name("C")),
    }
    assert network.get_common_opponents(graph.name("A"), graph.name("G"))["opponent"].tolist() == [
        graph.name("C")
    ]
    rebound = CareerRepo(graph.db).get_post_loss_rebound().set_index("fighter").loc[graph.name("A")]
    assert rebound["fights_after_loss"] == 1
    assert rebound["rebound_pct"] == 100
    assert GeographyRepo(graph.db).get_fight_outcomes_by_location()["count"].sum() == 10
    assert StrikingRepo(graph.db).get_striking_efficiency()["strike_ratio"].tolist() == [2.0] * 7
    duration = FightPaceRepo(graph.db).get_duration_by_weight_class().iloc[0]
    assert duration["avg_duration_sec"] == 513  # Includes the 12-minute opening round.
    coverage = RefereeRepo(graph.db).get_coverage()
    assert coverage == {"fights": 10, "with_referee": 10, "unavailable_at_source": 0, "checked": 10}
    rates = RefereeRepo(graph.db).get_referee_finish_rates().iloc[0]
    assert (rates["total_fights"], rates["ko_pct"], rates["sub_pct"], rates["decision_pct"]) == (
        10,
        30,
        20,
        40,
    )


def test_scorecards_and_title_rates_use_actual_recorded_results(graph):
    judges = JudgeRepo(graph.db)
    assert judges.get_judge_widest_margins().iloc[0]["margin"] == 5
    assert judges.get_wide_scorecards().to_dict("records") == [
        {"judge": graph.name("Judge 0"), "wide_margins": 4},
    ]
    agreement = judges.get_judge_consistency_analysis()
    assert dict(zip(agreement["judge"], agreement["agreements"])) == {
        graph.name("Judge 1"): 4,
        graph.name("Judge 2"): 4,
    }
    title = ChampionshipRepo(graph.db).get_title_vs_regular_finish_rates().iloc[0]
    assert title["title_fights"] == 1
    assert title["title_finish_pct"] == 0
    assert title["overall_finish_pct"] == 50


def test_loader_replays_sparse_rows_without_losing_details(graph):
    before = graph.db.run_query("MATCH (n) RETURN count(n) AS count")[0]["count"]
    fight = graph.fights[0]
    graph.loader.create_fight(fight, enriched=True)
    graph.loader.create_fight(
        {key: fight[key] for key in ("url", "event", "fighters", "fighter_urls")}
    )
    graph.loader.create_fighter(
        {"url": graph.url("A"), "name": graph.name("A"), "slpm": None, "reach": "--"}
    )
    row = graph.db.run_query(
        """
        MATCH (f:Fighter {name: $name})-[r:FOUGHT]->(fight:Fight {url: $url})
        MATCH (fight)-[:OFFICIATED_BY]->(ref:Referee)
        RETURN f.slpm AS slpm, f.reach AS reach, r.result AS result,
               fight.date AS date, ref.name AS referee
    """,
        {"name": graph.name("A"), "url": fight["url"]},
    )[0]
    assert row == {
        "slpm": 4.0,
        "reach": '70"',
        "result": "win",
        "date": "2024-01-01",
        "referee": graph.name("Referee"),
    }
    assert graph.db.run_query("MATCH (n) RETURN count(n) AS count")[0]["count"] == before


def test_leaf_opponents_are_included_in_direct_reach(graph):
    fight = {
        "url": graph.name("leaf-fight"),
        "event": graph.name("Event"),
        "fighters": [graph.name("A"), graph.name("Leaf")],
        "fighter_urls": [graph.url("A"), graph.url("Leaf")],
        "f1_result": "win",
        "f2_result": "loss",
    }
    graph.loader.create_fight(fight)
    try:
        row = (
            NetworkCentralityRepo(graph.db)
            .get_eigenvector_centrality()
            .set_index("fighter")
            .loc[graph.name("A")]
        )
        assert row["direct_opponents"] == 6
        assert row["second_degree_reach"] == 6
    finally:
        graph.db.run_write(
            "MATCH (n) WHERE n.url = $url OR n.name = $name DETACH DELETE n",
            {"url": fight["url"], "name": graph.name("Leaf")},
        )


def test_referee_backfill_distinguishes_missing_data_and_replaces_corrections(graph):
    fight = {
        "url": graph.name("backfill-fight"),
        "event": graph.name("Event"),
        "fighters": [graph.name("A"), graph.name("B")],
        "fighter_urls": [graph.url("A"), graph.url("B")],
        "referee": None,
    }
    graph.loader.create_fight(fight)
    try:
        assert fight["url"] in {row["url"] for row in graph.loader.backfill_candidates()}
        graph.loader.create_fight(fight, enriched=True)
        assert fight["url"] not in {row["url"] for row in graph.loader.backfill_candidates()}
        assert fight["url"] in {
            row["url"] for row in graph.loader.backfill_candidates(refresh=True)
        }
        graph.loader.create_fight(
            {**fight, "referee": graph.name("Incorrect referee")}, enriched=True
        )
        graph.loader.create_fight(
            {**fight, "referee": graph.name("Correct referee")}, enriched=True
        )
        refs = graph.db.run_query(
            "MATCH (:Fight {url: $url})-[:OFFICIATED_BY]->(r:Referee) RETURN r.name AS name",
            {"url": fight["url"]},
        )
        assert refs == [{"name": graph.name("Correct referee")}]
    finally:
        graph.db.run_write(
            "MATCH (n) WHERE n.url = $url OR n.name IN $names DETACH DELETE n",
            {
                "url": fight["url"],
                "names": [graph.name("Incorrect referee"), graph.name("Correct referee")],
            },
        )


def test_same_name_fighters_keep_distinct_profiles_and_network_edges(graph):
    duplicate_name = graph.name("Bruno Silva")
    first, second = graph.url("Bruno-1"), graph.url("Bruno-2")
    fight_url = graph.name("same-name-fight")
    for url, nickname in [(first, "First"), (second, "Second")]:
        graph.loader.create_fighter({"url": url, "name": duplicate_name, "nickname": nickname})
    try:
        graph.loader.create_fight(
            {
                "url": fight_url,
                "event": graph.name("Event"),
                "fighters": [duplicate_name, duplicate_name],
                "fighter_urls": [first, second],
                "f1_result": "win",
                "f2_result": "loss",
            }
        )
        repo = FighterRepo(graph.db)
        assert repo.get_fighter_profile(first)["nickname"].tolist() == ["First"]
        assert repo.get_fighter_profile(second)["nickname"].tolist() == ["Second"]
        assert repo.get_fighter_history(first)["result"].tolist() == ["win"]
        assert repo.get_fighter_history(second)["result"].tolist() == ["loss"]
        degree = NetworkCentralityRepo(graph.db).get_degree_centrality()
        same_name = degree[degree["fighter"] == duplicate_name]
        assert same_name["total_fights"].tolist() == [1, 1]
        edges = NetworkRepo(graph.db).get_network_sample()
        assert len(edges[(edges["f1"] == duplicate_name) & (edges["f2"] == duplicate_name)]) == 1
    finally:
        graph.db.run_write(
            "MATCH (n) WHERE n.url IN $urls DETACH DELETE n", {"urls": [first, second, fight_url]}
        )


def test_parser_and_loader_share_referee_and_outcome_semantics(graph):
    html = Path(__file__).with_name("fixtures").joinpath("fight.html").read_text(encoding="utf-8")
    with (
        UfcStatsScraper(delay=0) as scraper,
        patch.object(scraper, "_get_soup", return_value=BeautifulSoup(html, "lxml")),
    ):
        fight = scraper.scrape_fight_details(
            "http://ufcstats.com/fight-details/test", event_date="2025-11-15"
        )
    assert fight["referee"] == "Keith Peterson"
    assert [fight["f1_result"], fight["f2_result"]] == ["loss", "win"]
    # Every graph identity uses the fixture prefix, including source-derived names.
    fight.update(
        url=graph.name("parsed-fight"),
        event=graph.name("Parsed event"),
        fighters=[graph.name(name) for name in fight["fighters"]],
        referee=graph.name(fight["referee"]),
        weight_class=graph.name(fight["weight_class"]),
    )
    graph.loader.create_fight(fight, enriched=True)
    try:
        rows = graph.db.run_query(
            """
            MATCH (f:Fighter)-[r:FOUGHT]->(fight:Fight {url: $url})-[:OFFICIATED_BY]->(ref:Referee)
            RETURN f.name AS fighter, r.result AS result, ref.name AS referee
        """,
            {"url": fight["url"]},
        )
        assert {(row["fighter"], row["result"]) for row in rows} == set(
            zip(fight["fighters"], ["loss", "win"])
        )
        assert {row["referee"] for row in rows} == {graph.name("Keith Peterson")}
    finally:
        # Remove this subfixture immediately so page/ranking expectations stay independent.
        graph.db.run_write(
            "MATCH (n) WHERE n.url = $url OR n.name IN $names DETACH DELETE n",
            {"url": fight["url"], "names": [*fight["fighters"], fight["event"], fight["referee"]]},
        )


@pytest.mark.parametrize("page", list(PAGES))
def test_every_dashboard_page_renders_against_real_data(graph, monkeypatch, page):
    monkeypatch.setattr("web.app.get_connection", lambda: graph.db)
    app = AppTest.from_string("from web.app import main\nmain()", default_timeout=30)
    app.run()
    section = next(section for section, pages in NAVIGATION.items() if page in pages)
    app.sidebar.selectbox[0].set_value(section).run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception
    assert not app.error
    assert app.title


def test_archive_has_one_row_per_fight_with_multiple_divisions_and_scorecards(graph):
    extra = graph.name("Alternative division")
    graph.db.run_write(
        "MATCH (f:Fight {url: $url}) MERGE (w:WeightClass {name: $name}) "
        "MERGE (f)-[:IN_WEIGHT_CLASS]->(w)",
        {"url": graph.fights[2]["url"], "name": extra},
    )
    try:
        fights = ExplorerRepo(graph.db).get_fights()
        assert len(fights) == fights.fight_url.nunique() == 10
        row = fights.set_index("fight_url").loc[graph.fights[2]["url"]]
        assert len(row["divisions"]) == 2
        assert len(row["fighters"]) == 2
        assert len(row["judges"]) == 3
        assert {f["result"] for f in row["fighters"]} == {"win", "loss"}
    finally:
        graph.db.run_write("MATCH (w:WeightClass {name: $name}) DETACH DELETE w", {"name": extra})


def test_archive_filters_clear_and_title_bouts(graph, monkeypatch):
    monkeypatch.setattr("web.app.get_connection", lambda: graph.db)
    app = AppTest.from_string("from web.app import main\nmain()", default_timeout=30).run()
    app.sidebar.radio[0].set_value("Fight archive").run()
    app.text_input[0].set_value("no-such-matchup-123").run()
    assert any("0 matching fights" in item.value for item in app.subheader)
    next(button for button in app.button if button.label == "Clear filters").click().run()
    assert any("10 matching fights" in item.value for item in app.subheader)
    app.checkbox[0].check().run()
    assert any("1 matching fights" in item.value for item in app.subheader)
    assert not app.exception and not app.error
