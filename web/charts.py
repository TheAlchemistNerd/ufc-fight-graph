"""
UFC Fight Graph - Visualization Layer.

Pure functions: DataFrame in, Plotly figure out.
No database logic, no UI code, no framework imports.
"""

from __future__ import annotations
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def _empty_fig(msg: str = "No data available") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False,
                       xref="paper", yref="paper", x=0.5, y=0.5,
                       font=dict(size=16))
    fig.update_layout(height=300)
    return fig


def horizontal_bar(df: pd.DataFrame, x: str, y: str, color: str = None,
                   color_scale: str = "Blues", height: int = 400,
                   title: str = None, x_label: str = None) -> go.Figure:
    if df.empty:
        return _empty_fig()
    kwargs = {}
    if color and color in df.columns:
        kwargs = {"color": color, "color_continuous_scale": color_scale}
    fig = px.bar(df, x=x, y=y, orientation="h",
                 labels={x: x_label or x, y: y}, title=title, **kwargs)
    fig.update_layout(showlegend=False, height=height)
    return fig


def vertical_bar(df: pd.DataFrame, x: str, y: str, color: str = None,
                 color_scale: str = "Blues", height: int = 400,
                 title: str = None, y_label: str = None) -> go.Figure:
    if df.empty:
        return _empty_fig()
    kwargs = {}
    if color and color in df.columns:
        kwargs = {"color": color, "color_continuous_scale": color_scale}
    fig = px.bar(df, x=x, y=y,
                 labels={x: x, y: y_label or y}, title=title, **kwargs)
    fig.update_layout(xaxis_tickangle=-45, height=height)
    return fig


def line_chart(df: pd.DataFrame, x: str, y: str,
               title: str = None, height: int = 400) -> go.Figure:
    if df.empty:
        return _empty_fig()
    fig = px.line(df, x=x, y=y, markers=True,
                  labels={x: x, y: y}, title=title)
    fig.update_layout(height=height)
    return fig


def scatter_chart(df: pd.DataFrame, x: str, y: str,
                  size_col: str = None, color_col: str = None,
                  color_scale: str = "RdYlGn", hover_data: list = None,
                  height: int = 500, title: str = None) -> go.Figure:
    if df.empty:
        return _empty_fig()
    kwargs = {}
    if size_col and size_col in df.columns:
        kwargs["size"] = size_col
    if color_col and color_col in df.columns:
        kwargs["color"] = color_col
        kwargs["color_continuous_scale"] = color_scale
    if hover_data:
        kwargs["hover_data"] = hover_data
    fig = px.scatter(df, x=x, y=y, labels={x: x, y: y}, title=title, **kwargs)
    fig.update_layout(height=height)
    return fig
