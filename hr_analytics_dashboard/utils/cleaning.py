"""
Data-cleaning pipeline for the HR Analytics dataset.

`clean_hr_data(raw_df)` returns `(clean_df, log)` where `log` documents every
transformation (used by the "Data Quality" tab and by `clean_data.py`).

Nothing in here depends on Streamlit, so it can be unit-tested and reused.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
# Standard IBM HR-dataset data dictionary (ASSUMPTION: this file follows it).
_SAT = {1: "Low", 2: "Medium", 3: "High", 4: "Very High"}
ORDINAL_LABELS: dict[str, dict[int, str]] = {
    "Education": {1: "Below College", 2: "College", 3: "Bachelor", 4: "Master", 5: "Doctor"},
    "EnvironmentSatisfaction": _SAT,
    "JobInvolvement": _SAT,
    "JobSatisfaction": _SAT,
    "RelationshipSatisfaction": _SAT,
    "WorkLifeBalance": {1: "Bad", 2: "Good", 3: "Better", 4: "Best"},
    "PerformanceRating": {1: "Low", 2: "Good", 3: "Excellent", 4: "Outstanding"},
}

AGE_GROUP_ORDER = ["18-25", "26-35", "36-45", "46-55", "55+"]
SALARY_SLAB_ORDER = ["Upto 5k", "5k-10k", "10k-15k", "15k+"]
TENURE_ORDER = ["0-1", "2-5", "6-10", "11-20", "20+"]
DISTANCE_ORDER = ["Near (1-5)", "Mid (6-15)", "Far (16+)"]
TRAVEL_ORDER = ["Non-Travel", "Travel_Rarely", "Travel_Frequently"]

# Sort orders used by charts / filters (key = column name)
ORDERS: dict[str, list[str]] = {
    "AgeGroup": AGE_GROUP_ORDER,
    "SalarySlab": SALARY_SLAB_ORDER,
    "TenureBand": TENURE_ORDER,
    "DistanceBand": DISTANCE_ORDER,
    "BusinessTravel": TRAVEL_ORDER,
    "OverTime": ["No", "Yes"],
    "Status": ["Stayed", "Left"],
}
for _col, _map in ORDINAL_LABELS.items():
    ORDERS[f"{_col}_Label"] = list(_map.values())

# Columns the dashboard needs in order to work
REQUIRED_COLUMNS = [
    "EmpID", "Age", "Attrition", "BusinessTravel", "Department", "JobRole", "Gender",
    "MaritalStatus", "MonthlyIncome", "OverTime", "YearsAtCompany", "YearsInCurrentRole",
    "YearsSinceLastPromotion", "YearsWithCurrManager", "TotalWorkingYears", "JobLevel",
    "PercentSalaryHike", "StockOptionLevel", "DistanceFromHome", "NumCompaniesWorked",
    "TrainingTimesLastYear", "WorkLifeBalance", "EnvironmentSatisfaction", "JobSatisfaction",
    "RelationshipSatisfaction", "JobInvolvement", "PerformanceRating", "Education",
    "EducationField",
]

OUTLIER_COLUMNS = [
    "Age", "MonthlyIncome", "TotalWorkingYears", "YearsAtCompany", "YearsInCurrentRole",
    "YearsSinceLastPromotion", "YearsWithCurrManager", "NumCompaniesWorked",
    "TrainingTimesLastYear", "PercentSalaryHike", "DistanceFromHome",
]

TRAVEL_FIX = {
    "travelrarely": "Travel_Rarely",
    "travelfrequently": "Travel_Frequently",
    "nontravel": "Non-Travel",
}


def validate_columns(raw: pd.DataFrame) -> None:
    cols = [str(c).strip() for c in raw.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        raise ValueError(f"The file is missing required column(s): {', '.join(missing)}")


# --------------------------------------------------------------------------- #
# Main pipeline
# --------------------------------------------------------------------------- #
def clean_hr_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    validate_columns(raw)
    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    steps: list[dict] = []

    def log_step(step: str, detail: str, impact: str) -> None:
        steps.append({"#": len(steps) + 1, "Step": step, "What was done & why": detail, "Impact": impact})

    rows_before, cols_before = df.shape
    missing_before = {c: int(v) for c, v in df.isna().sum().items() if v > 0}

    # 1 ── Whitespace ------------------------------------------------------- #
    changed = 0
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            try:
                new = df[c].str.strip()
            except AttributeError:
                continue
            changed += int((new.fillna("") != df[c].fillna("")).sum())
            df[c] = new
    log_step("Trim whitespace", "Stripped leading/trailing spaces from all text columns so identical values group together.",
             f"{changed} cells changed")

    # 2 ── Standardise BusinessTravel -------------------------------------- #
    key = df["BusinessTravel"].astype(str).str.lower().str.replace(r"[\s_\-]", "", regex=True)
    fixed = key.map(TRAVEL_FIX)
    new_bt = fixed.where(fixed.notna(), df["BusinessTravel"])
    n_fixed = int((new_bt != df["BusinessTravel"]).sum())
    df["BusinessTravel"] = new_bt
    log_step("Standardise categories",
             "`BusinessTravel` held both 'Travel_Rarely' and 'TravelRarely' for the same category - merged into 'Travel_Rarely'.",
             f"{n_fixed} rows relabelled")

    # 3 ── Duplicates ------------------------------------------------------- #
    n_exact = int(df.duplicated().sum())
    df = df.drop_duplicates()
    n_id = int(df["EmpID"].duplicated().sum())
    df = df.drop_duplicates(subset="EmpID", keep="first").reset_index(drop=True)
    log_step("Remove exact duplicates", "Dropped rows that were identical in every column (keeping the first).",
             f"{n_exact} rows removed")
    log_step("Resolve duplicate employee IDs",
             "The same EmpID appeared more than once with conflicting values (e.g. different YearsWithCurrManager). "
             "An employee can only exist once, so the first record was kept.",
             f"{n_id} rows removed")

    # 4 ── Constant columns ------------------------------------------------- #
    const = [c for c in df.columns if df[c].nunique(dropna=True) <= 1 and c not in REQUIRED_COLUMNS]
    df = df.drop(columns=const)
    log_step("Drop zero-variance columns",
             "Columns with a single value carry no analytical information: " + (", ".join(f"`{c}`" for c in const) or "none") + ".",
             f"{len(const)} columns removed")

    # 5 ── Missing values --------------------------------------------------- #
    imputed_total = 0
    for c in [c for c in df.columns if df[c].isna().any()]:
        n_na = int(df[c].isna().sum())
        if c == "YearsWithCurrManager":
            grp = df.groupby("YearsInCurrentRole")[c].transform("median")
            filled = grp.fillna(df[c].median())
            filled = np.floor(filled + 0.5)  # round half up
            filled = np.minimum(filled, df["YearsAtCompany"])  # can't exceed company tenure
            df["YearsWithCurrManager_Imputed"] = df[c].isna()
            df[c] = df[c].fillna(filled)
            method = ("median of employees with the same `YearsInCurrentRole` (corr. ~0.7), capped at `YearsAtCompany`; "
                      "an `_Imputed` flag column keeps these rows identifiable")
        elif pd.api.types.is_numeric_dtype(df[c]):
            df[c] = df[c].fillna(df[c].median())
            method = "column median"
        else:
            df[c] = df[c].fillna(df[c].mode().iloc[0])
            method = "most frequent value"
        imputed_total += n_na
        log_step("Impute missing values", f"`{c}`: {n_na} blanks filled with {method}.", f"{n_na} cells filled")
    if imputed_total == 0:
        log_step("Impute missing values", "No missing values found after de-duplication.", "0 cells")

    # 6 ── Types ------------------------------------------------------------ #
    n_cast = 0
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_float_dtype(s) and s.notna().all() and (s % 1 == 0).all():
            df[c] = s.astype(int)
            n_cast += 1
    log_step("Fix data types", "Whole-number columns that were stored as decimals were converted to integers.",
             f"{n_cast} columns cast")

    # 7 ── Logical validation + derived-field repair ------------------------ #
    age_group = pd.cut(df["Age"], bins=[0, 25, 35, 45, 55, 200], labels=AGE_GROUP_ORDER).astype(str)
    slab = pd.cut(df["MonthlyIncome"], bins=[-np.inf, 5000, 10000, 15000, np.inf], labels=SALARY_SLAB_ORDER, right=False).astype(str)
    ag_mask = (df["AgeGroup"] != age_group) if "AgeGroup" in df else pd.Series(False, index=df.index)
    sl_mask = (df["SalarySlab"] != slab) if "SalarySlab" in df else pd.Series(False, index=df.index)
    df["AgeGroup"], df["SalarySlab"] = age_group, slab

    rules = [
        ("Age is at least 18", df["Age"] < 18, "Flag only"),
        ("YearsAtCompany <= TotalWorkingYears", df["YearsAtCompany"] > df["TotalWorkingYears"], "Flag only"),
        ("YearsInCurrentRole <= YearsAtCompany", df["YearsInCurrentRole"] > df["YearsAtCompany"], "Flag only"),
        ("YearsWithCurrManager <= YearsAtCompany", df["YearsWithCurrManager"] > df["YearsAtCompany"], "Flag only"),
        ("YearsSinceLastPromotion <= YearsAtCompany", df["YearsSinceLastPromotion"] > df["YearsAtCompany"], "Flag only"),
        ("MonthlyIncome > 0", df["MonthlyIncome"] <= 0, "Flag only"),
        ("Attrition is Yes/No", ~df["Attrition"].isin(["Yes", "No"]), "Flag only"),
        ("AgeGroup matches Age", ag_mask, "Recomputed"),
        ("SalarySlab matches MonthlyIncome", sl_mask, "Recomputed"),
    ]
    validity = pd.DataFrame(
        [{"Rule": r, "Violations": int(m.sum()), "Result": "✅ Pass" if m.sum() == 0 else "⚠️ Review", "Action": a if m.sum() else "-"}
         for r, m, a in rules]
    )
    log_step("Validate business rules",
             "Checked tenure/age/income consistency and rebuilt `AgeGroup` and `SalarySlab` directly from Age and MonthlyIncome.",
             f"{int(validity['Violations'].sum())} violations found")

    # 8 ── Outliers (report only) ------------------------------------------ #
    out_rows = []
    for c in [c for c in OUTLIER_COLUMNS if c in df.columns]:
        q1, q3 = df[c].quantile([0.25, 0.75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n = int(((df[c] < lo) | (df[c] > hi)).sum())
        out_rows.append({"Column": c, "Min": float(df[c].min()), "Max": float(df[c].max()),
                         "Lower fence": round(float(lo), 1), "Upper fence": round(float(hi), 1),
                         "Outliers": n, "% of rows": round(n / len(df) * 100, 1)})
    outliers = pd.DataFrame(out_rows)
    log_step("Outlier screening (IQR rule)",
             "Extreme values were reviewed but kept: they are plausible (e.g. 40-year careers, senior salaries) and removing them would bias attrition analysis.",
             f"{int(outliers['Outliers'].sum())} flagged, 0 removed")

    # 9 ── Feature engineering --------------------------------------------- #
    df["AttritionFlag"] = (df["Attrition"] == "Yes").astype(int)
    df["Status"] = np.where(df["AttritionFlag"] == 1, "Left", "Stayed")
    df["TenureBand"] = pd.cut(df["YearsAtCompany"], bins=[-1, 1, 5, 10, 20, 1000], labels=TENURE_ORDER).astype(str)
    df["DistanceBand"] = pd.cut(df["DistanceFromHome"], bins=[-1, 5, 15, 1000], labels=DISTANCE_ORDER).astype(str)
    for col, mapping in ORDINAL_LABELS.items():
        df[f"{col}_Label"] = df[col].map(mapping).fillna("Unknown")
    new_cols = ["AttritionFlag", "Status", "TenureBand", "DistanceBand"] + [f"{c}_Label" for c in ORDINAL_LABELS]
    log_step("Feature engineering",
             "Added readable fields: " + ", ".join(f"`{c}`" for c in new_cols) +
             ". Ordinal scores (1-4/1-5) are labelled using the standard IBM HR data dictionary (assumption).",
             f"{len(new_cols)} columns added")

    log = {
        "rows_before": rows_before, "rows_after": len(df),
        "cols_before": cols_before, "cols_after": df.shape[1],
        "duplicates_removed": n_exact + n_id,
        "dropped_columns": const,
        "missing_before": missing_before,
        "cells_imputed": imputed_total,
        "steps": pd.DataFrame(steps),
        "validity": validity,
        "outliers": outliers,
    }
    return df, log
