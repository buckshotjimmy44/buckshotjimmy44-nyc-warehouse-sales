"""Build small fake DOF spreadsheets shaped like the real ones (for testing)."""
from pathlib import Path

import pandas as pd

HEADERS = ["BOROUGH", "NEIGHBORHOOD", "BUILDING CLASS CATEGORY",
           "TAX CLASS AT PRESENT", "BLOCK", "LOT", "BUILDING CLASS AT PRESENT",
           "ADDRESS", "ZIP CODE", "LAND SQUARE FEET", "GROSS SQUARE FEET",
           "YEAR BUILT", "BUILDING CLASS AT TIME OF SALE", "SALE\nPRICE", "SALE DATE"]


def row(boro, hood, block, lot, cls, gsf, price, date):
    return [boro, hood, "30 WAREHOUSES" if cls.startswith("E") else "OTHER", "4",
            block, lot, cls, f"{lot} TEST ST", "11101", "5000", gsf, "1960",
            cls, price, date]


def write(path: Path, rows, title_rows=4):
    titles = [["Queens Rolling Sales File"] + [""] * 14] * title_rows
    pd.DataFrame(titles + [HEADERS] + rows).to_excel(path, header=False, index=False)


def build(dirpath: Path):
    dirpath.mkdir(parents=True, exist_ok=True)
    write(dirpath / "rolling_queens.xlsx", [
        row(4, "LONG ISLAND CITY", 100, 1, "E1", "10,000", "$3,000,000", "2026-03-01"),
        row(4, "LONG ISLAND CITY", 100, 2, "E9", "20000", "5000000", "2026-06-15"),
        row(4, "LONG ISLAND CITY", 100, 3, "E1", "0", "2000000", "2026-07-01"),    # no SF
        row(4, "LONG ISLAND CITY", 100, 4, "E1", "8000", "10", "2026-07-01"),      # too cheap
        row(4, "MASPETH", 200, 1, "K1", "8000", "4000000", "2026-02-01"),          # not E
        row(4, "MASPETH", 200, 2, "E2", "12000", "2400000", "2025-12-01"),         # dup below
    ])
    write(dirpath / "annual_2025_queens.xlsx", [
        row(4, "MASPETH", 200, 2, "E2", "12000", "2400000", "2025-12-01"),         # dup above
        row(4, "MASPETH", 200, 3, "E7", "40000", "16000000", "2025-04-01"),
    ], title_rows=6)  # different number of title rows, like real files
    write(dirpath / "annual_2022_queens.xlsx", [
        row(4, "MASPETH", 200, 9, "E1", "10000", "1000000", "2022-01-05"),         # too old
    ])


if __name__ == "__main__":
    build(Path("data/sample"))
