"""
Streamlit UI helpers: theme CSS, KPI cards, and wrappers that work across Streamlit versions
(newer releases replaced `use_container_width=True` with `width="stretch"`).
"""
from __future__ import annotations

import inspect
import itertools
import re

import streamlit as st

_HAS_WIDTH_PLOT = "width" in inspect.signature(st.plotly_chart).parameters
_HAS_WIDTH_DF = "width" in inspect.signature(st.dataframe).parameters
_counter = itertools.count()


def reset_keys() -> None:
    """Call once at the top of every script run so auto-generated chart keys stay stable."""
    global _counter
    _counter = itertools.count()


def plot(fig) -> None:
    key = f"plot_{next(_counter)}"
    if _HAS_WIDTH_PLOT:
        st.plotly_chart(fig, width="stretch", key=key)
    else:
        st.plotly_chart(fig, use_container_width=True, key=key)


def table(df, **kwargs) -> None:
    if _HAS_WIDTH_DF:
        st.dataframe(df, width="stretch", hide_index=True, **kwargs)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True, **kwargs)


CSS = """
<style>
.stApp {background: #F4F7FA;}
.block-container {padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1450px;}
section[data-testid="stSidebar"] {background: #FFFFFF; border-right: 1px solid #E3E9EE;}
.hero {background: linear-gradient(120deg, #264653 0%, #2A9D8F 100%); padding: 1.5rem 1.9rem; border-radius: 18px;
       margin-bottom: 1.2rem; box-shadow: 0 6px 22px rgba(38,70,83,.18);}
.hero h1 {color: #fff; font-size: 2rem; margin: 0; padding: 0; line-height: 1.2;}
.hero p {color: rgba(255,255,255,.88); margin: .35rem 0 0 0; font-size: .95rem;}
.kpi {background: #fff; border-radius: 14px; padding: .95rem 1.05rem; box-shadow: 0 2px 12px rgba(38,70,83,.08);
      border-left: 5px solid #2A9D8F; min-height: 112px;}
.kpi .label {font-size: .72rem; text-transform: uppercase; letter-spacing: .07em; color: #6b7c85; font-weight: 700;}
.kpi .value {font-size: 1.75rem; font-weight: 800; color: #264653; line-height: 1.3;}
.kpi .delta {font-size: .76rem; font-weight: 600;}
.delta.good {color: #2A9D8F;} .delta.bad {color: #E76F51;} .delta.neutral {color: #8a98a0;}
.insight {background: #fff; border-left: 5px solid #E9C46A; border-radius: 12px; padding: .9rem 1.2rem;
          box-shadow: 0 2px 12px rgba(38,70,83,.07); margin-bottom: .6rem;}
.insight .title {font-weight: 800; color: #264653; margin-bottom: .3rem;}
.insight ul {margin: 0; padding-left: 1.15rem;} .insight li {margin-bottom: .22rem; color: #33505c;}
.section-title {font-size: 1.12rem; font-weight: 800; color: #264653; margin: 1rem 0 .1rem 0;}
.section-sub {font-size: .85rem; color: #6b7c85; margin-bottom: .5rem;}
.stTabs [data-baseweb="tab-list"] {gap: 6px; flex-wrap: wrap;}
.stTabs [data-baseweb="tab"] {background: #fff; border-radius: 10px; padding: 8px 16px; font-weight: 700; border: 1px solid #E3E9EE;}
.stTabs [aria-selected="true"] {background: #264653 !important; border-color: #264653 !important;}
.stTabs [aria-selected="true"] p {color: #fff !important;}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {display: none;}
div[data-testid="stPlotlyChart"] {background: #fff; border-radius: 14px; padding: .4rem; box-shadow: 0 2px 12px rgba(38,70,83,.06);}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def kpi_card(label: str, value: str, delta: str = "", tone: str = "neutral", accent: str = "#2A9D8F") -> str:
    return (f'<div class="kpi" style="border-left-color:{accent}"><div class="label">{label}</div>'
            f'<div class="value">{value}</div><div class="delta {tone}">{delta}</div></div>')


def tone_for(delta: float, higher_is_good: bool | None, eps: float = 1e-9) -> str:
    if higher_is_good is None or abs(delta) < eps:
        return "neutral"
    return "good" if (delta > 0) == higher_is_good else "bad"


def section(title: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-sub">{subtitle}</div>', unsafe_allow_html=True)


_BOLD = re.compile(r"\*\*(.+?)\*\*")


def insight_box(items: list[str], title: str = "💡 Key takeaways") -> None:
    lis = "".join("<li>" + _BOLD.sub(r"<b>\1</b>", i) + "</li>" for i in items)
    st.markdown(f'<div class="insight"><div class="title">{title}</div><ul>{lis}</ul></div>', unsafe_allow_html=True)
