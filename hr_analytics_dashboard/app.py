"""
HR Analytics Dashboard
----------------------
Run with:   streamlit run app.py
"""
from __future__ import annotations

import io
import math
from pathlib import Path

import pandas as pd
import streamlit as st

from utils import analysis as an
from utils import charts as ch
from utils import ui
from utils.cleaning import ORDERS, ORDINAL_LABELS, clean_hr_data

st.set_page_config(page_title="HR Analytics Dashboard", page_icon="👥", layout="wide",
                   initial_sidebar_state="expanded")
ui.reset_keys()
ui.inject_css()

BASE_DIR = Path(__file__).parent
DEFAULT_FILE = BASE_DIR / "data" / "HR_Analytics.xlsx"

SAT_METRICS = ["EnvironmentSatisfaction", "JobSatisfaction", "RelationshipSatisfaction", "JobInvolvement", "WorkLifeBalance"]
BREAKDOWNS = ["Department", "JobRole", "Gender", "AgeGroup", "MaritalStatus", "BusinessTravel", "OverTime",
              "SalarySlab", "EducationField", "Education_Label", "TenureBand", "DistanceBand", "JobLevel",
              "StockOptionLevel", "NumCompaniesWorked", "TrainingTimesLastYear", "YearsSinceLastPromotion",
              "EnvironmentSatisfaction_Label", "JobSatisfaction_Label", "WorkLifeBalance_Label",
              "JobInvolvement_Label", "PerformanceRating_Label"]
FILTERS = [("Department", "Department"), ("JobRole", "Job role"), ("Gender", "Gender"), ("OverTime", "Overtime"),
           ("AgeGroup", "Age group"), ("MaritalStatus", "Marital status"), ("BusinessTravel", "Business travel"),
           ("SalarySlab", "Salary slab")]


# --------------------------------------------------------------------------- #
# Cached data functions
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Loading & cleaning data…")
def load_clean(name: str, content: bytes | None, mtime: float):
    if content is None:
        raw = pd.read_excel(DEFAULT_FILE)
    elif name.lower().endswith(".csv"):
        raw = pd.read_csv(io.BytesIO(content))
    else:
        raw = pd.read_excel(io.BytesIO(content))
    return clean_hr_data(raw)


@st.cache_data(show_spinner="Training driver model…")
def get_importance(df: pd.DataFrame):
    return an.feature_importance(df)


@st.cache_data(show_spinner=False)
def to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


@st.cache_data(show_spinner=False)
def to_xlsx(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="HR_Cleaned")
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Sidebar: data source + filters
# --------------------------------------------------------------------------- #
st.sidebar.markdown("## 👥 HR Analytics")
with st.sidebar.expander("📁 Data source"):
    upload = st.file_uploader("Upload an HR file (.xlsx / .csv)", type=["xlsx", "csv"])
    st.caption("Must have the same columns as the sample file. By default `data/HR_Analytics.xlsx` is used.")

src_name, content = DEFAULT_FILE.name, None
if upload is not None:
    src_name, content = upload.name, upload.getvalue()
try:
    df_all, log = load_clean(src_name, content, 0.0 if content else DEFAULT_FILE.stat().st_mtime)
except Exception as exc:  # bad upload -> fall back to the bundled file
    st.sidebar.error(f"Could not use the uploaded file: {exc}")
    src_name, content = DEFAULT_FILE.name, None
    df_all, log = load_clean(src_name, None, DEFAULT_FILE.stat().st_mtime)

sig = f"{src_name}-{len(df_all)}"
ver = st.session_state.get("filter_ver", 0)


def key(name: str) -> str:
    return f"flt_{sig}_{ver}_{name}"


def reset_filters() -> None:
    st.session_state["filter_ver"] = st.session_state.get("filter_ver", 0) + 1


def options(col: str) -> list:
    vals = df_all[col].dropna().unique().tolist()
    return [o for o in ORDERS[col] if o in vals] if col in ORDERS else sorted(vals)


st.sidebar.markdown("### 🎛️ Filters")
st.sidebar.button("↺ Reset all filters", on_click=reset_filters)

selections: dict[str, list] = {}
for i, (col, label) in enumerate(FILTERS):
    if i == 4:
        exp = st.sidebar.expander("More filters")
    target = st.sidebar if i < 4 else exp
    selections[col] = target.multiselect(label, options(col), default=options(col), key=key(col))

