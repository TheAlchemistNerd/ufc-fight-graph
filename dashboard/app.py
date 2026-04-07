"""
UFC Knowledge Graph Dashboard - Streamlit UI Layer.

Organized by insight category. Thin UI: imports repositories (data access)
and chart generators (visualizations). Zero Cypher queries, zero data manipulation logic.
"""

import streamlit as st
import pandas as pd
from data_access.repositories import (
    Neo4jClient,
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
from visualizations.charts import (
    horizontal_bar,
    vertical_bar,
    grouped_bar,
    line_chart,
    scatter_chart,
    two_panel_chart,
)

st.set_page_config(
    page_title="UFC Knowledge Graph Dashboard",
    page_icon="[UFC]",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ===================== INITIALIZATION =====================

@st.cache_resource
def get_client():
    return Neo4jClient()


def get_repos(client):
    return {
        "overview": OverviewRepo(client),
        "fighter": FighterRepo(client),
        "referee": RefereeRepo(client),
        "geography": GeographyRepo(client),
        "weight_class": WeightClassRepo(client),
        "network": NetworkRepo(client),
        "network_centrality": NetworkCentralityRepo(client),
        "evolution": EvolutionRepo(client),
        "striking": StrikingRepo(client),
        "championship": ChampionshipRepo(client),
        "pace": FightPaceRepo(client),
        "career": CareerRepo(client),
        "style": StyleMatchupRepo(client),
        "finish": FinishRepo(client),
        "betting": BettingRepo(client),
    }


# ===================== SIDEBAR =====================

def render_sidebar():
    with st.sidebar:
        st.header("[UFC] UFC Knowledge Graph")
        st.caption("Interactive Neo4j Dashboard")

        client = get_client()
        ok, info = client.test_connection()
        if ok:
            st.success(f"[OK] Connected ({info:,} nodes)")
        else:
            st.error(f"[ERR] Connection failed: {info}")
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
                "7. Fight Pace & Duration",
                "8. Career & Longevity",
                "9. Geographic Insights",
                "10. Style Matchups",
                "11. Network Centrality",
                "12. Network Analysis",
                "13. Evolution Over Time",
                "14. Championship Insights",
                "15. Betting Patterns",
            ],
        )


# ===================== PAGE 1: OVERVIEW =====================

def page_overview(repos):
    st.title("1. UFC Knowledge Graph - Overview")

    counts = repos["overview"].get_node_counts()
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: st.metric("Fighters", f"{counts.get('Fighter', 0):,}")
    with col2: st.metric("Events", f"{counts.get('Event', 0):,}")
    with col3: st.metric("Fights", f"{counts.get('Fight', 0):,}")
    with col4: st.metric("Weight Classes", f"{counts.get('WeightClass', 0):,}")
    with col5: st.metric("Locations", f"{counts.get('Location', 0):,}")

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

def page_fighter_explorer(repos):
    st.title("2. Fighter Explorer")

    names = repos["fighter"].get_all_fighter_names()
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

def page_finish_specialists(repos):
    st.title("3. Finish Specialists")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Knockout Kings")
        df = repos["finish"].get_ko_kings()
        if not df.empty:
            fig = horizontal_bar(df, "ko_wins", "name", "ko_wins", color_scale="Reds")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Submission Specialists")
        df = repos["finish"].get_sub_specialists()
        if not df.empty:
            fig = horizontal_bar(df, "sub_wins", "name", "sub_wins", color_scale="Purples")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Career Win Percentages (Most Active)")
    df = repos["career"].get_career_lengths()
    if not df.empty:
        fig = scatter_chart(df, "total_fights", "win_pct",
                           size_col="wins", color_col="win_pct",
                           hover_data=["fighter", "nickname"],
                           color_scale="RdYlGn")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ===================== PAGE 4: REFEREE ANALYSIS =====================

