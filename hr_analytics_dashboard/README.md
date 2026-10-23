# 👥 HR Analytics Dashboard (Streamlit)

An interactive, cleaned and presentation-ready analysis of employee attrition built from `HR_Analytics.xlsx`.

## Quick start

```bash
# 1. (optional) create a virtual env, then install dependencies
pip install -r requirements.txt

# 2. launch the dashboard
streamlit run app.py
```

Or just double-click / run the launcher: **`run_app.bat`** (Windows) or **`./run_app.sh`** (macOS/Linux) -
it creates a virtual environment, installs the requirements and starts the app at <http://localhost:8501>.

Requires Python 3.9+.

## What's inside

```
hr_analytics_dashboard/
├── app.py                  # Streamlit dashboard (8 tabs)
├── clean_data.py           # Standalone cleaning script -> data/HR_Analytics_cleaned.*
├── requirements.txt
├── run_app.bat / run_app.sh
├── .streamlit/config.toml  # colour theme
├── data/
│   ├── HR_Analytics.xlsx           # raw input
│   ├── HR_Analytics_cleaned.csv    # cleaned output
│   ├── HR_Analytics_cleaned.xlsx   # cleaned data + cleaning log + validation + outliers
│   └── cleaning_log.csv
├── utils/
│   ├── cleaning.py         # cleaning pipeline (returns cleaned df + full audit log)
│   ├── analysis.py         # KPIs, auto-insights, chi-square / Spearman / random-forest drivers
│   ├── charts.py           # all Plotly chart builders
│   └── ui.py               # theme CSS, KPI cards, version-safe Streamlit wrappers
└── tests/test_cleaning.py  # sanity tests for the cleaning pipeline
```

## Dashboard tabs

| Tab | What you get |
|---|---|
| 📊 **Overview** | Auto-generated key takeaways, workforce status, attrition by department/role, headcount treemap, age distribution |
| 🔥 **Attrition** | Break attrition down by any of 22 dimensions, 2-D hotspot heatmap, ranked high-risk segments, chi-square significance |
| 💰 **Compensation** | Income of leavers vs stayers, salary slabs, pay by role / level / gender, stock options, salary hikes |
| 😊 **Satisfaction** | Engagement scorecard, attrition vs rating, rating distributions, overtime × work-life balance, travel & commute |
| 🧭 **Career & Tenure** | Tenure bands, promotion stagnation, job-hopping, training, education |
| 🧠 **Drivers** | Spearman correlations, random-forest feature importance (cross-validated AUC), correlation matrix, significance tests |
| 🧹 **Data Quality** | Full cleaning log, validation rules, missing-value chart, outlier screening, data dictionary, cleaned-data download |
| 🔎 **Explorer** | Browse/export filtered data (CSV/Excel), summary stats, and a build-your-own chart tool |

**Sidebar filters** (department, job role, gender, overtime, age group, marital status, travel, salary slab, age and income
ranges) update every KPI, chart and table. You can also upload another HR file with the same columns.

## Data-cleaning summary (raw 1,480 × 38  →  clean 1,470 × 47)

| Issue found | Treatment |
|---|---|
| 7 exact duplicate rows | Removed |
| 3 more `EmpID`s repeated with conflicting `YearsWithCurrManager` | Kept first record per employee |
| `BusinessTravel` had `TravelRarely` **and** `Travel_Rarely` (8 rows) | Merged into `Travel_Rarely` |
| 57 missing `YearsWithCurrManager` | Imputed with the median for employees with the same `YearsInCurrentRole` (capped at tenure); flagged in `YearsWithCurrManager_Imputed` |
| `EmployeeCount`, `Over18`, `StandardHours` constant | Dropped (no information) |
| Derived fields checked (`AgeGroup`, `SalarySlab`) | Rebuilt from Age / MonthlyIncome - all matched |
| Business rules (tenure ≤ career, age ≥ 18 …) | 0 violations |
| 712 IQR "outliers" across 11 numeric columns | Reviewed and **kept** (plausible values) |
| Added | `AttritionFlag`, `Status`, `TenureBand`, `DistanceBand`, and `*_Label` columns for the 1-4/1-5 rating scales |

Re-run the cleaning alone with `python clean_data.py`.

## Assumptions to be aware of

* **Rating labels** (e.g. 1-4 → Low / Medium / High / Very High, Education 1-5 → Below College … Doctor) follow the
  standard IBM HR-analytics data dictionary; the Excel file only contains the numeric codes. Numeric columns are kept as well.
* Income has no currency in the source, so none is displayed.
* The driver model is exploratory: associations are **not** proof of causation.
* "Gender pay" comparisons are descriptive and not controlled for role, level or tenure.
