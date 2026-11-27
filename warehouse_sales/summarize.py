"""
STEP 4 — Summarize by neighborhood and year.

For each borough / neighborhood / sale year:
  * sale_count       : all warehouse sales >= $500k
  * sales_with_sf    : how many of those had a usable gross SF
  * median_price_per_gsf : median $/SF across sales_with_sf

We use the median, not the mean, because a handful of odd deals (a sale
with tiny listed SF, or a portfolio price repeated on every lot) can drag an
average a long way. The median is the middle value, so outliers barely move it.
"""
from __future__ import annotations

import pandas as pd


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["borough_name", "neighborhood", "sale_year"])
          .agg(sale_count=("sale_price", "size"),
               sales_with_sf=("price_per_gsf", "count"),  # count skips NaN
               median_price_per_gsf=("price_per_gsf", "median"),
               median_sale_price=("sale_price", "median"))
          .round({"median_price_per_gsf": 2, "median_sale_price": 0})
          .reset_index()
    )


def pivot_median(summary: pd.DataFrame) -> pd.DataFrame:
    """Wide view: one row per neighborhood, one column per year."""
    wide = summary.pivot_table(index=["borough_name", "neighborhood"],
                               columns="sale_year",
                               values=["median_price_per_gsf", "sale_count"])
    # Flatten ("sale_count", 2024) -> "2024_sale_count", grouped by year
    wide = wide.sort_index(axis=1, level=1)
    wide.columns = [f"{year}_{metric}" for metric, year in wide.columns]
    return wide.reset_index()