def page_referee_analysis(repos):
    st.title("4. Referee Analysis")

    st.subheader("Finish Rate by Referee (Min 3 Fights)")
    df = repos["referee"].get_referee_finish_rates()
    if not df.empty:
        fig = vertical_bar(df, "referee", "ko_pct", "ko_pct", color_scale="Reds", height=500)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Most Active Referees")
    df2 = repos["referee"].get_top_referees()
    if not df2.empty:
        st.plotly_chart(horizontal_bar(df2, "fights", "referee", "fights"), use_container_width=True)


# ===================== PAGE 5: STRIKING EFFICIENCY =====================

def page_striking_efficiency(repos):
    st.title("5. Striking Efficiency")

    st.subheader("Best Strikers by SLpM/SApM Ratio (Min 2.0 SLpM)")
    df = repos["striking"].get_striking_efficiency()
    if not df.empty:
        fig = scatter_chart(df, "sapm", "slpm",
                           size_col="strike_ratio", color_col="strike_ratio",
                           hover_data=["fighter", "nickname"],
                           color_scale="RdYlGn",
                           x_label="SApM (Absorbed)", y_label="SLpM (Landed)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Reach Advantage Impact on Win Rate")
    df2 = repos["striking"].get_reach_advantage()
    if not df2.empty:
        fig = line_chart(df2, "reach_advantage_inches", "longer_reach_win_pct",
                        x_label="Reach Advantage (inches)", y_label="Longer Reach Win %")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df2, use_container_width=True, hide_index=True)


# ===================== PAGE 6: WEIGHT CLASSES =====================

def page_weight_classes(repos):
    st.title("6. Weight Class Breakdown")

    wcs = repos["weight_class"].get_all_weight_classes()
    selected_wc = st.selectbox("Select Weight Class", ["All"] + sorted(wcs))
    wc_param = None if selected_wc == "All" else selected_wc

    df = repos["weight_class"].get_win_rates(weight_class=wc_param)
    if not df.empty:
        fig = scatter_chart(df, "total_fights", "win_percentage",
                           size_col="wins", color_col="win_percentage",
                           hover_data=["fighter", "nickname"],
                           color_scale="RdYlGn")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Average Fight Duration by Weight Class")
    df2 = repos["pace"].get_duration_by_weight_class()
    if not df2.empty:
        fig = vertical_bar(df2, "weight_class", "avg_duration_min", "avg_duration_min",
                          color_scale="Blues", height=400,
                          x_label="Weight Class", y_label="Avg Duration (min)")
        st.plotly_chart(fig, use_container_width=True)


# ===================== PAGE 7: FIGHT PACE =====================

def page_fight_pace(repos):
    st.title("7. Fight Pace & Duration")

    st.subheader("Fight Finish Rate by Year")
    df = repos["pace"].get_finish_rate_by_year()
    if not df.empty:
        fig = line_chart(df, "year", "finish_pct",
                        x_label="Year", y_label="Finish %")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Fight Duration by Weight Class")
    df2 = repos["pace"].get_duration_by_weight_class()
    if not df2.empty:
        fig = horizontal_bar(df2, "avg_duration_min", "weight_class",
                            "avg_duration_min", color_scale="Blues")
        st.plotly_chart(fig, use_container_width=True)


# ===================== PAGE 8: CAREER & LONGEVITY =====================

def page_career(repos):
    st.title("8. Career & Longevity")

    st.subheader("Most Active Fighters by Career Length")
    df = repos["career"].get_career_lengths()
    if not df.empty:
        fig = scatter_chart(df, "total_fights", "win_pct",
                           size_col="wins", color_col="win_pct",
                           hover_data=["fighter", "nickname"],
                           color_scale="RdYlGn")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Underdog Analysis (Fighters with More Losses than Wins Who Still Win)")
    df2 = repos["career"].get_underdog_analysis()
    if not df2.empty:
        st.dataframe(df2, use_container_width=True, hide_index=True)

    st.subheader("Post-Loss Rebound Rate")
    df3 = repos["betting"].get_post_loss_rebound()
    if not df3.empty:
        fig = horizontal_bar(df3, "rebound_pct", "fighter", "rebound_pct",
                            color_scale="Greens", height=400,
                            x_label="Rebound Win %")
        st.plotly_chart(fig, use_container_width=True)


