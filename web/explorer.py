"""Interactive exploration pages built from the existing graph, without graph writes."""

import hashlib
from collections import Counter
from html import escape
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from web.catalogue import csv_bytes, fight_table, fighter_fights, filter_fights, prepare_fights
from web.charts import donut_chart, horizontal_bar, line_chart, opponent_graph


@st.cache_data(ttl=120, max_entries=8, show_spinner="Loading the fight archive…")
def cached_fights(connection_id, _repo):
    return prepare_fights(_repo.get_fights())


def catalogue(repos):
    repo = repos["explorer"]
    return cached_fights(id(repo._db), repo)


def heading(title, description, eyebrow="Explore the archive"):
    st.markdown(f'<div class="eyebrow">{escape(eyebrow)}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="lede">{escape(description)}</p>', unsafe_allow_html=True)


def source_link(label, url):
    if isinstance(url, str):
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.hostname in (
            "ufcstats.com",
            "www.ufcstats.com",
        ):
            st.link_button(label, url)


def value(value_, suffix="", decimals=None):
    if value_ is None or pd.isna(value_):
        return "N/A"
    if decimals is not None:
        return f"{float(value_):.{decimals}f}{suffix}"
    return f"{value_}{suffix}"


def fight_detail(row):
    st.subheader("Fight detail")
    st.caption(
        f"{value(row['event'])} · {row['date'].strftime('%d %b %Y') if pd.notna(row['date']) else 'Date unavailable'}"
    )
    with st.container(border=True):
        participants = row["fighters"]
        if participants:
            for column, fighter in zip(st.columns(len(participants)), participants):
                with column:
                    result = fighter.get("result") or "unrecorded"
                    color = result if result in ("win", "loss") else "other"
                    st.markdown(
                        f'<span class="result-tag result-{color}">{escape(result.upper())}</span>'
                        f'<div class="fighter-name">{escape(fighter["name"] or "Unknown fighter")}</div>',
                        unsafe_allow_html=True,
                    )
                    source_link("Fighter source ↗", fighter["url"])
        st.divider()
        columns = st.columns(4)
        for column, (label, item) in zip(
            columns,
            [
                ("Method", row["method"]),
                ("Round / time", f"{value(row['round'])} / {value(row['time'])}"),
                ("Referee", row["referee"]),
                ("Division", row["division"]),
            ],
        ):
            column.caption(label)
            column.write(value(item))
        if row["title_fight"]:
            st.caption("★ Championship bout")
        if row.get("finish_details"):
            st.caption(f"Finish details: {row['finish_details']}")
        if row["judges"]:
            st.markdown("**Published scorecards**")
            st.dataframe(
                pd.DataFrame(row["judges"]).rename(
                    columns={"judge": "Judge", "score": "Published total"}
                ),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "Fight-level totals as published by UFCStats; round-by-round cards are not supplied."
            )
        else:
            st.caption("No judge totals are published for this bout in the imported source.")
        source_link("Open fight on UFCStats ↗", row["fight_url"])


def browse_bouts(frame, key, page_size=50):
    if frame.empty:
        st.info("No fights match these filters. Try a broader year range or clear the search.")
        return
    fingerprint = hashlib.sha256("|".join(frame["fight_url"]).encode()).hexdigest()[:12]
    pages = (len(frame) + page_size - 1) // page_size
    page = 1
    if pages > 1:
        page = st.number_input(
            "Results page", min_value=1, max_value=pages, value=1, key=f"{key}_page_{fingerprint}"
        )
    start = (page - 1) * page_size
    visible = frame.iloc[start : start + page_size].reset_index(drop=True)
    st.caption(
        f"{start + 1:,}–{start + len(visible):,} of {len(frame):,} fights · Select a row to inspect the bout."
    )
    selection = st.dataframe(
        fight_table(visible),
        hide_index=True,
        width="stretch",
        height=360,
        column_order=["Date", "Matchup", "Event", "Method", "Winner", "Referee"],
        on_select="rerun",
        selection_mode="single-row",
        key=f"{key}_table_{fingerprint}_{page}",
    )
    selected = selection.selection.rows
    fight_detail(visible.iloc[selected[0] if selected else 0])


def reset_filters():
    for key in (
        "archive_query",
        "archive_years",
        "archive_divisions",
        "archive_outcomes",
        "archive_title",
        "archive_event",
    ):
        st.session_state.pop(key, None)


