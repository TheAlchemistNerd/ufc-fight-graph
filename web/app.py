"""
UFC Fight Graph - Streamlit Dashboard (16 pages).

Thin UI layer: imports repos + chart generators.
Zero Cypher queries, zero data manipulation logic.
Clean architecture bounded contexts enforced.
"""

from __future__ import annotations
import sys
import os

# Ensure project root is in sys.path for Streamlit execution
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Clear any stale cached modules from previous runs
for _mod in list(sys.modules.keys()):
    if _mod.startswith(('data_access', 'config', 'infrastructure', 'domain', 'web', 'visualizations')):
        del sys.modules[_mod]

import streamlit as st
import pandas as pd
from config.settings import Neo4jConfig
from infrastructure.neo4j_client import Neo4jConnection
from data_access.repositories import (
    OverviewRepo,
    NetworkCentralityRepo,
    NetworkRepo,
    JudgeRepo,
    FighterRepo,
    RefereeRepo,
    StrikingRepo,
    GeographyRepo,
    WeightClassRepo,
    CareerRepo,
    EvolutionRepo,
    FightPaceRepo,
    StyleMatchupRepo,
    FinishRepo,
    ChampionshipRepo,
    BettingRepo,
)
from web.charts import (
    horizontal_bar,
    vertical_bar,
    line_chart,
    scatter_chart,
)


# ===================== INITIALIZATION =====================

@st.cache_resource
def get_connection() -> Neo4jConnection:
    return Neo4jConnection(Neo4jConfig())


@st.cache_resource
def get_repos(_conn: Neo4jConnection) -> dict:
    return {
        "overview": OverviewRepo(_conn),
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
        "betting": BettingRepo(_conn),
        "centrality": NetworkCentralityRepo(_conn),
        "network": NetworkRepo(_conn),
        "judge": JudgeRepo(_conn),
    }


# ===================== SIDEBAR =====================

def render_sidebar() -> str:
    with st.sidebar:
        st.header("UFC Knowledge Graph")
        st.caption("Network Analysis Dashboard")

        conn = get_connection()
        ok, count = conn.test_connection()
        if ok:
            st.success(f"Connected ({count:,} nodes)")
        else:
            st.error("Connection failed")
            st.stop()

        st.divider()

        return st.radio(
            "Navigate",
            [
                "1. Overview",
                "2. Fighter Explorer",
                "3. Finish Specialists",
                "4. Referee Analysis",
                "5. Striking Efficiency",
                "6. Weight Classes",
                "7. Fight Pace",
                "8. Career & Longevity",
                "9. Geographic Insights",
                "10. Style Matchups",
                "11. Network Centrality",
                "12. Network Analysis",
                "13. Judge Scoring",
                "14. Evolution Over Time",
                "15. Championship Insights",
                "16. Betting Patterns",
            ],
        )


# ===================== PAGE 1: OVERVIEW =====================

def page_overview(repos: dict):
    st.title("1. Overview")

    counts = repos["overview"].get_node_counts()
    cols = st.columns(5)
    metrics = [
        ("Fighters", counts.get("Fighter", 0)),
        ("Events", counts.get("Event", 0)),
        ("Fights", counts.get("Fight", 0)),
        ("Weight Classes", counts.get("WeightClass", 0)),
        ("Locations", counts.get("Location", 0)),
    ]
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, f"{value:,}")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Most Active Fighters")
        df = repos["overview"].get_top_active_fighters()
        if not df.empty:
            st.plotly_chart(horizontal_bar(df, "fights", "name", "fights"), use_container_width=True)
    with col2:
        st.subheader("Top KO Artists")
        df = repos["overview"].get_top_ko_artists()
        if not df.empty:
            st.plotly_chart(horizontal_bar(df, "ko_wins", "name", "ko_wins", color_scale="Reds"), use_container_width=True)

    st.subheader("Events Over Time")
    df = repos["overview"].get_events_over_time()
    if not df.empty:
        st.plotly_chart(line_chart(df, "year", "events"), use_container_width=True)

    st.subheader("Recent Events")
    df = repos["overview"].get_recent_events()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)


# ===================== PAGE 2: FIGHTER EXPLORER =====================

def page_fighter_explorer(repos: dict):
    st.title("2. Fighter Explorer")

    names = repos["fighter"].get_all_fighter_names()
    if not names:
        st.info("No fighters loaded yet.")
        return

    selected = st.selectbox("Search Fighter", sorted(names))
    if not selected:
        return

    profile = repos["fighter"].get_fighter_profile(selected)
    if profile.empty:
        st.warning("No profile data found.")
        return

    row = profile.iloc[0]
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Record", row.get("record") or "N/A")
    with col2: st.metric("Wins", row.get("wins") or "N/A")
    with col3: st.metric("Losses", row.get("losses") or "N/A")
    with col4: st.metric("Stance", row.get("stance") or "N/A")

    st.markdown(f"**{row['name']}** \"{row['nickname']}\" - {row['height']} | {row['weight']} | {row['reach']}")

    st.subheader("Fight History")
    history = repos["fighter"].get_fighter_history(selected)
    if not history.empty:
        st.dataframe(history, use_container_width=True, hide_index=True)

    st.subheader("Similar Striking Profile")
    similar = repos["fighter"].get_similar_fighters(selected)
    if not similar.empty:
        st.dataframe(similar, use_container_width=True, hide_index=True)


