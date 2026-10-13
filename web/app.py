# ruff: noqa: E402 -- Streamlit needs the project root before local imports.
"""
Streamlit dashboard for the UFC graph.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

# Ensure project root is in sys.path for Streamlit execution
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st

from config.settings import load_config
from data_access.repositories import (
    CareerRepo,
    ChampionshipRepo,
    EvolutionRepo,
    ExplorerRepo,
    FighterRepo,
    FightPaceRepo,
    FinishRepo,
    GeographyRepo,
    JudgeRepo,
    NetworkCentralityRepo,
    NetworkRepo,
    OverviewRepo,
    RefereeRepo,
    StrikingRepo,
    StyleMatchupRepo,
    WeightClassRepo,
)
from infrastructure.neo4j_client import Neo4jConnection
from web.charts import (
    event_map,
    horizontal_bar,
    line_chart,
    scatter_chart,
    vertical_bar,
)
from web.explorer import (
    cached_fights,
    choices_for,
    page_comparison,
    page_fight_archive,
    page_fighter_explorer,
    page_judge_analysis,
    page_overview,
    page_referee_analysis,
    source_columns,
)
from web.geography import country_totals, prepare_locations


@st.cache_resource
def get_connection() -> Neo4jConnection:
    return Neo4jConnection(load_config())


def get_repos(_conn: Neo4jConnection) -> dict:
    return {
        "overview": OverviewRepo(_conn),
        "explorer": ExplorerRepo(_conn),
        "fighter": FighterRepo(_conn),
        "referee": RefereeRepo(_conn),
        "striking": StrikingRepo(_conn),
        "geography": GeographyRepo(_conn),
        "weight_class": WeightClassRepo(_conn),
        "career": CareerRepo(_conn),
        "evolution": EvolutionRepo(_conn),
        "pace": FightPaceRepo(_conn),
        "style": StyleMatchupRepo(_conn),
        "finish": FinishRepo(_conn),
        "championship": ChampionshipRepo(_conn),
        "centrality": NetworkCentralityRepo(_conn),
        "network": NetworkRepo(_conn),
        "judge": JudgeRepo(_conn),
    }


def metric_value(value, suffix=""):
    """Display zero as a value and missing numeric data as N/A."""
    return f"{value}{suffix}" if pd.notna(value) else "N/A"


def fighter_choices(repo):
    return choices_for({"fighter": repo})


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            '<div class="brand"><span>UFC</span> / FIGHT GRAPH</div>', unsafe_allow_html=True
        )
        st.caption("The fight archive, connected.")
        st.divider()
        section = st.selectbox("Collection", list(NAVIGATION), key="nav_section")
        page = st.radio("Navigate", NAVIGATION[section], key="nav_page")
        st.divider()
        conn = get_connection()
        ok, count = conn.test_connection()
        if ok:
            st.caption(f"● Connected · {count:,} graph records")
        else:
            st.error("The database is currently unavailable. Start Neo4j and refresh.")
            st.stop()
        st.button("Refresh data", on_click=cached_fights.clear, width="stretch")
        st.caption("Source: UFCStats · Career averages and recorded fight results.")
        return page


def page_finish_specialists(repos: dict):
    st.title("Finish Specialists")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Knockout Kings")
        df = repos["finish"].get_ko_kings()
        if not df.empty:
            st.plotly_chart(
                horizontal_bar(df, "ko_wins", "name", "ko_wins", color_scale="Reds"),
                width="stretch",
            )
    with col2:
        st.subheader("Submission Specialists")
        df = repos["finish"].get_sub_specialists()
        if not df.empty:
            st.plotly_chart(
                horizontal_bar(df, "sub_wins", "name", "sub_wins", color_scale="Purples"),
                width="stretch",
            )

    st.subheader("Career Win Percentages (Most Active)")
    df = repos["career"].get_career_lengths()
    if not df.empty:
        st.plotly_chart(
            scatter_chart(
                df,
                "total_fights",
                "win_pct",
                size_col="wins",
                color_col="win_pct",
                hover_data=["fighter", "nickname"],
                color_scale="RdYlGn",
            ),
            width="stretch",
        )
        st.dataframe(df, width="stretch", hide_index=True)


def page_striking_efficiency(repos: dict):
    st.title("Striking Efficiency")

    st.subheader("Best Strikers by SLpM/SApM Ratio (Min 2.0 SLpM)")
    df = repos["striking"].get_striking_efficiency()
    if not df.empty:
        st.plotly_chart(
            scatter_chart(
                df,
                "sapm",
                "slpm",
                size_col="strike_ratio",
                color_col="strike_ratio",
                hover_data=["fighter", "nickname"],
                color_scale="RdYlGn",
                x_label="SApM (Absorbed)",
                y_label="SLpM (Landed)",
            ),
            width="stretch",
        )
        st.dataframe(df, width="stretch", hide_index=True)

    st.subheader("Reach Advantage Impact on Win Rate")
    df = repos["striking"].get_reach_advantage()
    if not df.empty:
        st.plotly_chart(
            line_chart(
                df,
                "reach_advantage_inches",
                "longer_reach_win_pct",
                x_label="Reach Advantage (inches)",
                y_label="Longer Reach Win %",
            ),
            width="stretch",
        )
        st.dataframe(df, width="stretch", hide_index=True)


def page_weight_classes(repos: dict):
    st.title("Weight Classes")

    wcs = repos["weight_class"].get_all_weight_classes()
    selected_wc = st.selectbox("Select Weight Class", ["All"] + sorted(wcs))
    wc_param = None if selected_wc == "All" else selected_wc

    df = repos["weight_class"].get_win_rates(weight_class=wc_param)
    if not df.empty:
        st.plotly_chart(
            scatter_chart(
                df,
                "total_fights",
                "win_percentage",
                size_col="wins",
                color_col="win_percentage",
                hover_data=["fighter", "nickname"],
                color_scale="RdYlGn",
            ),
            width="stretch",
        )
        st.dataframe(df, width="stretch", hide_index=True)

    st.subheader("Average Fight Duration by Weight Class")
    df = repos["pace"].get_duration_by_weight_class()
    if not df.empty:
        st.plotly_chart(
            vertical_bar(
                df,
                "weight_class",
                "avg_duration_min",
                "avg_duration_min",
                color_scale="Blues",
                height=400,
                x_label="Weight Class",
                y_label="Avg Duration (min)",
            ),
            width="stretch",
        )


def page_fight_pace(repos: dict):
    st.title("Fight Pace & Duration")

    st.subheader("Fight Finish Rate by Year")
    df = repos["pace"].get_finish_rate_by_year()
    if not df.empty:
        st.plotly_chart(
            line_chart(df, "year", "finish_pct", x_label="Year", y_label="Finish %"),
            width="stretch",
        )
        st.dataframe(df, width="stretch", hide_index=True)

    st.subheader("Fight Duration by Weight Class")
    df = repos["pace"].get_duration_by_weight_class()
    if not df.empty:
        st.plotly_chart(
            horizontal_bar(
                df, "avg_duration_min", "weight_class", "avg_duration_min", color_scale="Blues"
            ),
            width="stretch",
        )


def page_career(repos: dict):
    st.title("Career & Longevity")

    st.subheader("Most Active Fighters by Career Record")
    df = repos["career"].get_career_lengths()
    if not df.empty:
        st.plotly_chart(
            scatter_chart(
                df,
                "total_fights",
                "win_pct",
                size_col="wins",
                color_col="win_pct",
                hover_data=["fighter", "nickname"],
                color_scale="RdYlGn",
            ),
            width="stretch",
        )
        st.dataframe(df, width="stretch", hide_index=True)

    st.subheader("Wins by Fighters With More Career Losses Than Wins")
    df = repos["career"].get_underdog_analysis()
    if not df.empty:
        st.dataframe(df, width="stretch", hide_index=True)

    st.subheader("Post-Loss Rebound Rate")
    df = repos["career"].get_post_loss_rebound()
    if not df.empty:
        st.plotly_chart(
            horizontal_bar(
                df,
                "rebound_pct",
                "fighter",
                "rebound_pct",
                color_scale="Greens",
                height=400,
                x_label="Rebound Win %",
            ),
            width="stretch",
        )


def page_geographic(repos: dict):
    st.title("Geographic Insights")
    st.caption("Where the UFC has held events. Hover over a country or territory for its totals.")
    locations = repos["geography"].get_events_by_location()
    if locations.empty:
        st.info("The map will appear once events with locations are imported.")
        return
    locations = prepare_locations(locations)
    countries = country_totals(locations)
    for column, label, count in zip(
        st.columns(3),
        ["Events", "Host locations", "Mapped countries / territories"],
        [locations.events.sum(), len(locations), countries.iso3.notna().sum()],
    ):
        column.metric(label, f"{count:,}")
    metric = st.radio("Colour map by", ["Events", "Fights"], horizontal=True)
    st.plotly_chart(
        event_map(countries, "events" if metric == "Events" else "total_fights"),
        width="stretch",
        theme=None,
        config={"displaylogo": False, "scrollZoom": False},
    )
    unmapped = locations[locations.iso3.isna()]
    if not unmapped.empty:
        st.caption(
            f"{unmapped.events.sum():,} events have locations not mapped to a country code; "
            "they remain in the tables below."
        )
    country = st.selectbox("Explore a country / territory", ["All", *sorted(countries.country)])
    selected = locations if country == "All" else locations[locations.country == country]
    st.subheader("Host locations" if country == "All" else f"Host locations · {country}")
    st.plotly_chart(
        horizontal_bar(selected.head(15), "events", "location", "events", height=460),
        width="stretch",
        theme=None,
    )
    st.caption(
        f"Chart shows the top {min(15, len(selected))} locations. The table includes all matches."
    )
    st.dataframe(
        selected[["location", "country", "events", "total_fights"]].rename(
            columns={
                "location": "Location",
                "country": "Country / territory",
                "events": "Events",
                "total_fights": "Fights",
            }
        ),
        hide_index=True,
        width="stretch",
    )
    outcomes = repos["geography"].get_fight_outcomes_by_location()
    if not outcomes.empty:
        outcomes = outcomes[outcomes.location.isin(selected.location)]
        totals = (
            outcomes.groupby("result", as_index=False)["count"]
            .sum()
            .sort_values("count", ascending=False)
        )
        st.subheader("Fight methods" if country == "All" else f"Fight methods · {country}")
        st.plotly_chart(horizontal_bar(totals, "count", "result"), width="stretch", theme=None)


def page_style_matchups(repos: dict):
    st.title("Style Matchups")

    st.subheader("Stance Matchup Results")
    df = repos["style"].get_stance_matchups()
    if not df.empty:
        st.plotly_chart(
            scatter_chart(
                df,
                "winner_stance",
                "wins",
                color_col="loser_stance",
                hover_data=["winner_stance", "loser_stance"],
                color_scale="Set1",
            ),
            width="stretch",
        )
        st.dataframe(df, width="stretch", hide_index=True)


def page_network_centrality(repos: dict):
    st.title("Network Centrality")
    st.markdown(
        "Fighter influence metrics based on network position in the UFC matchmaking ecosystem."
    )

    st.subheader("Degree Centrality - Most Unique Opponents")
    df = repos["centrality"].get_degree_centrality()
    if not df.empty:
        st.plotly_chart(
            horizontal_bar(df, "unique_opponents", "fighter", "unique_opponents", height=500),
            width="stretch",
        )
        st.dataframe(df, width="stretch", hide_index=True)

    st.subheader("Opponent Influence Proxy - Direct and Two-Hop Reach")
    df = repos["centrality"].get_eigenvector_centrality()
    if not df.empty:
        st.plotly_chart(
            scatter_chart(
                df,
                "direct_opponents",
                "eigenvector_score",
                size_col="second_degree_reach",
                color_col="eigenvector_score",
                hover_data=["fighter", "nickname"],
                color_scale="Reds",
            ),
            width="stretch",
        )

    st.subheader("Win-Network Proxy - Defeated Opponents and Their Reach")
    df = repos["centrality"].get_pagerank_rankings()
    if not df.empty:
        st.plotly_chart(
            horizontal_bar(
                df, "pagerank_score", "fighter", "pagerank_score", color_scale="Greens", height=500
            ),
            width="stretch",
        )
        st.dataframe(df, width="stretch", hide_index=True)

    st.subheader("Bridge Proxy - Unconnected Opponent Pairs")
    df = repos["centrality"].get_betweenness_centrality()
    if not df.empty:
        st.dataframe(df, width="stretch", hide_index=True)

    st.subheader("Network Density by Weight Class")
    df = repos["centrality"].get_network_density_by_weight_class()
    if not df.empty:
        st.plotly_chart(
            vertical_bar(df, "weight_class", "density_pct", "density_pct", height=400),
            width="stretch",
        )

    st.subheader("Degrees of Separation")
    choices = fighter_choices(repos["fighter"])
    if choices:
        selected = st.selectbox("Starting fighter", list(choices), format_func=choices.get)
        df = repos["centrality"].get_path_length_sample(selected)
        if not df.empty:
            st.dataframe(df, width="stretch", hide_index=True)


def page_network(repos: dict):
    st.title("Network Analysis")

    st.subheader("Transitive Wins")
    st.caption("Fighters who beat someone who beat the selected fighter.")
    choices = fighter_choices(repos["fighter"])
    if not choices:
        st.info("No fighters loaded yet.")
        return
    selected = st.selectbox(
        "Select fighter", list(choices), format_func=choices.get, key="trans_wins"
    )
    if selected:
        df = repos["network"].get_transitive_wins(selected)
        if not df.empty:
            st.dataframe(df, width="stretch", hide_index=True, column_config=source_columns(df))
        else:
            st.info(f"No transitive wins found for {choices[selected]}.")

    st.divider()
    st.subheader("Common Opponents Between Fighters")
    col1, col2 = st.columns(2)
    with col1:
        f1 = st.selectbox("Fighter 1", list(choices), format_func=choices.get, key="co_f1")
    with col2:
        f2 = st.selectbox("Fighter 2", list(choices), format_func=choices.get, key="co_f2")

    if f1 and f2 and f1 != f2:
        df = repos["network"].get_common_opponents(f1, f2)
        if not df.empty:
            st.dataframe(df, width="stretch", hide_index=True, column_config=source_columns(df))
        else:
            st.info(f"No common opponents found between {choices[f1]} and {choices[f2]}.")

    st.divider()
    st.subheader("Fighter Network Sample")
    net = repos["network"].get_network_sample()
    if not net.empty:
        st.dataframe(net, width="stretch", hide_index=True, column_config=source_columns(net))


def page_evolution(repos: dict):
    st.title("Evolution Over Time")
    st.caption(
        "Eras group fighters by birth year; statistics describe their recorded career profiles."
    )

    st.subheader("Physical Stats by Era")
    df = repos["evolution"].get_physical_by_era()
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                vertical_bar(
                    df,
                    "era",
                    "avg_height",
                    "avg_height",
                    color_scale="Blues",
                    y_label="Avg Height (inches)",
                ),
                width="stretch",
            )
        with col2:
            st.plotly_chart(
                vertical_bar(
                    df,
                    "era",
                    "avg_reach",
                    "avg_reach",
                    color_scale="Greens",
                    y_label="Avg Reach (inches)",
                ),
                width="stretch",
            )

    st.subheader("Striking Evolution (SLpM by Era)")
    df = repos["evolution"].get_striking_by_era()
    if not df.empty:
        st.plotly_chart(
            line_chart(df, "era", "avg_slpm", x_label="Era", y_label="Avg SLpM"),
            width="stretch",
        )
        st.dataframe(df, width="stretch", hide_index=True)


def page_championship(repos: dict):
    st.title("Championship Insights")

    st.subheader("Title Fight and Overall Finish Rates")
    df = repos["championship"].get_title_vs_regular_finish_rates()
    if not df.empty:
        row = df.iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Title Finish %", metric_value(row.get("title_finish_pct"), "%"))
        with col2:
            st.metric("Overall Finish %", metric_value(row.get("overall_finish_pct"), "%"))
        with col3:
            st.metric("Title Fights", f"{row.get('title_fights', 0):,}")
        with col4:
            st.metric("Total Fights", f"{row.get('total_fights', 0):,}")
        st.dataframe(df, width="stretch", hide_index=True)


NAVIGATION = {
    "Explore": ["Overview", "Fight archive", "Fighter explorer", "Tale of the tape"],
    "Officials": ["Referee desk", "Judge scorecards"],
    "Analysis": [
        "Finish specialists",
        "Striking efficiency",
        "Weight classes",
        "Fight pace",
        "Career & longevity",
        "Geographic insights",
        "Style matchups",
        "Evolution over time",
        "Championship insights",
    ],
    "Network": ["Network centrality", "Network analysis"],
}

PAGES = {
    "Overview": page_overview,
    "Fight archive": page_fight_archive,
    "Fighter explorer": page_fighter_explorer,
    "Tale of the tape": page_comparison,
    "Referee desk": page_referee_analysis,
    "Judge scorecards": page_judge_analysis,
    "Finish specialists": page_finish_specialists,
    "Striking efficiency": page_striking_efficiency,
    "Weight classes": page_weight_classes,
    "Fight pace": page_fight_pace,
    "Career & longevity": page_career,
    "Geographic insights": page_geographic,
    "Style matchups": page_style_matchups,
    "Network centrality": page_network_centrality,
    "Network analysis": page_network,
    "Evolution over time": page_evolution,
    "Championship insights": page_championship,
}


def main():
    st.set_page_config(page_title="UFC Fight Graph", page_icon="🥊", layout="wide")
    css = Path(__file__).with_name("style.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    page = render_sidebar()
    conn = get_connection()
    repos = get_repos(conn)
    try:
        PAGES[page](repos)
    except Exception as exc:
        st.error(f"Unable to load this page: {exc}")


if __name__ == "__main__":
    main()