def page_fight_archive(repos):
    heading(
        "Fight archive",
        "Find a matchup. Follow the result. Inspect the people behind the decision.",
    )
    fights = catalogue(repos)
    if fights.empty:
        st.info("The archive will appear when fights are imported.")
        return
    with st.container(border=True):
        left, right = st.columns([2, 1])
        query = left.text_input(
            "Search fights", placeholder="Fighter, event, referee or location", key="archive_query"
        )
        years = sorted(fights["year"].dropna().astype(int).unique())
        selected_years = None
        if len(years) > 1:
            bounds = (years[0], years[-1])
            chosen = right.slider("Event years", *bounds, value=bounds, key="archive_years")
            selected_years = chosen if chosen != bounds else None
        columns = st.columns(3)
        divisions = columns[0].multiselect(
            "Divisions",
            sorted({v for values in fights["divisions"] for v in values}),
            key="archive_divisions",
        )
        outcomes = columns[1].multiselect(
            "Result types", ["KO / TKO", "Submission", "Decision", "Other"], key="archive_outcomes"
        )
        event = columns[2].selectbox(
            "Event", ["All events", *fights["event"].dropna().unique()], key="archive_event"
        )
        title_only = st.checkbox("Championship bouts only", key="archive_title")
        st.button("Clear filters", on_click=reset_filters)
    filtered = filter_fights(
        fights,
        query=query,
        years=selected_years,
        divisions=divisions,
        outcomes=outcomes,
        title_only=title_only,
    )
    if event != "All events":
        filtered = filtered[filtered["event"] == event]
    left, right = st.columns([3, 1])
    left.subheader(f"{len(filtered):,} matching fights")
    right.download_button(
        "Export results · CSV", csv_bytes(fight_table(filtered)), "ufc-fights.csv", "text/csv"
    )
    browse_bouts(filtered, "archive")


def page_overview(repos):
    heading(
        "Every fight. Every connection.",
        "Explore the fighters, events and officials that make up the UFC's recorded history.",
        "UFC · Fight Graph",
    )
    fights = catalogue(repos)
    counts = repos["overview"].get_node_counts()
    for column, label, count in zip(
        st.columns(4),
        ["Recorded fights", "Fighter profiles", "Events", "Officials"],
        [
            len(fights),
            counts.get("Fighter", 0),
            counts.get("Event", 0),
            counts.get("Referee", 0) + counts.get("Judge", 0),
        ],
    ):
        column.metric(label, f"{count:,}")
    if fights.empty:
        st.info(
            "Start a crawl to populate the archive. Imported records appear here as they arrive."
        )
        return
    st.caption(
        f"UFCStats archive · {counts.get('Referee', 0):,} referees · {counts.get('Judge', 0):,} judges · Refresh data in the sidebar to pick up new imports."
    )
    left, right = st.columns([1.4, 1])
    with left:
        st.subheader("The sport, over time")
        yearly = fights.dropna(subset=["year"]).groupby("year").size().reset_index(name="fights")
        st.plotly_chart(
            line_chart(yearly, "year", "fights", x_label="Year", y_label="Fights", height=310),
            width="stretch",
        )
    with right:
        st.subheader("How fights end")
        outcomes = (
            fights["outcome"].value_counts().rename_axis("outcome").reset_index(name="fights")
        )
        st.plotly_chart(donut_chart(outcomes, "outcome", "fights"), width="stretch")
    with st.expander("Explore data coverage"):
        ref_count = int(fights["referee"].notna().sum())
        scored = int(fights["judges"].map(bool).sum())
        st.write(
            f"{ref_count:,} / {len(fights):,} fights have a referee; {scored:,} have published judge totals."
        )
        st.progress(ref_count / len(fights), text="Referee coverage")
        st.caption(
            "Career records include bouts beyond this archive. Profile averages are career statistics, not measurements from each individual fight."
        )
    st.subheader("Recent event cards")
    recent = fights["event"].dropna().drop_duplicates().head(12).tolist()
    selected = st.selectbox("Choose an event", recent)
    browse_bouts(fights[fights["event"] == selected], "overview", page_size=30)