# ===================== PAGE 3: FINISH SPECIALISTS =====================

def page_finish_specialists(repos: dict):
    st.title("3. Finish Specialists")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Knockout Kings")
        df = repos["finish"].get_ko_kings()
        if not df.empty:
            st.plotly_chart(horizontal_bar(df, "ko_wins", "name", "ko_wins", color_scale="Reds"), use_container_width=True)
    with col2:
        st.subheader("Submission Specialists")
        df = repos["finish"].get_sub_specialists()
        if not df.empty:
            st.plotly_chart(horizontal_bar(df, "sub_wins", "name", "sub_wins", color_scale="Purples"), use_container_width=True)

    st.subheader("Career Win Percentages (Most Active)")
    df = repos["career"].get_career_lengths()
    if not df.empty:
        st.plotly_chart(scatter_chart(df, "total_fights", "win_pct",
                                     size_col="wins", color_col="win_pct",
                                     hover_data=["fighter", "nickname"],
                                     color_scale="RdYlGn"),
                       use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ===================== PAGE 4: REFEREE ANALYSIS =====================

def page_referee_analysis(repos: dict):
    st.title("4. Referee Analysis")

    st.subheader("Finish Rate by Referee (Min 3 Fights)")
    df = repos["referee"].get_referee_finish_rates()
    if not df.empty:
        st.plotly_chart(vertical_bar(df, "referee", "ko_pct", "ko_pct", color_scale="Reds", height=500), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Most Active Referees")
    df = repos["referee"].get_top_referees()
    if not df.empty:
        st.plotly_chart(horizontal_bar(df, "fights", "referee", "fights"), use_container_width=True)


# ===================== PAGE 5: STRIKING EFFICIENCY =====================

def page_striking_efficiency(repos: dict):
    st.title("5. Striking Efficiency")

    st.subheader("Best Strikers by SLpM/SApM Ratio (Min 2.0 SLpM)")
    df = repos["striking"].get_striking_efficiency()
    if not df.empty:
        st.plotly_chart(scatter_chart(df, "sapm", "slpm",
                                     size_col="strike_ratio", color_col="strike_ratio",
                                     hover_data=["fighter", "nickname"],
                                     color_scale="RdYlGn",
                                     x_label="SApM (Absorbed)", y_label="SLpM (Landed)"),
                       use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Reach Advantage Impact on Win Rate")
    df = repos["striking"].get_reach_advantage()
    if not df.empty:
        st.plotly_chart(line_chart(df, "reach_advantage_inches", "longer_reach_win_pct",
                                  x_label="Reach Advantage (inches)", y_label="Longer Reach Win %"),
                       use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ===================== PAGE 6: WEIGHT CLASSES =====================

def page_weight_classes(repos: dict):
    st.title("6. Weight Classes")

    wcs = repos["weight_class"].get_all_weight_classes()
    selected_wc = st.selectbox("Select Weight Class", ["All"] + sorted(wcs))
    wc_param = None if selected_wc == "All" else selected_wc

    df = repos["weight_class"].get_win_rates(weight_class=wc_param)
    if not df.empty:
        st.plotly_chart(scatter_chart(df, "total_fights", "win_percentage",
                                     size_col="wins", color_col="win_percentage",
                                     hover_data=["fighter", "nickname"],
                                     color_scale="RdYlGn"),
                       use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Average Fight Duration by Weight Class")
    df = repos["pace"].get_duration_by_weight_class()
    if not df.empty:
        st.plotly_chart(vertical_bar(df, "weight_class", "avg_duration_min", "avg_duration_min",
                                    color_scale="Blues", height=400,
                                    x_label="Weight Class", y_label="Avg Duration (min)"),
                       use_container_width=True)


# ===================== PAGE 7: FIGHT PACE =====================

def page_fight_pace(repos: dict):
    st.title("7. Fight Pace & Duration")

    st.subheader("Fight Finish Rate by Year")
    df = repos["pace"].get_finish_rate_by_year()
    if not df.empty:
        st.plotly_chart(line_chart(df, "year", "finish_pct",
                                  x_label="Year", y_label="Finish %"),
                       use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Fight Duration by Weight Class")
    df = repos["pace"].get_duration_by_weight_class()
    if not df.empty:
        st.plotly_chart(horizontal_bar(df, "avg_duration_min", "weight_class",
                                      "avg_duration_min", color_scale="Blues"),
                       use_container_width=True)


# ===================== PAGE 8: CAREER & LONGEVITY =====================

def page_career(repos: dict):
    st.title("8. Career & Longevity")

    st.subheader("Most Active Fighters by Career Length")
    df = repos["career"].get_career_lengths()
    if not df.empty:
        st.plotly_chart(scatter_chart(df, "total_fights", "win_pct",
                                     size_col="wins", color_col="win_pct",
                                     hover_data=["fighter", "nickname"],
                                     color_scale="RdYlGn"),
                       use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Underdog Victories (More Career Losses than Wins)")
    df = repos["career"].get_underdog_analysis()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Post-Loss Rebound Rate")
    df = repos["betting"].get_post_loss_rebound()
    if not df.empty:
        st.plotly_chart(horizontal_bar(df, "rebound_pct", "fighter", "rebound_pct",
                                      color_scale="Greens", height=400,
                                      x_label="Rebound Win %"),
                       use_container_width=True)


# ===================== PAGE 9: GEOGRAPHIC INSIGHTS =====================

def page_geographic(repos: dict):
    st.title("9. Geographic Insights")

    st.subheader("Events by Location")
    df = repos["geography"].get_events_by_location()
    if not df.empty:
        st.plotly_chart(vertical_bar(df, "location", "events", "events", height=500), use_container_width=True)

    st.subheader("Fight Outcomes by Location")
    df = repos["geography"].get_fight_outcomes_by_location()
    if not df.empty:
        st.plotly_chart(scatter_chart(df, "location", "count",
                                     color_col="result", hover_data=["location"],
                                     color_scale="Set1"),
                       use_container_width=True)


# ===================== PAGE 10: STYLE MATCHUPS =====================

def page_style_matchups(repos: dict):
    st.title("10. Style Matchups")

    st.subheader("Stance Matchup Results")
    df = repos["style"].get_stance_matchups()
    if not df.empty:
        st.plotly_chart(scatter_chart(df, "winner_stance", "wins",
                                     color_col="loser_stance", hover_data=["winner_stance", "loser_stance"],
                                     color_scale="Set1"),
                       use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Gym Output (if data available)")
    df = repos["style"].get_gym_output()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No gym data available yet. Add gym affiliations from fighter profiles.")


# ===================== PAGE 11: NETWORK CENTRALITY =====================

def page_network_centrality(repos: dict):
    st.title("11. Network Centrality")
    st.markdown("Fighter influence metrics based on network position in the UFC matchmaking ecosystem.")

    st.subheader("Degree Centrality - Most Unique Opponents")
    df = repos["centrality"].get_degree_centrality()
    if not df.empty:
        st.plotly_chart(horizontal_bar(df, "unique_opponents", "fighter", "unique_opponents", height=500), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Eigenvector Centrality - Influence by Opponent Quality")
    df = repos["centrality"].get_eigenvector_centrality()
    if not df.empty:
        st.plotly_chart(scatter_chart(df, "direct_opponents", "eigenvector_score",
                                     size_col="second_degree_reach", color_col="eigenvector_score",
                                     hover_data=["fighter", "nickname"], color_scale="Reds"),
                       use_container_width=True)

    st.subheader("PageRank Rankings - Loss-Weighted Relevance Flow")
    df = repos["centrality"].get_pagerank_rankings()
    if not df.empty:
        st.plotly_chart(horizontal_bar(df, "pagerank_score", "fighter", "pagerank_score",
                                      color_scale="Greens", height=500), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Betweenness Centrality - Bridge Fighters")
    df = repos["centrality"].get_betweenness_centrality()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Network Density by Weight Class")
    df = repos["centrality"].get_network_density_by_weight_class()
    if not df.empty:
        st.plotly_chart(vertical_bar(df, "weight_class", "density_pct", "density_pct", height=400), use_container_width=True)

    st.subheader("Degrees of Separation from Leon Edwards")
    df = repos["centrality"].get_path_length_sample("Leon Edwards")
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)


# ===================== PAGE 12: NETWORK ANALYSIS =====================

def page_network(repos: dict):
    st.title("12. Network Analysis")

    st.subheader("Transitive Wins")
    names = repos["fighter"].get_all_fighter_names()
    selected = st.selectbox("Select fighter", sorted(names), key="trans_wins")
    if selected:
        df = repos["network"].get_transitive_wins(selected)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info(f"No transitive wins found for {selected}.")

    st.divider()
    st.subheader("Common Opponents Between Fighters")
    col1, col2 = st.columns(2)
    with col1:
        f1 = st.selectbox("Fighter 1", sorted(names), key="co_f1")
    with col2:
        f2 = st.selectbox("Fighter 2", sorted(names), key="co_f2")

    if f1 and f2 and f1 != f2:
        df = repos["network"].get_common_opponents(f1, f2)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info(f"No common opponents found between {f1} and {f2}.")

    st.divider()
    st.subheader("Fighter Network Sample")
    net = repos["network"].get_network_sample()
    if not net.empty:
        st.dataframe(net, use_container_width=True, hide_index=True)


# ===================== PAGE 13: JUDGE SCORING =====================

def page_judge_analysis(repos: dict):
    st.title("13. Judge Scoring Analysis")
    st.markdown("UFC judge scoring patterns, consistency, and potential biases.")

    st.subheader("Most Active Judges")
    df = repos["judge"].get_judge_activity_volume()
    if not df.empty:
        st.plotly_chart(horizontal_bar(df, "fights_scored", "judge", "fights_scored", height=400), use_container_width=True)

    st.subheader("Judges with Widest Scorecard Margins")
    df = repos["judge"].get_judge_widest_margins()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Judges with Most 10-8 Scorecards")
    df = repos["judge"].get_judge_10_8_frequency()
    if not df.empty:
        st.plotly_chart(horizontal_bar(df, "wide_margins", "judge", "wide_margins", color_scale="Reds", height=400), use_container_width=True)

    st.subheader("Judge Consistency (Scorecard Agreement)")
    df = repos["judge"].get_judge_consistency_analysis()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)


# ===================== PAGE 14: EVOLUTION OVER TIME =====================

def page_evolution(repos: dict):
    st.title("14. Evolution Over Time")

    st.subheader("Physical Stats by Era")
    df = repos["evolution"].get_physical_by_era()
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(vertical_bar(df, "era", "avg_height", "avg_height",
                                        color_scale="Blues", y_label="Avg Height (inches)"),
                           use_container_width=True)
        with col2:
            st.plotly_chart(vertical_bar(df, "era", "avg_reach", "avg_reach",
                                        color_scale="Greens", y_label="Avg Reach (inches)"),
                           use_container_width=True)

    st.subheader("Striking Evolution (SLpM by Era)")
    df = repos["evolution"].get_striking_by_era()
    if not df.empty:
        st.plotly_chart(line_chart(df, "era", "avg_slpm",
                                  x_label="Era", y_label="Avg SLpM"),
                       use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ===================== PAGE 15: CHAMPIONSHIP INSIGHTS =====================

def page_championship(repos: dict):
    st.title("15. Championship Insights")

    st.subheader("Title Fight vs Regular Fight Finish Rates")
    df = repos["championship"].get_title_vs_regular_finish_rates()
    if not df.empty:
        row = df.iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Title Finish %", f"{row.get('title_finish_pct', 'N/A')}%")
        with col2: st.metric("Overall Finish %", f"{row.get('overall_finish_pct', 'N/A')}%")
        with col3: st.metric("Title Fights", f"{row.get('title_fights', 0):,}")
        with col4: st.metric("Total Fights", f"{row.get('total_fights', 0):,}")
        st.dataframe(df, use_container_width=True, hide_index=True)


# ===================== PAGE 16: BETTING PATTERNS =====================

def page_betting(repos: dict):
    st.title("16. Betting Patterns")

    st.subheader("Post-Loss Rebound Rate")
    df = repos["betting"].get_post_loss_rebound()
    if not df.empty:
        st.plotly_chart(horizontal_bar(df, "rebound_pct", "fighter", "rebound_pct",
                                      color_scale="Greens", height=400,
                                      x_label="Rebound Win %"),
                       use_container_width=True)

    st.subheader("Underdog Analysis (More Losses than Wins)")
    df = repos["career"].get_underdog_analysis()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)


# ===================== ROUTER =====================

PAGES = {
    "1. Overview": page_overview,
    "2. Fighter Explorer": page_fighter_explorer,
    "3. Finish Specialists": page_finish_specialists,
    "4. Referee Analysis": page_referee_analysis,
    "5. Striking Efficiency": page_striking_efficiency,
    "6. Weight Classes": page_weight_classes,
    "7. Fight Pace": page_fight_pace,
    "8. Career & Longevity": page_career,
    "9. Geographic Insights": page_geographic,
    "10. Style Matchups": page_style_matchups,
    "11. Network Centrality": page_network_centrality,
    "12. Network Analysis": page_network,
    "13. Judge Scoring": page_judge_analysis,
    "14. Evolution Over Time": page_evolution,
    "15. Championship Insights": page_championship,
    "16. Betting Patterns": page_betting,
}


def main():
    page = render_sidebar()
    conn = get_connection()
    repos = get_repos(conn)
    PAGES[page](repos)


if __name__ == "__main__":
    main()
