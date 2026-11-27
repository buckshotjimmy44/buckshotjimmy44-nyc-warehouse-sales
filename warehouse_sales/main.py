"""
Run the whole pipeline:

    python -m warehouse_sales.main

Options:
    --refresh       re-download files even if they are already in data/raw/
    --skip-download use whatever is already in data/raw/ (.xlsx, .xls or .pdf)
    --end-date      end the 3-year window on this date (default: latest sale)
"""
from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from . import config, download, load, summarize, transform


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--skip-download", action="store_true")
    ap.add_argument("--end-date", type=pd.Timestamp)
    ap.add_argument("--raw-dir", default=config.RAW_DIR)
    ap.add_argument("--out-dir", default=config.OUTPUT_DIR)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # STEP 1: download. The rolling file covers the latest 12 months; annual
    # files cover earlier calendar years. Going back LOOKBACK_YEARS + 1 years
    # makes sure the start of the window is covered (it can fall mid-year).
    this_year = date.today().year
    years = list(range(this_year - config.LOOKBACK_YEARS - 1, this_year))
    if args.skip_download:
        paths = sorted(p for p in Path(args.raw_dir).iterdir()
                       if p.suffix.lower() in (".xlsx", ".xls", ".pdf"))
    else:
        paths = download.download_all(years, args.raw_dir, args.refresh)

    # STEP 2: load and stack all files
    raw = load.load_all(paths)

    # STEP 3: clean, dedupe, filter, compute $/SF
    sales = transform.run_all(raw, end=args.end_date)

    # STEP 4: summarize
    summary = summarize.summarize(sales)
    wide = summarize.pivot_median(summary)

    # STEP 5: write outputs
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cols = ["borough_name", "neighborhood", "sale_year", "sale_date", "address",
            "zip_code", "block", "lot", "building_class", "building_class_category",
            "year_built", "parcels_in_sale", "land_sqft", "gross_sqft", "sale_price",
            "price_per_gsf", "gsf_to_land_ratio", "source_file"]
    sales[cols].to_csv(out / "warehouse_sales.csv", index=False,
                       date_format="%Y-%m-%d")
    summary.to_csv(out / "summary_by_neighborhood_year.csv", index=False)
    wide.to_csv(out / "summary_wide.csv", index=False)

    print(f"\n{len(sales):,} warehouse sales written to {out}/warehouse_sales.csv")
    print(f"Window: {sales.sale_date.min().date()} to {sales.sale_date.max().date()}\n")
    with pd.option_context("display.max_rows", 500, "display.width", 140):
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