def choices_for(repos):
    fighters = repos["fighter"].get_fighter_options()
    names = Counter(f["name"] for f in fighters)
    return {
        f["url"]: f["name"] + (f" ({f['url'].rsplit('/', 1)[-1]})" if names[f["name"]] > 1 else "")
        for f in fighters
        if f["url"]
    }


def profile_metrics(row):
    columns = st.columns(4)
    for column, label, item in zip(
        columns,
        ["Career record", "Stance", "Height", "Reach"],
        [row.get("record"), row.get("stance"), row.get("height"), row.get("reach")],
    ):
        column.metric(label, value(item))


def skill_metrics(row):
    labels = {
        "slpm": "Sig. strikes landed / min",
        "sapm": "Sig. strikes absorbed / min",
        "str_acc": "Striking accuracy",
        "str_def": "Striking defense",
        "td_avg": "Takedowns / 15 min",
        "td_def": "Takedown defense",
        "sub_avg": "Submissions / 15 min",
    }
    percentages = {"str_acc", "str_def", "td_def"}
    return pd.DataFrame(
        [
            {
                "Statistic": label,
                "Value": value(
                    row.get(key) * 100
                    if key in percentages and pd.notna(row.get(key))
                    else row.get(key),
                    "%" if key in percentages else "",
                    1,
                ),
            }
            for key, label in labels.items()
        ]
    )


def page_fighter_explorer(repos):
    heading(
        "Fighter explorer",
        "Career statistics, recorded matchups and the opponents that connect them.",
    )
    choices = choices_for(repos)
    if not choices:
        st.info("No fighter profiles are available yet.")
        return
    selected = st.selectbox("Search fighter", list(choices), format_func=choices.get)
    profile = repos["fighter"].get_fighter_profile(selected)
    if profile.empty:
        st.info("This fighter's profile has not been imported yet.")
        return
    row = profile.iloc[0]
    st.subheader(row["name"])
    if pd.notna(row.get("nickname")):
        st.caption(row["nickname"])
    profile_metrics(row)
    source_link("View fighter on UFCStats ↗", selected)
    history = fighter_fights(catalogue(repos), selected)
    st.caption(
        f"{len(history):,} bouts in this archive. Career record and rate statistics may include other promotions."
    )
    stats, bouts, network = st.tabs(["Career statistics", "Fight history", "Opponent network"])
    with stats:
        st.dataframe(skill_metrics(row), hide_index=True, width="stretch")
        st.subheader("Similar striking profiles")
        similar = repos["fighter"].get_similar_fighters(selected)
        if similar.empty:
            st.info("More complete striking profiles are needed for this comparison.")
        else:
            st.dataframe(similar, hide_index=True, width="stretch")
    with bouts:
        browse_bouts(history, "fighter")
    with network:
        if history.empty:
            st.info("Opponent connections appear once this fighter has a recorded bout.")
        else:
            st.plotly_chart(opponent_graph(history, selected, row["name"]), width="stretch")
            st.caption(
                "Up to 12 most frequent opponents. Larger nodes indicate more meetings; hover for counts."
            )


def page_comparison(repos):
    heading(
        "Tale of the tape",
        "Compare two career profiles, their meetings and their common opponents.",
    )
    choices = choices_for(repos)
    if len(choices) < 2:
        st.info("Import at least two fighter profiles to compare them.")
        return
    columns = st.columns(2)
    first = columns[0].selectbox("First fighter", list(choices), format_func=choices.get)
    second = columns[1].selectbox("Second fighter", list(choices), index=1, format_func=choices.get)
    if first == second:
        st.info("Choose two different fighters to compare.")
        return
    profiles = [repos["fighter"].get_fighter_profile(f) for f in (first, second)]
    if any(profile.empty for profile in profiles):
        st.info("Both profiles need to be available for a comparison.")
        return
    rows = [profile.iloc[0] for profile in profiles]
    for column, row in zip(st.columns(2), rows):
        with column, st.container(border=True):
            st.subheader(row["name"])
            st.metric("Career record", value(row.get("record")))
            st.write(
                f"{value(row.get('stance'))} · {value(row.get('height'))} tall · {value(row.get('reach'))} reach"
            )
    comparison = skill_metrics(rows[0]).rename(columns={"Value": choices[first]})
    comparison[choices[second]] = skill_metrics(rows[1])["Value"]
    st.dataframe(comparison, hide_index=True, width="stretch")
    st.caption("These are career averages; comparison does not predict a fight result.")
    fights = fighter_fights(fighter_fights(catalogue(repos), first), second)
    st.subheader("Head-to-head meetings")
    if fights.empty:
        st.info("No head-to-head meeting is recorded in this archive.")
    else:
        browse_bouts(fights, "comparison")
    st.subheader("Common opponents")
    common = repos["network"].get_common_opponents(first, second)
    if common.empty:
        st.info("No common opponents are recorded.")
    else:
        st.dataframe(common, hide_index=True, width="stretch")


