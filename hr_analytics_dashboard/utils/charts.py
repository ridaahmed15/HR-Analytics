"""
Plotly chart builders. Every function takes a DataFrame and returns a styled Figure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import analysis as an
from .cleaning import ORDERS, ORDINAL_LABELS

# --------------------------------------------------------------------------- #
# Look & feel
# --------------------------------------------------------------------------- #
INK = "#264653"
TEAL = "#2A9D8F"
SAND = "#E9C46A"
CORAL = "#E76F51"
STATUS_COLORS = {"Stayed": TEAL, "Left": CORAL}
RATE_SCALE = [TEAL, SAND, CORAL]
SEQ_SCALE = ["#E6F2F1", TEAL, INK]
DIVERGING = [CORAL, "#F7F7F7", TEAL]
PALETTE = [INK, TEAL, SAND, "#F4A261", CORAL, "#8AB17D", "#6D597A", "#4D908E"]
FONT = "Inter, Segoe UI, Helvetica, Arial, sans-serif"
SATISFACTION_COLORS = {4: [CORAL, "#F4A261", TEAL, INK], 5: [CORAL, "#F4A261", SAND, TEAL, INK]}


def style(fig: go.Figure, title: str | None = None, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=70 if title else 30, b=10),
        font=dict(family=FONT, size=12, color=INK),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title_text=""),
        showlegend=legend,
    )
    if title:
        fig.update_layout(title=dict(text=title, x=0, xanchor="left", font=dict(size=16, color=INK)))
    return fig


def _order_for(col: str, values) -> list[str]:
    """Return category order for a column (known order first, otherwise numeric/alpha sort)."""
    vals = list(pd.unique(pd.Series(values)))
    if col in ORDERS:
        return [o for o in ORDERS[col] if o in {str(v) for v in vals}]
    try:
        return [str(v) for v in sorted(vals, key=float)]
    except (TypeError, ValueError):
        return [str(v) for v in sorted(vals, key=str)]


# --------------------------------------------------------------------------- #
# Overview
# --------------------------------------------------------------------------- #
def donut_status(df: pd.DataFrame) -> go.Figure:
    counts = df["Status"].value_counts().reindex(["Stayed", "Left"]).fillna(0)
    rate = df["AttritionFlag"].mean() * 100
    fig = go.Figure(go.Pie(
        labels=counts.index.tolist(), values=counts.values.tolist(), hole=0.66, sort=False,
        marker=dict(colors=[STATUS_COLORS[i] for i in counts.index], line=dict(color="white", width=2)),
        textinfo="label+value",
    ))
    fig.add_annotation(text=f"<b>{rate:.1f}%</b><br>attrition", x=0.5, y=0.5, showarrow=False,
                       font=dict(size=22, color=INK))
    return style(fig, "Workforce status", legend=False, height=360)


def treemap_risk(df: pd.DataFrame) -> go.Figure:
    g = an.attrition_by(df, ["Department", "JobRole"])
    fig = px.treemap(
        g, path=[px.Constant("Company"), "Department", "JobRole"], values="Employees",
        color="AttritionRate", color_continuous_scale=RATE_SCALE,
        hover_data={"Leavers": True, "AttritionRate": ":.1f"},
    )
    fig.update_traces(textinfo="label+value")
    fig.update_coloraxes(colorbar=dict(title="Attrition %"))
    return style(fig, "Headcount by role (colour = attrition rate)", height=420, legend=False)


# --------------------------------------------------------------------------- #
# Attrition views
# --------------------------------------------------------------------------- #
def rate_bar(df: pd.DataFrame, col: str, horizontal: bool = False, title: str | None = None,
             height: int = 380, min_n: int = 1, sort: str = "auto") -> go.Figure:
    """Attrition rate (%) per category, coloured by rate, with the average as a dashed line."""
    g = an.attrition_by(df, col)
    g = g[g["Employees"] >= min_n].copy()
    overall = df["AttritionFlag"].mean() * 100
    order = _order_for(col, g[col])
    g[col] = g[col].astype(str)
    g["Label"] = g["AttritionRate"].round(1).astype(str) + "%"

    kw = dict(color="AttritionRate", color_continuous_scale=RATE_SCALE, text="Label",
              range_color=[0, max(float(g["AttritionRate"].max()), 1.0)],
              hover_data={"Employees": True, "Leavers": True, "AttritionRate": ":.1f", "Label": False})
    if horizontal:
        fig = px.bar(g, y=col, x="AttritionRate", orientation="h", **kw)
    else:
        fig = px.bar(g, x=col, y="AttritionRate", **kw)

    known_order = col in ORDERS or all(o.replace(".", "", 1).isdigit() for o in order)
    axis = fig.update_yaxes if horizontal else fig.update_xaxes
    if sort == "auto" and known_order:
        axis(type="category", categoryorder="array", categoryarray=order[::-1] if horizontal else order)
    else:
        axis(type="category", categoryorder="total ascending" if horizontal else "total descending")

    line = fig.add_vline if horizontal else fig.add_hline
    line_kw = {"x": overall} if horizontal else {"y": overall}
    line(line_dash="dash", line_color=INK, opacity=0.6, annotation_text=f"Avg {overall:.1f}%",
         annotation_position="top" if horizontal else "top right", **line_kw)

    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_coloraxes(showscale=False)
    (fig.update_xaxes if horizontal else fig.update_yaxes)(title="Attrition rate (%)")
    (fig.update_yaxes if horizontal else fig.update_xaxes)(title=None)
    return style(fig, title or f"Attrition rate by {col}", height=height, legend=False)


def stacked_counts(df: pd.DataFrame, col: str, horizontal: bool = False, title: str | None = None,
                   height: int = 380) -> go.Figure:
    """Headcount per category split into Stayed / Left."""
    g = df.groupby([col, "Status"]).size().reset_index(name="Employees")
    order = _order_for(col, g[col])
    g[col] = g[col].astype(str)
    kw = dict(color="Status", color_discrete_map=STATUS_COLORS, category_orders={"Status": ["Stayed", "Left"]},
              text_auto=True)
    fig = px.bar(g, y=col, x="Employees", orientation="h", **kw) if horizontal else px.bar(g, x=col, y="Employees", **kw)
    known = col in ORDERS or all(o.replace(".", "", 1).isdigit() for o in order)
    axis = fig.update_yaxes if horizontal else fig.update_xaxes
    if known:
        axis(type="category", categoryorder="array", categoryarray=order[::-1] if horizontal else order)
    else:
        axis(type="category", categoryorder="total ascending" if horizontal else "total descending")
    return style(fig, title or f"Headcount by {col}", height=height)


def heatmap_rate(df: pd.DataFrame, rows: str, cols: str, min_n: int = 10, height: int = 420) -> go.Figure:
    """Attrition-rate matrix for two dimensions; cells with fewer than `min_n` employees are greyed out."""
    d = df.groupby([rows, cols])["AttritionFlag"].agg(["size", "mean"]).reset_index()
    rate = d.pivot(index=rows, columns=cols, values="mean") * 100
    n = d.pivot(index=rows, columns=cols, values="size")
    rate.index, rate.columns, n.index, n.columns = (x.astype(str) for x in (rate.index, rate.columns, n.index, n.columns))
    r_order, c_order = _order_for(rows, rate.index), _order_for(cols, rate.columns)
    rate, n = rate.reindex(index=r_order, columns=c_order), n.reindex(index=r_order, columns=c_order)
    z = rate.where(n >= min_n)
    text = [["" if pd.isna(z.iloc[i, j]) else f"{z.iloc[i, j]:.0f}%<br>n={int(n.iloc[i, j])}"
             for j in range(z.shape[1])] for i in range(z.shape[0])]
    fig = go.Figure(go.Heatmap(
        z=z.values, x=list(z.columns), y=list(z.index), text=text, texttemplate="%{text}",
        colorscale=RATE_SCALE, zmin=0, hoverongaps=False, xgap=3, ygap=3,
        colorbar=dict(title="Attrition %"),
        customdata=n.values, hovertemplate=f"{rows}: %{{y}}<br>{cols}: %{{x}}<br>Attrition: %{{z:.1f}}%<br>Employees: %{{customdata}}<extra></extra>",
    ))
    fig.update_xaxes(type="category", side="top")
    fig.update_yaxes(type="category", autorange="reversed")
    return style(fig, None, height=height, legend=False)


def hist_by_status(df: pd.DataFrame, col: str, nbins: int = 30, title: str | None = None, height: int = 380) -> go.Figure:
    fig = px.histogram(df, x=col, color="Status", nbins=nbins, barmode="overlay", opacity=0.75,
                       color_discrete_map=STATUS_COLORS, category_orders={"Status": ["Stayed", "Left"]},
                       marginal="box")
    return style(fig, title or f"Distribution of {col}", height=height)


def box_by_status(df: pd.DataFrame, y: str, x: str | None = None, title: str | None = None, height: int = 380) -> go.Figure:
    fig = px.box(df, x=x, y=y, color="Status", color_discrete_map=STATUS_COLORS,
                 category_orders={"Status": ["Stayed", "Left"], **({x: _order_for(x, df[x])} if x else {})})
    return style(fig, title or f"{y} - leavers vs stayers", height=height)


# --------------------------------------------------------------------------- #
# Compensation / relationships
# --------------------------------------------------------------------------- #
def scatter_status(df: pd.DataFrame, x: str, y: str, title: str | None = None, height: int = 400) -> go.Figure:
    fig = px.scatter(df, x=x, y=y, color="Status", opacity=0.6, color_discrete_map=STATUS_COLORS,
                     category_orders={"Status": ["Stayed", "Left"]},
                     hover_data=["EmpID", "JobRole", "Department"])
    fig.update_traces(marker=dict(size=7))
    return style(fig, title or f"{y} vs {x}", height=height)


def grouped_mean_bar(df: pd.DataFrame, x: str, y: str, color: str, title: str | None = None,
                     height: int = 380) -> go.Figure:
    g = df.groupby([x, color])[y].mean().reset_index()
    order = _order_for(x, g[x])
    g[x] = g[x].astype(str)
    fig = px.bar(g, x=x, y=y, color=color, barmode="group", color_discrete_sequence=PALETTE,
                 text_auto=".0f" if g[y].max() > 100 else ".2f")
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=order)
    return style(fig, title or f"Average {y} by {x} and {color}", height=height)


def mean_bar(df: pd.DataFrame, x: str, y: str, horizontal: bool = True, title: str | None = None,
             height: int = 380) -> go.Figure:
    g = df.groupby(x)[y].mean().reset_index().sort_values(y, ascending=horizontal)
    g[x] = g[x].astype(str)
    fig = px.bar(g, y=x, x=y, orientation="h", text_auto=".0f") if horizontal else px.bar(g, x=x, y=y, text_auto=".0f")
    fig.update_traces(marker_color=TEAL)
    fig.update_yaxes(type="category") if horizontal else fig.update_xaxes(type="category")
    return style(fig, title or f"Average {y} by {x}", height=height, legend=False)


# --------------------------------------------------------------------------- #
# Satisfaction
# --------------------------------------------------------------------------- #
def avg_heatmap(df: pd.DataFrame, group: str, metrics: list[str], height: int = 380) -> go.Figure:
    means = df.groupby(group)[metrics].mean()
    means.index = means.index.astype(str)
    means = means.reindex(_order_for(group, means.index))
    fig = px.imshow(means, text_auto=".2f", aspect="auto", zmin=1, zmax=4,
                    color_continuous_scale=[CORAL, "#F6EBC8", TEAL])
    fig.update_xaxes(side="top", title=None)
    fig.update_yaxes(title=None)
    fig.update_coloraxes(colorbar=dict(title="Avg (1-4)"))
    return style(fig, None, height=height, legend=False)


def score_rate_lines(df: pd.DataFrame, metrics: list[str], height: int = 380) -> go.Figure:
    frames = []
    for m in metrics:
        g = an.attrition_by(df, m).rename(columns={m: "Score"})
        g["Metric"] = m
        frames.append(g)
    long = pd.concat(frames, ignore_index=True)
    fig = px.line(long, x="Score", y="AttritionRate", color="Metric", markers=True,
                  color_discrete_sequence=PALETTE, hover_data={"Employees": True, "AttritionRate": ":.1f"})
    fig.update_xaxes(dtick=1, title="Score (1 = lowest)")
    fig.update_yaxes(title="Attrition rate (%)", rangemode="tozero")
    return style(fig, "Attrition rate by satisfaction score", height=height)


def dist_100(df: pd.DataFrame, group: str, metric: str, height: int = 380) -> go.Figure:
    """100 % stacked bar of an ordinal metric's labels within each group."""
    label_col = f"{metric}_Label"
    levels = list(ORDINAL_LABELS[metric].values())
    ct = pd.crosstab(df[group], df[label_col], normalize="index") * 100
    ct = ct.reindex(columns=[l for l in levels if l in ct.columns]).fillna(0)
    ct.index = ct.index.astype(str)
    ct = ct.reindex(_order_for(group, ct.index)).rename_axis(group)
    long = ct.reset_index().melt(id_vars=group, var_name="Rating", value_name="Share")
    colors = SATISFACTION_COLORS.get(len(levels), PALETTE)
    fig = px.bar(long, y=group, x="Share", color="Rating", orientation="h", text_auto=".0f",
                 category_orders={"Rating": levels}, color_discrete_sequence=colors)
    fig.update_xaxes(title="% of employees", range=[0, 100])
    fig.update_yaxes(title=None, type="category", autorange="reversed")
    return style(fig, f"{metric} distribution by {group}", height=height)