age_lo, age_hi = int(df_all["Age"].min()), int(df_all["Age"].max())
inc_lo = int(math.floor(df_all["MonthlyIncome"].min() / 100) * 100)
inc_hi = int(math.ceil(df_all["MonthlyIncome"].max() / 100) * 100)
age_rng = st.sidebar.slider("Age", age_lo, age_hi, (age_lo, age_hi), key=key("age"))
inc_rng = st.sidebar.slider("Monthly income", inc_lo, inc_hi, (inc_lo, inc_hi), step=100, key=key("inc"))

mask = df_all["Age"].between(*age_rng) & df_all["MonthlyIncome"].between(*inc_rng)
for col, sel in selections.items():
    mask &= df_all[col].isin(sel)
df = df_all[mask].reset_index(drop=True)

st.sidebar.markdown("---")
st.sidebar.caption(f"Showing **{len(df):,}** of **{len(df_all):,}** employees")

# --------------------------------------------------------------------------- #
# Header + KPIs
# --------------------------------------------------------------------------- #
removed = log["rows_before"] - log["rows_after"]
ui.hero("👥 HR Analytics Dashboard",
        f"Source: {src_name} · {len(df):,} of {len(df_all):,} employees selected · "
        f"{removed} duplicate rows and {log['cells_imputed']} missing values handled during cleaning")

if df.empty:
    st.warning("No employees match the current filters. Adjust or reset the filters in the sidebar.")
    st.stop()

k, k0 = an.kpis(df), an.kpis(df_all)
d_rate = k["attrition_rate"] - k0["attrition_rate"]
d_inc = (k["avg_income"] / k0["avg_income"] - 1) * 100
d_ten = k["avg_tenure"] - k0["avg_tenure"]
d_ot = k["overtime_share"] - k0["overtime_share"]
d_sat = k["avg_job_sat"] - k0["avg_job_sat"]
cards = [
    ("Employees", f"{k['headcount']:,}", f"{k['headcount'] / k0['headcount']:.0%} of workforce", "neutral", ch.INK),
    ("Attrition rate", f"{k['attrition_rate']:.1f}%", f"{k['leavers']:,} leavers · {d_rate:+.1f} pts vs all",
     ui.tone_for(d_rate, False, 0.05), ch.CORAL),
    ("Avg monthly income", f"{k['avg_income']:,.0f}", f"{d_inc:+.1f}% vs all", ui.tone_for(d_inc, None), ch.SAND),
    ("Avg tenure", f"{k['avg_tenure']:.1f} yrs", f"{d_ten:+.1f} yrs vs all", ui.tone_for(d_ten, None), ch.TEAL),
    ("Overtime share", f"{k['overtime_share']:.1f}%", f"{d_ot:+.1f} pts vs all", ui.tone_for(d_ot, False, 0.05), "#F4A261"),
    ("Avg job satisfaction", f"{k['avg_job_sat']:.2f} / 4", f"{d_sat:+.2f} vs all", ui.tone_for(d_sat, True, 0.005), "#6D597A"),
]
for col_, card in zip(st.columns(6), cards):
    col_.markdown(ui.kpi_card(*card), unsafe_allow_html=True)
st.write("")

tabs = st.tabs(["📊 Overview", "🔥 Attrition", "💰 Compensation", "😊 Satisfaction", "🧭 Career & Tenure",
                "🧠 Drivers", "🧹 Data Quality", "🔎 Explorer"])

# --------------------------------------------------------------------------- #
# 1. Overview
# --------------------------------------------------------------------------- #
with tabs[0]:
    ui.insight_box(an.build_insights(df))
    c1, c2 = st.columns([1, 1.4])
    with c1:
        ui.plot(ch.donut_status(df))
    with c2:
        ui.plot(ch.rate_bar(df, "Department", title="Attrition rate by department", height=360))
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.treemap_risk(df))
    with c2:
        ui.plot(ch.hist_by_status(df, "Age", nbins=25, title="Age distribution - leavers vs stayers", height=420))
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.rate_bar(df, "JobRole", horizontal=True, title="Attrition rate by job role", height=400, min_n=5))
    with c2:
        ui.plot(ch.stacked_counts(df, "AgeGroup", title="Headcount by age group", height=400))

