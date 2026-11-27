"""
STEP 2 — Load the spreadsheets into one table.

The DOF files are made for people, not programs:
  * There are a few title rows above the real column headers, and how many
    has changed between years.
  * Header text varies a little (extra spaces, line breaks, e.g.
    "SALE\\nPRICE", or "BUILDING CLASS AT TIME OF SALE" vs "... OF SALE ").

So for each file we find the header row by looking for the row that contains
"SALE PRICE", clean the header text, and rename the columns we need to
short snake_case names.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# The columns we keep: cleaned DOF header -> our name.
COLUMN_MAP = {
    "BOROUGH": "borough",
    "NEIGHBORHOOD": "neighborhood",
    "BUILDING CLASS CATEGORY": "building_class_category",
    "BLOCK": "block",
    "LOT": "lot",
    "BUILDING CLASS AT TIME OF SALE": "building_class",
    "ADDRESS": "address",
    "ZIP CODE": "zip_code",
    "LAND SQUARE FEET": "land_sqft",
    "GROSS SQUARE FEET": "gross_sqft",
    "YEAR BUILT": "year_built",
    "SALE PRICE": "sale_price",
    "SALE DATE": "sale_date",
}


def _clean_header(text) -> str:
    """'  Sale\\nPrice ' -> 'SALE PRICE'"""
    return re.sub(r"\s+", " ", str(text)).strip().upper()


def _find_header_row(raw: pd.DataFrame) -> int:
    """Return the index of the first row (of the first 30) with 'SALE PRICE'."""
    for i in range(min(30, len(raw))):
        if "SALE PRICE" in {_clean_header(v) for v in raw.iloc[i].tolist()}:
            return i
    raise ValueError("could not find a header row containing 'SALE PRICE'")


def read_dof_file(path: Path) -> pd.DataFrame:
    """Read one DOF sales file (.xlsx, .xls or .pdf) into a tidy DataFrame."""
    if path.suffix.lower() == ".pdf":
        # PDFs printed from the spreadsheet: see pdf_reader.py
        from .pdf_reader import read_pdf
        df = read_pdf(path)
    else:
        # Read with no header and everything as text; types get fixed later
        # in transform.py, which keeps this step simple and predictable.
        raw = pd.read_excel(path, header=None, dtype=str)
        hdr = _find_header_row(raw)
        df = raw.iloc[hdr + 1:].copy()
        df.columns = raw.iloc[hdr].tolist()
    df.columns = [_clean_header(c) for c in df.columns]

    missing = [c for c in COLUMN_MAP if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}")

    df = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    df = df.dropna(how="all")                 # blank rows at the bottom
    df["source_file"] = path.name             # keep where each row came from
    log.info("loaded   %-28s %7d rows", path.name, len(df))
    return df


def load_all(paths: list[Path]) -> pd.DataFrame:
    """Read every file and stack them into one DataFrame."""
    if not paths:
        raise SystemExit("No input files. Check the download step / data/raw/.")
    return pd.concat([read_dof_file(p) for p in paths], ignore_index=True)