# --------------------------------------------------------------------------- #
# Drivers
# --------------------------------------------------------------------------- #
def corr_heatmap(corr: pd.DataFrame, height: int = 640) -> go.Figure:
    fig = px.imshow(corr, text_auto=".2f", aspect="auto", zmin=-1, zmax=1,
                    color_continuous_scale="RdBu_r")
    fig.update_traces(textfont_size=9)
    fig.update_xaxes(side="top", tickangle=-45)
    return style(fig, None, height=height, legend=False)


def importance_bar(fi: pd.DataFrame, top: int = 15, height: int = 460) -> go.Figure:
    d = fi.head(top).iloc[::-1].copy()
    d["Importance (%)"] = d["Importance"] * 100
    fig = px.bar(d, x="Importance (%)", y="Feature", orientation="h", color="Importance (%)",
                 color_continuous_scale=SEQ_SCALE, text_auto=".1f")
    fig.update_coloraxes(showscale=False)
    fig.update_yaxes(title=None)
    return style(fig, f"Top {len(d)} attrition drivers (random-forest importance)", height=height, legend=False)


def spearman_bar(assoc: pd.DataFrame, height: int = 520) -> go.Figure:
    d = assoc.sort_values("Spearman ρ")
    fig = px.bar(d, x="Spearman ρ", y="Feature", orientation="h", color="Spearman ρ",
                 color_continuous_scale=DIVERGING, range_color=[-0.3, 0.3], text_auto=".2f")
    fig.update_coloraxes(showscale=False)
    fig.update_yaxes(title=None)
    return style(fig, "Correlation with attrition (negative = lower attrition)", height=height, legend=False)