# --------------------------------------------------------------------------- #
# 2. Attrition deep-dive
# --------------------------------------------------------------------------- #
with tabs[1]:
    ui.section("Attrition breakdown", "Pick any dimension to see who is leaving. The dashed line is the average of the current selection.")
    dims = [d for d in BREAKDOWNS if d in df.columns]
    by = st.selectbox("Break down attrition by", dims, index=dims.index("JobRole"), key="by_dim")
    horiz = df[by].nunique() > 6
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.rate_bar(df, by, horizontal=horiz, title=f"Attrition rate by {by}", height=420))
    with c2:
        ui.plot(ch.stacked_counts(df, by, horizontal=horiz, title=f"Headcount by {by}", height=420))
    assoc = an.categorical_association(df, [by])
    if not assoc.empty:
        row = assoc.iloc[0]
        verdict = "statistically significant" if row["p-value"] < 0.05 else "not statistically significant"
        cramers_v = row["Cramér's V"]
        st.caption(f"Chi-square test: χ² = {row['Chi²']}, p = {row['p-value']:.2g}, Cramér's V = {cramers_v} "
                   f"→ the link between **{by}** and attrition is {verdict}.")

    ui.section("Two-dimensional hotspots", "Attrition rate for every combination of two dimensions. Cells with too few employees are greyed out.")
    c1, c2, c3 = st.columns([1, 1, 1])
    r_dim = c1.selectbox("Rows", dims, index=dims.index("JobRole"), key="hm_r")
    c_dim = c2.selectbox("Columns", dims, index=dims.index("OverTime"), key="hm_c")
    min_n = c3.slider("Min. employees per cell", 3, 40, 10, key="hm_n")
    if r_dim == c_dim:
        st.info("Choose two different dimensions.")
    else:
        ui.plot(ch.heatmap_rate(df, r_dim, c_dim, min_n=min_n, height=max(380, 60 * df[r_dim].nunique() + 120)))

    ui.section("High-risk segments", "Combine up to three attributes to find the groups with the highest attrition.")
    c1, c2 = st.columns([3, 1])
    seg_cols = c1.multiselect("Segment by", dims, default=["JobRole", "OverTime"], max_selections=3, key="seg_cols")
    seg_min = c2.number_input("Min. employees", 5, 100, 15, key="seg_min")
    if seg_cols:
        seg = an.attrition_by(df, seg_cols)
        seg = seg[seg["Employees"] >= seg_min].sort_values("AttritionRate", ascending=False).head(25)
        seg = seg.rename(columns={"AttritionRate": "Attrition rate (%)"})
        seg["Attrition rate (%)"] = seg["Attrition rate (%)"].round(1)
        if seg.empty:
            st.info("No segment reaches the minimum size - lower the threshold.")
        else:
            ui.table(seg, column_config={"Attrition rate (%)": st.column_config.ProgressColumn(
                "Attrition rate (%)", format="%.1f", min_value=0, max_value=100)})

# --------------------------------------------------------------------------- #
# 3. Compensation
# --------------------------------------------------------------------------- #
with tabs[2]:
    gm = df.groupby("Gender")["MonthlyIncome"].median()
    if {"Female", "Male"} <= set(gm.index):
        st.caption(f"Median monthly income - Female: **{gm['Female']:,.0f}** · Male: **{gm['Male']:,.0f}** "
                   f"({(gm['Female'] / gm['Male'] - 1) * 100:+.1f}% difference, not controlled for job level).")
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.box_by_status(df, "MonthlyIncome", title="Monthly income - leavers vs stayers"))
    with c2:
        ui.plot(ch.rate_bar(df, "SalarySlab", title="Attrition rate by salary slab"))
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.mean_bar(df, "JobRole", "MonthlyIncome", title="Average monthly income by job role", height=400))
    with c2:
        ui.plot(ch.grouped_mean_bar(df, "JobLevel", "MonthlyIncome", "Gender",
                                    title="Average monthly income by job level and gender", height=400))
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.scatter_status(df, "TotalWorkingYears", "MonthlyIncome",
                                  title="Income vs total working years", height=420))
    with c2:
        ui.plot(ch.rate_bar(df, "StockOptionLevel", title="Attrition rate by stock-option level", height=420))
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.rate_bar(df, "PercentSalaryHike", title="Attrition rate by last salary hike (%)", min_n=5))
    with c2:
        ui.plot(ch.box_by_status(df, "PercentSalaryHike", x="Department", title="Salary hike (%) by department"))

