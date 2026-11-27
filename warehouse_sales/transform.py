"""
STEP 3 — Clean, filter and calculate $/SF.

Each step is its own small function so you can test it or swap it out.
"""
from __future__ import annotations

import logging

import pandas as pd

from . import config

log = logging.getLogger(__name__)


def _to_number(s: pd.Series) -> pd.Series:
    """'$1,250,000' / '1250000' / ' - ' -> 1250000.0 / NaN"""
    cleaned = s.astype(str).str.replace(r"[$,\s]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def clean_types(df: pd.DataFrame) -> pd.DataFrame:
    """3a. Turn text columns into numbers and dates; tidy up the text."""
    df = df.copy()
    # Borough is normally a code (2/3/4); map a spelled-out name just in case.
    names = {k.upper(): v for k, v in config.BOROUGHS.items()}
    df["borough"] = df["borough"].astype(str).str.strip().str.upper().replace(names)
    for col in ["borough", "block", "lot", "zip_code", "land_sqft",
                "gross_sqft", "year_built", "sale_price"]:
        df[col] = _to_number(df[col])
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    for col in ["neighborhood", "building_class", "building_class_category",
                "address"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["building_class"] = df["building_class"].str.upper()
    df["neighborhood"] = df["neighborhood"].str.upper()
    return df


def drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """3b. Remove sales that appear in two files.

    The rolling file (last 12 months) overlaps the latest annual file, so the
    same sale can show up twice. A sale is the same parcel (borough/block/lot)
    and address selling on the same date for the same price. The address
    matters because co-op apartments in one building share a block and lot;
    the apartment number in the address is what tells them apart.
    """
    key = ["borough", "block", "lot", "address", "sale_date", "sale_price"]
    before = len(df)
    df = df.drop_duplicates(subset=key, keep="first")
    log.info("dedupe: removed %d duplicate rows", before - len(df))
    return df


def filter_date_window(df: pd.DataFrame, years: int = config.LOOKBACK_YEARS,
                       end: pd.Timestamp | None = None) -> pd.DataFrame:
    """3c. Keep only sales in the last `years` years.

    The window ends at the latest sale date in the data (or `end`), so it
    follows whatever DOF has published rather than today's date.
    """
    end = end or df["sale_date"].max()
    start = end - pd.DateOffset(years=years)
    keep = df["sale_date"].gt(start) & df["sale_date"].le(end)
    log.info("date window %s to %s: kept %d of %d",
             start.date(), end.date(), keep.sum(), len(df))
    return df[keep]


def filter_warehouses(df: pd.DataFrame,
                      prefix: str = config.BUILDING_CLASS_PREFIX) -> pd.DataFrame:
    """3d. Keep building classes starting with 'E' (warehouses)."""
    keep = df["building_class"].str.startswith(prefix)
    log.info("building class %s*: kept %d of %d", prefix, keep.sum(), len(df))
    return df[keep]


def filter_min_price(df: pd.DataFrame,
                     minimum: float = config.MIN_SALE_PRICE) -> pd.DataFrame:
    """3e. Drop sales under the minimum price (and missing prices)."""
    keep = df["sale_price"].ge(minimum)
    log.info("price >= $%s: kept %d of %d", f"{minimum:,.0f}", keep.sum(), len(df))
    return df[keep]


def combine_portfolio_sales(df: pd.DataFrame) -> pd.DataFrame:
    """3f. Merge multi-lot deals into one sale.

    When several lots are sold together, DOF lists the *total* deal price on
    every lot. If we left that alone, a $28M three-lot deal would count as
    three $28M sales and its $/SF would be worked out on only one lot's
    floor area. Lots on the same block that sell on the same date for the
    same price are treated as one deal: the price is counted once and the
    square footage is added up across the lots.
    """
    key = ["borough", "block", "sale_date", "sale_price"]
    text = lambda s: "; ".join(dict.fromkeys(s.astype(str)))  # unique, in order
    agg = {col: "first" for col in df.columns if col not in key}
    agg.update(lot=text, address=text, building_class=text, source_file="first",
               gross_sqft=lambda s: s.sum(min_count=1),
               land_sqft=lambda s: s.sum(min_count=1))
    out = (df.assign(lot=df["lot"].astype("Int64"))
             .groupby(key, as_index=False, dropna=False).agg(agg))
    out["parcels_in_sale"] = df.groupby(key, dropna=False).size().values
    log.info("portfolio sales: %d lots merged into %d multi-lot deals",
             out.loc[out.parcels_in_sale > 1, "parcels_in_sale"].sum(),
             (out.parcels_in_sale > 1).sum())
    return out


def add_price_per_sf(df: pd.DataFrame) -> pd.DataFrame:
    """3g. price_per_gsf = sale_price / gross_sqft.

    Some records have gross square feet of 0 or blank. Dividing by those
    would give infinity or nonsense, so $/SF is left empty (NaN) there.
    Those sales stay in the CSV and in the sale count, but they are left
    out of the median.
    """
    df = df.copy()
    gsf = df["gross_sqft"].where(df["gross_sqft"] > 0)
    df["price_per_gsf"] = (df["sale_price"] / gsf).round(2)
    # Building SF / lot SF. Well below ~0.5 means a small building on a big
    # lot, so the price is mostly paying for land and $/SF of building runs high.
    df["gsf_to_land_ratio"] = (gsf / df["land_sqft"].where(df["land_sqft"] > 0)).round(2)
    df["sale_year"] = df["sale_date"].dt.year
    df["borough_name"] = df["borough"].map(
        {code: name.title() for name, code in config.BOROUGHS.items()})
    log.info("$/SF calculated for %d of %d sales (others lack gross SF)",
             df["price_per_gsf"].notna().sum(), len(df))
    return df


def run_all(df: pd.DataFrame, end: pd.Timestamp | None = None) -> pd.DataFrame:
    """Run steps 3a to 3g in order."""
    df = clean_types(df)
    df = drop_duplicates(df)
    df = filter_date_window(df, end=end)
    df = filter_warehouses(df)
    df = filter_min_price(df)
    df = combine_portfolio_sales(df)
    df = add_price_per_sf(df)
    return df.sort_values(["borough", "neighborhood", "sale_date"]).reset_index(drop=True)
