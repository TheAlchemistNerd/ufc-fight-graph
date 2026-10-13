"""Plotly chart helpers shared by dashboard pages."""

import math
from collections import Counter

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PALETTE = ["#ef5544", "#77cbb9", "#7ca9e6", "#dcb871", "#ad98d9"]


def style_chart(fig, height=400):
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial, sans-serif", color="#cbd0da", size=12),
        colorway=PALETTE,
        margin=dict(l=10, r=20, t=30, b=20),
        legend=dict(orientation="h", y=-0.2),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)", zeroline=False, title_font_size=12)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)", zeroline=False, title_font_size=12)
    return fig


def _chart(
    factory,
    df,
    x,
    y,
    *,
    title=None,
    height=400,
    x_label=None,
    y_label=None,
    color=None,
    color_scale="Blues",
    **kwargs,
):
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", showarrow=False)
        return fig
    if color and color in df.columns:
        kwargs["color"] = color
        if pd.api.types.is_numeric_dtype(df[color]):
            kwargs["color_continuous_scale"] = color_scale
        elif hasattr(px.colors.qualitative, color_scale):
            kwargs["color_discrete_sequence"] = getattr(px.colors.qualitative, color_scale)
    fig = factory(
        df,
        x=x,
        y=y,
        title=title,
        labels={
            x: x_label or x.replace("_", " ").title(),
            y: y_label or y.replace("_", " ").title(),
        },
        **kwargs,
    )
    if factory == px.bar and not color:
        fig.update_traces(marker_color=PALETTE[0])
    return style_chart(fig, height)


def horizontal_bar(df, x, y, color=None, **kwargs):
    fig = _chart(px.bar, df, x, y, color=color, orientation="h", **kwargs)
    fig.update_yaxes(autorange="reversed")
    return fig


def vertical_bar(df, x, y, color=None, **kwargs):
    fig = _chart(px.bar, df, x, y, color=color, **kwargs)
    fig.update_layout(xaxis_tickangle=-45)
    return fig


def line_chart(df, x, y, **kwargs):
    return _chart(px.line, df, x, y, markers=True, **kwargs)


def scatter_chart(df, x, y, size_col=None, color_col=None, hover_data=None, **kwargs):
    return _chart(
        px.scatter,
        df,
        x,
        y,
        color=color_col,
        size=size_col if size_col in df.columns else None,
        hover_data=hover_data,
        **kwargs,
    )


def donut_chart(df, names, values):
    fig = go.Figure(
        go.Pie(
            labels=df[names],
            values=df[values],
            hole=0.72,
            marker=dict(colors=PALETTE),
            textinfo="percent",
            hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>",
        )
    )
    fig.add_annotation(
        text=f"<b>{df[values].sum():,}</b><br>fights", x=0.5, y=0.5, showarrow=False, font_size=19
    )
    return style_chart(fig, 310)


def event_map(countries, metric="events"):
    mapped = countries.dropna(subset=["iso3"])
    fig = px.choropleth(
        mapped,
        locations="iso3",
        locationmode="ISO-3",
        color=metric,
        hover_name="country",
        hover_data={"iso3": False, "events": ":,", "total_fights": ":,", "locations": ":,"},
        labels={"events": "Events", "total_fights": "Fights", "locations": "Host locations"},
        color_continuous_scale=["#4e2930", "#ef5544", "#ffd29b"],
        projection="natural earth",
    )
    style_chart(fig, 500)
    fig.update_geos(
        bgcolor="rgba(0,0,0,0)",
        showframe=False,
        showcoastlines=False,
        showland=True,
        landcolor="#252b34",
        showcountries=True,
        countrycolor="#535b68",
        lataxis_range=[-60, 85],
        resolution=50,
    )
    fig.update_traces(marker_line_color="#aeb8c6", marker_line_width=0.5)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_colorbar=dict(thickness=12))
    return fig


def opponent_graph(history, fighter_url, fighter_name):
    opponents, labels = Counter(), {}
    for participants in history["fighters"]:
        for fighter in participants:
            if fighter["url"] != fighter_url:
                opponents[fighter["url"]] += 1
                labels[fighter["url"]] = fighter["name"]
    entries = opponents.most_common(12)
    fig = go.Figure()
    if not entries:
        fig.add_annotation(text="No opponent connections available", showarrow=False)
        return style_chart(fig)
    xs = [math.cos(2 * math.pi * i / len(entries)) for i in range(len(entries))]
    ys = [math.sin(2 * math.pi * i / len(entries)) for i in range(len(entries))]
    edge_x, edge_y = [], []
    for x, y in zip(xs, ys):
        edge_x.extend([0, x, None])
        edge_y.extend([0, y, None])
    fig.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line=dict(color="#454d5c", width=1.5),
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers+text",
            text=[labels[url] for url, _ in entries],
            textposition=["top center" if y >= 0 else "bottom center" for y in ys],
            customdata=[count for _, count in entries],
            marker=dict(size=[15 + count * 4 for _, count in entries], color=PALETTE[1]),
            hovertemplate="%{text}<br>%{customdata} recorded meeting(s)<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[0],
            y=[0],
            mode="markers+text",
            text=[fighter_name],
            textposition="bottom center",
            marker=dict(size=28, color=PALETTE[0]),
            hoverinfo="text",
        )
    )
    style_chart(fig, 460)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(visible=False, range=[-1.5, 1.5])
    fig.update_yaxes(visible=False, range=[-1.35, 1.35], scaleanchor="x")
    return fig