# --------------------------------------------------------------------------- #
# 4. Satisfaction
# --------------------------------------------------------------------------- #
with tabs[3]:
    ui.section("Engagement scorecard", "Average rating (1 = low, 4 = high). Red cells are pain points.")
    g_dim = st.selectbox("Group by", ["Department", "JobRole", "Gender", "AgeGroup", "MaritalStatus", "OverTime", "Status"],
                         key="sat_group")
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.avg_heatmap(df, g_dim, SAT_METRICS, height=420))
    with c2:
        ui.plot(ch.score_rate_lines(df, SAT_METRICS, height=420))

    ui.section("Rating distribution", "Share of employees giving each rating.")
    c1, c2 = st.columns(2)
    metric = c1.selectbox("Metric", SAT_METRICS, index=1, key="dist_metric")
    group = c2.selectbox("Split by", ["Department", "JobRole", "Gender", "AgeGroup", "OverTime", "Status"], key="dist_group")
    ui.plot(ch.dist_100(df, group, metric, height=max(340, 55 * df[group].nunique() + 120)))

    c1, c2 = st.columns(2)
    with c1:
        ui.section("Overtime × work-life balance")
        ui.plot(ch.heatmap_rate(df, "OverTime", "WorkLifeBalance_Label", min_n=5, height=320))
    with c2:
        ui.section("Travel & commute")
        ui.plot(ch.rate_bar(df, "BusinessTravel", title="Attrition rate by business travel", height=320))
    ui.plot(ch.rate_bar(df, "DistanceBand", title="Attrition rate by distance from home", height=340))

# --------------------------------------------------------------------------- #
# 5. Career & tenure
# --------------------------------------------------------------------------- #
with tabs[4]:
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.hist_by_status(df, "YearsAtCompany", nbins=20, title="Years at company - leavers vs stayers"))
    with c2:
        ui.plot(ch.rate_bar(df, "TenureBand", title="Attrition rate by tenure band"))
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.rate_bar(df, "YearsSinceLastPromotion", title="Attrition rate by years since last promotion", min_n=5))
    with c2:
        ui.plot(ch.rate_bar(df, "NumCompaniesWorked", title="Attrition rate by number of previous employers", min_n=5))
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.rate_bar(df, "JobLevel", title="Attrition rate by job level"))
    with c2:
        ui.plot(ch.rate_bar(df, "TrainingTimesLastYear", title="Attrition rate by trainings last year", min_n=5))
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(ch.stacked_counts(df, "EducationField", horizontal=True, title="Headcount by education field"))
    with c2:
        ui.plot(ch.rate_bar(df, "Education_Label", title="Attrition rate by education level"))

# --------------------------------------------------------------------------- #
# 6. Drivers
# --------------------------------------------------------------------------- #
with tabs[5]:
    st.caption("Statistical view of what is associated with attrition. Associations are **not** proof of causation.")
    fi, auc, auc_sd = get_importance(df_all)
    num_cols = an.numeric_features(df)
    c1, c2 = st.columns(2)
    with c1:
        sp = an.numeric_association(df, num_cols)
        if sp.empty:
            st.info("Not enough variation in the current selection.")
        else:
            ui.plot(ch.spearman_bar(sp))
    with c2:
        if fi is None:
            st.info("Too few leavers in the dataset to fit a model.")
        else:
            ui.plot(ch.importance_bar(fi))
            st.caption(f"Random forest fitted on the full cleaned dataset · 5-fold cross-validated ROC-AUC = "
                       f"**{auc:.2f} ± {auc_sd:.2f}** (0.5 = random guessing).")

    ui.section("Correlation matrix", "Pick the numeric variables to compare (AttritionFlag: 1 = left).")
    pool = num_cols + ["AttritionFlag"]
    default = [c for c in ["Age", "MonthlyIncome", "JobLevel", "TotalWorkingYears", "YearsAtCompany", "YearsInCurrentRole",
                           "YearsSinceLastPromotion", "YearsWithCurrManager", "DistanceFromHome", "JobSatisfaction",
                           "WorkLifeBalance", "AttritionFlag"] if c in pool]
    chosen = st.multiselect("Variables", pool, default=default, key="corr_cols")
    if len(chosen) >= 2:
        ui.plot(ch.corr_heatmap(df[chosen].corr(), height=max(420, 42 * len(chosen) + 120)))
    else:
        st.info("Select at least two variables.")

    ui.section("Significance of categorical factors", "Chi-square test of independence against attrition.")
    cat = an.categorical_association(df, an.CAT_FEATURES + ["AgeGroup", "SalarySlab", "TenureBand", "DistanceBand"])
    if not cat.empty:
        cat["p-value"] = cat["p-value"].map(lambda p: f"{p:.2g}")
        ui.table(cat)

