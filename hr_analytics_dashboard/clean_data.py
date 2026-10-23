"""
Standalone cleaning script (no Streamlit needed).

    python clean_data.py                         # uses data/HR_Analytics.xlsx
    python clean_data.py path/to/file.xlsx       # custom input

Writes to ./data/ :
    HR_Analytics_cleaned.csv / .xlsx   - the cleaned dataset (the same one the dashboard uses)
    cleaning_log.csv                   - step-by-step record of every transformation
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from utils.cleaning import clean_hr_data

BASE = Path(__file__).parent
DATA = BASE / "data"


def main(src: str | None = None) -> None:
    path = Path(src) if src else DATA / "HR_Analytics.xlsx"
    raw = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
    df, log = clean_hr_data(raw)

    DATA.mkdir(exist_ok=True)
    df.to_csv(DATA / "HR_Analytics_cleaned.csv", index=False)
    with pd.ExcelWriter(DATA / "HR_Analytics_cleaned.xlsx", engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="HR_Cleaned")
        log["steps"].to_excel(writer, index=False, sheet_name="Cleaning_Log")
        log["validity"].to_excel(writer, index=False, sheet_name="Validation")
        log["outliers"].to_excel(writer, index=False, sheet_name="Outliers")
    log["steps"].to_csv(DATA / "cleaning_log.csv", index=False)

    print(f"Raw     : {log['rows_before']:,} rows x {log['cols_before']} columns")
    print(f"Cleaned : {log['rows_after']:,} rows x {log['cols_after']} columns")
    print(f"Duplicates removed: {log['duplicates_removed']} | Missing cells filled: {log['cells_imputed']} "
          f"| Columns dropped: {', '.join(log['dropped_columns']) or 'none'}")
    print(log["steps"][["Step", "Impact"]].to_string(index=False))
    print(f"\nSaved to {DATA}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