def missing_bar(missing: dict, height: int = 300) -> go.Figure:
    d = pd.DataFrame({"Column": list(missing), "Missing values": list(missing.values())})
    fig = px.bar(d, x="Column", y="Missing values", text_auto=True)
    fig.update_traces(marker_color=CORAL)
    return style(fig, "Missing values found in the raw file", height=height, legend=False)


# --------------------------------------------------------------------------- #
# Free-form builder
# --------------------------------------------------------------------------- #
def custom_chart(df: pd.DataFrame, kind: str, x: str, y: str | None, color: str | None, height: int = 460) -> go.Figure:
    color = None if color in (None, "None") else color
    cmap = STATUS_COLORS if color == "Status" else None
    seq = PALETTE if color and color != "Status" else None
    if kind == "Scatter":
        fig = px.scatter(df, x=x, y=y, color=color, opacity=0.65, color_discrete_map=cmap, color_discrete_sequence=seq)
    elif kind == "Box":
        fig = px.box(df, x=x, y=y, color=color, color_discrete_map=cmap, color_discrete_sequence=seq)
    elif kind == "Histogram":
        fig = px.histogram(df, x=x, color=color, barmode="overlay", opacity=0.75, color_discrete_map=cmap,
                           color_discrete_sequence=seq)
    else:  # Bar (average of y)
        keys = [x] + ([color] if color else [])
        g = df.groupby(keys)[y].mean().reset_index()
        g[x] = g[x].astype(str)
        fig = px.bar(g, x=x, y=y, color=color, barmode="group", color_discrete_map=cmap, color_discrete_sequence=seq)
        fig.update_xaxes(type="category")
    return style(fig, None, height=height)