# ===================== PAGE 9: GEOGRAPHIC INSIGHTS =====================

def page_geographic(repos):
    st.title("9. Geographic Insights")

    st.subheader("Events by Location")
    df = repos["geography"].get_events_by_location()
    if not df.empty:
        fig = vertical_bar(df, "location", "events", "events", height=500)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Fight Outcomes by Location")
    df2 = repos["geography"].get_fight_outcomes_by_location()
    if not df2.empty:
        fig = grouped_bar(df2, "location", "count", "result")
        st.plotly_chart(fig, use_container_width=True)


# ===================== PAGE 10: STYLE MATCHUPS =====================

def page_style_matchups(repos):
    st.title("10. Style Matchups")

    st.subheader("Stance Matchup Results")
    df = repos["style"].get_stance_matchups()
    if not df.empty:
        fig = grouped_bar(df, "winner_stance", "wins", "loser_stance",
                         x_label="Winner Stance", y_label="Wins")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Gym Output (if data available)")
    df2 = repos["style"].get_gym_output()
    if not df2.empty:
        st.dataframe(df2, use_container_width=True, hide_index=True)
    else:
        st.info("No gym data available yet. This can be added by scraping gym affiliations from fighter profiles.")


# ===================== PAGE 11: NETWORK CENTRALITY =====================

