"""Run with:  python -m pytest -q   (or just: python tests/test_cleaning.py)"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.cleaning import clean_hr_data  # noqa: E402
from utils import analysis as an  # noqa: E402

RAW = pd.read_excel(Path(__file__).resolve().parents[1] / "data" / "HR_Analytics.xlsx")
DF, LOG = clean_hr_data(RAW)


def test_no_duplicates_or_nulls():
    assert DF["EmpID"].is_unique
    assert DF.isna().sum().sum() == 0


def test_row_counts():
    assert LOG["rows_before"] == 1480 and LOG["rows_after"] == 1470


def test_business_travel_standardised():
    assert set(DF["BusinessTravel"]) == {"Travel_Rarely", "Travel_Frequently", "Non-Travel"}


def test_constant_columns_dropped():
    for c in ["EmployeeCount", "Over18", "StandardHours"]:
        assert c not in DF.columns


def test_imputed_values_are_logical():
    assert (DF["YearsWithCurrManager"] <= DF["YearsAtCompany"]).all()
    assert DF["YearsWithCurrManager_Imputed"].sum() == 57


def test_attrition_flag_consistent():
    assert (DF["AttritionFlag"] == (DF["Attrition"] == "Yes")).all()


def test_kpis():
    k = an.kpis(DF)
    assert k["headcount"] == 1470 and 0 < k["attrition_rate"] < 100


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
