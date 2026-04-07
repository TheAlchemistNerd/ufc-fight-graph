"""
Visualization Layer — Plotly Chart Generators.

Pure functions: take DataFrames, return Plotly figures.
No database logic, no UI code, no Streamlit imports.
"""

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


def _empty_fig(message="No data available") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False,
                       xref="paper", yref="paper", x=0.5, y=0.5,
                       font=dict(size=16))
    fig.update_layout(height=300)
    return fig


# ===================== BAR CHARTS =====================

def horizontal_bar(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: str = None,
    title: str = None,
    color_scale: str = "Blues",
    height: int = 400,
    x_label: str = None,
    y_label: str = None,
) -> go.Figure:
    """Standard horizontal bar chart."""
    if df.empty:
        return _empty_fig()

    color_kwargs = {}
    if color_col and color_col in df.columns:
        color_kwargs = {"color": color_col, "color_continuous_scale": color_scale}

    fig = px.bar(
        df, x=x_col, y=y_col, orientation="h",
        labels={x_col: x_label or x_col, y_col: y_label or y_col},
        title=title,
        **color_kwargs
    )
    fig.update_layout(showlegend=False, height=height)
    return fig


def vertical_bar(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: str = None,
    title: str = None,
    color_scale: str = "Blues",
    height: int = 400,
    x_tick_angle: int = -45,
    x_label: str = None,
    y_label: str = None,
) -> go.Figure:
    """Standard vertical bar chart."""
    if df.empty:
        return _empty_fig()

    color_kwargs = {}
    if color_col and color_col in df.columns:
        color_kwargs = {"color": color_col, "color_continuous_scale": color_scale}

    fig = px.bar(
        df, x=x_col, y=y_col,
        labels={x_col: x_label or x_col, y_col: y_label or y_col},
        title=title,
        **color_kwargs
    )
    fig.update_layout(xaxis_tickangle=x_tick_angle, height=height)
    return fig


def grouped_bar(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: str,
    title: str = None,
    height: int = 400,
    x_tick_angle: int = -45,
) -> go.Figure:
    """Grouped bar chart (barmode='group')."""
    if df.empty:
        return _empty_fig()

    fig = px.bar(
        df, x=x_col, y=y_col, color=color_col, barmode="group",
        labels={x_col: x_col, y_col: y_col, color_col: color_col},
        title=title,
    )
    fig.update_layout(xaxis_tickangle=x_tick_angle, height=height)
    return fig


# ===================== LINE & SCATTER =====================

def line_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str = None,
    markers: bool = True,
    height: int = 400,
    x_label: str = None,
    y_label: str = None,
) -> go.Figure:
    """Simple line chart with optional markers."""
    if df.empty:
        return _empty_fig()

    fig = px.line(
        df, x=x_col, y=y_col, markers=markers,
        labels={x_col: x_label or x_col, y_col: y_label or y_col},
        title=title,
    )
    fig.update_layout(height=height)
    return fig


def scatter_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    size_col: str = None,
    color_col: str = None,
    hover_data: list = None,
    title: str = None,
    color_scale: str = "RdYlGn",
    height: int = 500,
    x_label: str = None,
    y_label: str = None,
) -> go.Figure:
    """Scatter/bubble chart."""
    if df.empty:
        return _empty_fig()

    size_kwargs = {}
    if size_col and size_col in df.columns:
        size_kwargs = {"size": size_col}

    color_kwargs = {}
    if color_col and color_col in df.columns:
        color_kwargs = {"color": color_col, "color_continuous_scale": color_scale}

    hover_kwargs = {}
    if hover_data:
        hover_kwargs = {"hover_data": hover_data}

    fig = px.scatter(
        df, x=x_col, y=y_col,
        labels={x_col: x_label or x_col, y_col: y_label or y_col},
        title=title,
        **size_kwargs, **color_kwargs, **hover_kwargs
    )
    fig.update_layout(height=height)
    return fig


# ===================== COMPOSITE CHARTS =====================

def two_panel_chart(
    df1: pd.DataFrame, df2: pd.DataFrame,
    x1: str, y1: str, title1: str,
    x2: str, y2: str, title2: str,
    color_scale1: str = "Blues",
    color_scale2: str = "Greens",
    height: int = 400,
) -> go.Figure:
    """Two side-by-side bar charts in one figure."""
    if df1.empty and df2.empty:
        return _empty_fig()

    fig = make_subplots(rows=1, cols=2, subplot_titles=(title1, title2))

    if not df1.empty:
        fig.add_trace(go.Bar(x=df1[y1], y=df1[x1], orientation="h",
                             marker=dict(color=df1[x1], colorscale=color_scale1),
                             name=title1), row=1, col=1)

    if not df2.empty:
        fig.add_trace(go.Bar(x=df2[y2], y=df2[x2], orientation="h",
                             marker=dict(color=df2[x2], colorscale=color_scale2),
                             name=title2), row=1, col=2)

    fig.update_layout(height=height, showlegend=False)
    return fig