def page_network_centrality(repos):
    st.title("11. Network Centrality - Fighter Influence Analysis")

    st.markdown("""
    Network centrality measures a fighter's position in the UFC matchmaking ecosystem.
    Fighters are nodes, bouts are edges. Central fighters are more influential in the network.
    """)

    st.subheader("Degree Centrality - Most Active Fighters (Unique Opponents)")
    df = repos["network_centrality"].get_degree_centrality()
    if not df.empty:
        fig = horizontal_bar(df, "unique_opponents", "fighter", "unique_opponents",
                            color_scale="Blues", height=500,
                            x_label="Unique Opponents")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Eigenvector Centrality - Influence by Opponent Quality")
    df2 = repos["network_centrality"].get_eigenvector_centrality()
    if not df2.empty:
        fig2 = scatter_chart(df2, "direct_opponents", "eigenvector_score",
                            size_col="second_degree_reach", color_col="eigenvector_score",
                            hover_data=["fighter", "nickname"],
                            color_scale="Reds",
                            x_label="Direct Opponents", y_label="Eigenvector Score")
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("PageRank Rankings - Loss-Weighted Relevance Flow")
    df3 = repos["network_centrality"].get_pagerank_rankings()
    if not df3.empty:
        fig3 = horizontal_bar(df3, "pagerank_score", "fighter", "pagerank_score",
                             color_scale="Greens", height=500,
                             x_label="PageRank Score")
        st.plotly_chart(fig3, use_container_width=True)
        st.dataframe(df3, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Betweenness Centrality - Bridge Fighters Across Clusters")
    df4 = repos["network_centrality"].get_betweenness_centrality()
    if not df4.empty:
        st.dataframe(df4, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Closeness Centrality - Network Reach")
    df5 = repos["network_centrality"].get_closeness_centrality()
    if not df5.empty:
        st.dataframe(df5, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Network Density by Weight Class")
    df6 = repos["network_centrality"].get_network_density_by_weight_class()
    if not df6.empty:
        fig6 = vertical_bar(df6, "weight_class", "density_pct", "density_pct",
                           color_scale="Viridis", height=400,
                           x_label="Weight Class", y_label="Density %")
        st.plotly_chart(fig6, use_container_width=True)

    st.divider()
    st.subheader("Degrees of Separation")
    names = repos["fighter"].get_all_fighter_names()
    selected = st.selectbox("Select fighter to find connections", sorted(names), key="path_length")
    if selected:
        df7 = repos["network_centrality"].get_path_length_sample(selected)
        if not df7.empty:
            st.dataframe(df7, use_container_width=True, hide_index=True)
        else:
            st.info(f"No connections found for {selected}.")

    st.divider()
    st.subheader("Network Robustness - Load-Bearing Fighters")
    df8 = repos["network_centrality"].get_robustness_analysis()
    if not df8.empty:
        st.dataframe(df8, use_container_width=True, hide_index=True)


# ===================== PAGE 12: NETWORK ANALYSIS =====================

def page_network(repos):
    st.title("12. Network Analysis - Connections & Paths")

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
        df2 = repos["network"].get_common_opponents(f1, f2)
        if not df2.empty:
            st.dataframe(df2, use_container_width=True, hide_index=True)
        else:
            st.info(f"No common opponents found between {f1} and {f2}.")

    st.divider()
    st.subheader("Fighter Network Sample")
    net = repos["network"].get_network_sample()
    if not net.empty:
        st.dataframe(net, use_container_width=True, hide_index=True)


# ===================== PAGE 13: EVOLUTION OVER TIME =====================

def page_evolution(repos):
    st.title("13. Evolution Over Time")

    st.subheader("Physical Stats by Era")
    df = repos["evolution"].get_physical_by_era()
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            fig = vertical_bar(df, "era", "avg_height", "avg_height",
                              color_scale="Blues", y_label="Avg Height (inches)")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = vertical_bar(df, "era", "avg_reach", "avg_reach",
                              color_scale="Greens", y_label="Avg Reach (inches)")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Striking Evolution (SLpM by Era)")
    df2 = repos["evolution"].get_striking_by_era()
    if not df2.empty:
        st.plotly_chart(line_chart(df2, "era", "avg_slpm",
                                   x_label="Era", y_label="Avg SLpM"),
                       use_container_width=True)
        st.dataframe(df2, use_container_width=True, hide_index=True)


# ===================== PAGE 13: CHAMPIONSHIP INSIGHTS =====================

def page_championship(repos):
    st.title("13. Championship Insights")

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


# ===================== PAGE 14: BETTING PATTERNS =====================

def page_betting(repos):
    st.title("14. Betting Patterns")

    st.subheader("Post-Loss Rebound Rate")
    df = repos["betting"].get_post_loss_rebound()
    if not df.empty:
        fig = horizontal_bar(df, "rebound_pct", "fighter", "rebound_pct",
                            color_scale="Greens", height=400,
                            x_label="Rebound Win %")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Underdog Victories (More Career Losses than Wins)")
    df2 = repos["career"].get_underdog_analysis()
    if not df2.empty:
        st.dataframe(df2, use_container_width=True, hide_index=True)


# ===================== ROUTER =====================

PAGE_MAP = {
    "1. Overview": page_overview,
    "2. Fighter Explorer": page_fighter_explorer,
    "3. Finish Specialists": page_finish_specialists,
    "4. Referee Analysis": page_referee_analysis,
    "5. Striking Efficiency": page_striking_efficiency,
    "6. Weight Classes": page_weight_classes,
    "7. Fight Pace & Duration": page_fight_pace,
    "8. Career & Longevity": page_career,
    "9. Geographic Insights": page_geographic,
    "10. Style Matchups": page_style_matchups,
    "11. Network Centrality": page_network_centrality,
    "12. Network Analysis": page_network,
    "13. Evolution Over Time": page_evolution,
    "14. Championship Insights": page_championship,
    "15. Betting Patterns": page_betting,
}


def main():
    page = render_sidebar()
    client = get_client()
    repos = get_repos(client)
    PAGE_MAP[page](repos)


if __name__ == "__main__":
    main()
