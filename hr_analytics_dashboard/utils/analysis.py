"""
Pure-pandas analysis helpers (no Streamlit / Plotly imports).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

# Columns that are identifiers / helper flags, never analysed as features
NON_FEATURE_COLS = {"EmployeeNumber", "AttritionFlag", "YearsWithCurrManager_Imputed"}
CAT_FEATURES = ["BusinessTravel", "Department", "EducationField", "Gender", "JobRole", "MaritalStatus", "OverTime"]


def numeric_features(df: pd.DataFrame) -> list[str]:
    cols = [c for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])
            and c not in NON_FEATURE_COLS and df[c].nunique() > 1]
    return cols


# --------------------------------------------------------------------------- #
# Core aggregations
# --------------------------------------------------------------------------- #
def attrition_by(df: pd.DataFrame, cols) -> pd.DataFrame:
    """Headcount, leavers and attrition rate (%) per group."""
    g = (df.groupby(cols)["AttritionFlag"].agg(Employees="size", Leavers="sum").reset_index())
    g["AttritionRate"] = g["Leavers"] / g["Employees"] * 100
    return g


def kpis(df: pd.DataFrame) -> dict:
    n = len(df)
    if n == 0:
        return {k: 0 for k in ["headcount", "leavers", "attrition_rate", "avg_income", "avg_tenure",
                               "overtime_share", "avg_job_sat", "avg_age"]}
    return {
        "headcount": n,
        "leavers": int(df["AttritionFlag"].sum()),
        "attrition_rate": df["AttritionFlag"].mean() * 100,
        "avg_income": df["MonthlyIncome"].mean(),
        "avg_tenure": df["YearsAtCompany"].mean(),
        "overtime_share": (df["OverTime"] == "Yes").mean() * 100,
        "avg_job_sat": df["JobSatisfaction"].mean(),
        "avg_age": df["Age"].mean(),
    }


# --------------------------------------------------------------------------- #
# Auto-generated insights
# --------------------------------------------------------------------------- #
def _ranked(df: pd.DataFrame, col: str, min_n: int) -> pd.DataFrame:
    g = attrition_by(df, col)
    return g[g["Employees"] >= min_n].sort_values("AttritionRate", ascending=False)


def build_insights(df: pd.DataFrame, min_n: int = 20) -> list[str]:
    """Plain-English takeaways computed from the *current selection*."""
    out: list[str] = []
    if len(df) < 30 or df["AttritionFlag"].sum() < 5:
        return ["The current selection is too small for reliable insights - widen the filters."]

    rate = df["AttritionFlag"].mean() * 100
    out.append(f"**{rate:.1f}%** of the {len(df):,} employees in view have left ({int(df['AttritionFlag'].sum())} leavers).")

    for col, label in [("JobRole", "job role"), ("Department", "department")]:
        r = _ranked(df, col, min_n)
        if len(r) >= 2:
            top, low = r.iloc[0], r.iloc[-1]
            out.append(f"Highest attrition {label}: **{top[col]}** at {top['AttritionRate']:.1f}% "
                       f"(lowest: {low[col]}, {low['AttritionRate']:.1f}%).")

    ot = attrition_by(df, "OverTime").set_index("OverTime")
    if {"Yes", "No"} <= set(ot.index) and ot.loc["Yes", "Employees"] >= min_n and ot.loc["No", "Employees"] >= min_n:
        a, b = ot.loc["Yes", "AttritionRate"], ot.loc["No", "AttritionRate"]
        if b > 0:
            out.append(f"Employees working overtime leave at **{a:.1f}%** vs {b:.1f}% for those who don't "
                       f"(**{a / b:.1f}x** higher).")

    ms = _ranked(df, "MaritalStatus", min_n)
    if len(ms) >= 2:
        out.append(f"**{ms.iloc[0]['MaritalStatus']}** employees show the highest attrition by marital status "
                   f"({ms.iloc[0]['AttritionRate']:.1f}%).")

    leavers, stayers = df[df["AttritionFlag"] == 1], df[df["AttritionFlag"] == 0]
    if len(leavers) >= 10 and len(stayers) >= 10:
        med_l, med_s = leavers["MonthlyIncome"].median(), stayers["MonthlyIncome"].median()
        if med_s > 0:
            out.append(f"Median monthly income of leavers is **{med_l:,.0f}** vs {med_s:,.0f} for stayers "
                       f"({(med_l / med_s - 1) * 100:+.0f}%).")
        early = (leavers["YearsAtCompany"] <= 3).mean() * 100
        out.append(f"**{early:.0f}%** of leavers departed within their first 3 years at the company.")
    return out


# --------------------------------------------------------------------------- #
# Statistical association with attrition
# --------------------------------------------------------------------------- #
def categorical_association(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Chi-square test + Cramer's V between each categorical column and attrition."""
    from scipy.stats import chi2_contingency
    rows = []
    for c in cols:
        ct = pd.crosstab(df[c], df["AttritionFlag"])
        if ct.shape[0] < 2 or ct.shape[1] < 2:
            continue
        chi2, p, _, _ = chi2_contingency(ct)
        v = math.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))
        rows.append({"Feature": c, "Cramér's V": round(v, 3), "Chi²": round(chi2, 1), "p-value": p,
                     "Significant (p<0.05)": "Yes" if p < 0.05 else "No"})
    return pd.DataFrame(rows).sort_values("Cramér's V", ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


def numeric_association(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Spearman correlation of each numeric column with the attrition flag."""
    from scipy.stats import spearmanr
    rows = []
    for c in cols:
        if df[c].nunique() < 2:
            continue
        rho, p = spearmanr(df[c], df["AttritionFlag"])
        rows.append({"Feature": c, "Spearman ρ": round(float(rho), 3), "p-value": float(p),
                     "Significant (p<0.05)": "Yes" if p < 0.05 else "No"})
    return pd.DataFrame(rows).sort_values("Spearman ρ").reset_index(drop=True) if rows else pd.DataFrame()


def feature_importance(df: pd.DataFrame, seed: int = 42):
    """
    Random-forest importance of each original feature for predicting attrition.
    Returns (importance_df, cv_auc_mean, cv_auc_std). Returns (None, None, None) if too few leavers.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_score

    y = df["AttritionFlag"].to_numpy()
    if y.sum() < 20 or (len(y) - y.sum()) < 20:
        return None, None, None

    num = numeric_features(df)
    cat = [c for c in CAT_FEATURES if c in df.columns]
    dummies = pd.get_dummies(df[cat], dtype=float)
    X = pd.concat([df[num].astype(float), dummies], axis=1)

    origin = {c: c for c in num}
    for d in dummies.columns:
        for c in cat:
            if d.startswith(c + "_"):
                origin[d] = c

    rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=5, class_weight="balanced",
                                random_state=seed, n_jobs=-1)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    auc = cross_val_score(rf, X, y, cv=cv, scoring="roc_auc")
    rf.fit(X, y)
    imp = pd.Series(rf.feature_importances_, index=X.columns).groupby(origin).sum().sort_values(ascending=False)
    fi = imp.rename("Importance").reset_index().rename(columns={"index": "Feature"})
    fi.columns = ["Feature", "Importance"]
    return fi, float(auc.mean()), float(auc.std())
