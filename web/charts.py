"""Plotly chart helpers shared by dashboard pages."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


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
    fig = factory(df, x=x, y=y, title=title, labels={x: x_label or x, y: y_label or y}, **kwargs)
    fig.update_layout(height=height)
    return fig


def horizontal_bar(df, x, y, color=None, **kwargs):
    return _chart(px.bar, df, x, y, color=color, orientation="h", **kwargs)


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