def page_referee_analysis(repos):
    heading(
        "Referee desk",
        "Explore assignments and recorded outcomes for each referee.",
        "Inside the officials' records",
    )
    fights = catalogue(repos)
    if fights.empty or not fights["referee"].notna().any():
        st.info("Referee assignments appear after fight details are imported.")
        return
    totals = fights["referee"].value_counts()
    columns = st.columns(3)
    columns[0].metric("Referees", f"{len(totals):,}")
    columns[1].metric("Fights with a referee", f"{totals.sum():,}")
    columns[2].metric("Coverage", f"{100 * totals.sum() / len(fights):.1f}%")
    selected = st.selectbox("Referee", totals.index.tolist())
    assigned = fights[fights["referee"] == selected]
    left, right = st.columns([1, 1.3])
    with left:
        breakdown = (
            assigned["outcome"].value_counts().rename_axis("outcome").reset_index(name="fights")
        )
        st.plotly_chart(donut_chart(breakdown, "outcome", "fights"), width="stretch")
    with right:
        st.subheader(f"{len(assigned):,} assignments")
        st.caption(
            "Outcomes describe the assigned fights; differences in sample size and matchups affect rates."
        )
        minimum = st.slider("Minimum fights for leaderboard", 1, 100, 20)
        rates = repos["referee"].get_referee_finish_rates(min_fights=minimum)
        if not rates.empty:
            st.dataframe(rates.head(20), hide_index=True, width="stretch", height=240)
    st.subheader(f"{selected} · fight log")
    browse_bouts(assigned, "referee")


def page_judge_analysis(repos):
    heading(
        "Judge scorecards",
        "Follow published totals from the judge to the individual fight.",
        "Inside the officials' records",
    )
    fights = catalogue(repos)
    if fights.empty:
        st.info("Scorecards appear after fight details are imported.")
        return
    cards = pd.DataFrame(
        [
            {**card, "fight_url": row["fight_url"]}
            for row in fights.to_dict("records")
            for card in row["judges"]
        ]
    )
    if cards.empty:
        st.info("No published judge totals are available in the imported fights.")
        return
    columns = st.columns(3)
    columns[0].metric("Judges", f"{cards['judge'].nunique():,}")
    columns[1].metric("Published scorecards", f"{len(cards):,}")
    columns[2].metric("Fights with scorecards", f"{cards['fight_url'].nunique():,}")
    selected = st.selectbox("Judge", cards["judge"].value_counts().index.tolist())
    selected_cards = cards[cards["judge"] == selected]
    assigned = fights[fights["fight_url"].isin(selected_cards["fight_url"])]
    left, right = st.columns([1, 1.4])
    with left:
        st.subheader("Most frequent totals")
        frequent = (
            selected_cards["score"]
            .value_counts()
            .head(8)
            .rename_axis("score")
            .reset_index(name="cards")
        )
        st.plotly_chart(
            horizontal_bar(
                frequent,
                "cards",
                "score",
                height=300,
                x_label="Scorecards",
                y_label="Published total",
            ),
            width="stretch",
        )
    with right:
        st.subheader(f"{selected} · {len(selected_cards):,} scorecards")
        st.caption(
            "Scores retain the source's published total. They do not provide a round-by-round breakdown or establish judging accuracy."
        )
        table = selected_cards.merge(fights[["fight_url", "bout", "date"]], on="fight_url").drop(
            columns="fight_url"
        )
        st.dataframe(
            table.rename(
                columns={"judge": "Judge", "score": "Total", "bout": "Matchup", "date": "Date"}
            ),
            hide_index=True,
            width="stretch",
            height=240,
        )
    st.subheader("Scored fights")
    browse_bouts(assigned, "judge")