# --------------------------------------------------------------------------- #
# 7. Data quality
# --------------------------------------------------------------------------- #
with tabs[6]:
    ui.section("Cleaning summary", "Everything that was changed between the raw file and the data used in this dashboard.")
    m = st.columns(5)
    m[0].metric("Rows", f"{log['rows_after']:,}", f"-{log['rows_before'] - log['rows_after']} vs raw", delta_color="off")
    m[1].metric("Duplicates removed", log["duplicates_removed"])
    m[2].metric("Missing cells filled", log["cells_imputed"])
    m[3].metric("Columns", log["cols_after"], f"{log['cols_after'] - log['cols_before']:+d} vs raw", delta_color="off")
    m[4].metric("Zero-variance dropped", len(log["dropped_columns"]))
    ui.table(log["steps"])

    c1, c2 = st.columns(2)
    with c1:
        ui.section("Business-rule validation")
        ui.table(log["validity"])
    with c2:
        if log["missing_before"]:
            ui.section("Missing values in the raw file")
            ui.plot(ch.missing_bar(log["missing_before"]))
        else:
            st.success("The raw file had no missing values.")

    ui.section("Outlier screening", "IQR rule (1.5×). Flagged values were reviewed and kept - they are plausible for HR data.")
    ui.table(log["outliers"])

    with st.expander("📖 Data dictionary (cleaned dataset)"):
        dd = pd.DataFrame({
            "Column": df_all.columns,
            "Type": [str(t) for t in df_all.dtypes],
            "Unique values": [df_all[c].nunique() for c in df_all.columns],
            "Example": [str(df_all[c].iloc[0]) for c in df_all.columns],
        })
        ui.table(dd)
        st.caption("Rating labels (e.g. 1-4 → Low…Very High) follow the standard IBM HR data dictionary - an assumption, "
                   "since the source file only holds the numeric codes.")

    c1, c2, _ = st.columns([1, 1, 2])
    c1.download_button("⬇ Cleaned dataset (CSV)", to_csv(df_all), "HR_Analytics_cleaned.csv", "text/csv")
    c2.download_button("⬇ Cleaned dataset (Excel)", to_xlsx(df_all), "HR_Analytics_cleaned.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --------------------------------------------------------------------------- #
# 8. Explorer
# --------------------------------------------------------------------------- #
with tabs[7]:
    ui.section("Data explorer", f"{len(df):,} employees match the sidebar filters.")
    default_cols = ["EmpID", "Age", "Department", "JobRole", "Gender", "MonthlyIncome", "OverTime", "YearsAtCompany",
                    "JobSatisfaction", "Attrition"]
    cols_sel = st.multiselect("Columns to show", list(df.columns), default=[c for c in default_cols if c in df.columns],
                              key="explorer_cols")
    view = df[cols_sel] if cols_sel else df
    ui.table(view)
    c1, c2, _ = st.columns([1, 1, 2])
    c1.download_button("⬇ Filtered data (CSV)", to_csv(df), "HR_filtered.csv", "text/csv")
    c2.download_button("⬇ Filtered data (Excel)", to_xlsx(df), "HR_filtered.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with st.expander("Summary statistics"):
        st.dataframe(df[an.numeric_features(df)].describe().T.round(2))

    ui.section("Build your own chart")
    num_all = an.numeric_features(df)
    cat_all = ["Department", "JobRole", "Gender", "MaritalStatus", "OverTime", "BusinessTravel", "AgeGroup",
               "SalarySlab", "TenureBand", "EducationField", "Status"]
    c1, c2, c3, c4 = st.columns(4)
    kind = c1.selectbox("Chart type", ["Scatter", "Box", "Histogram", "Bar (average)"], key="cc_kind")
    x_opts = num_all + cat_all if kind in ("Scatter", "Histogram") else cat_all + num_all
    x = c2.selectbox("X axis", x_opts, key="cc_x")
    y = c3.selectbox("Y axis (numeric)", num_all, index=num_all.index("MonthlyIncome"), key="cc_y",
                     disabled=(kind == "Histogram"))
    color = c4.selectbox("Colour by", ["None", "Status", "Department", "Gender", "OverTime", "JobRole", "MaritalStatus"],
                         index=1, key="cc_color")
    try:
        ui.plot(ch.custom_chart(df, kind, x, None if kind == "Histogram" else y, color))
    except Exception as exc:
        st.info(f"That combination can't be drawn: {exc}")

st.caption("Built with Streamlit & Plotly · all figures are computed from the cleaned dataset and respond to the sidebar filters.")
