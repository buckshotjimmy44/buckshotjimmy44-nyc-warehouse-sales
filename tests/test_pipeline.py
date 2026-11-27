import pandas as pd
import pytest

from warehouse_sales import load, summarize, transform
from tests.make_fixtures import build


@pytest.fixture
def sales(tmp_path):
    build(tmp_path)
    raw = load.load_all(sorted(tmp_path.glob("*.xlsx")))
    return transform.run_all(raw)


def test_filters(sales):
    assert sales["building_class"].str.startswith("E").all()
    assert (sales["sale_price"] >= 500_000).all()
    # 2022 sale is outside the 3-year window; duplicate removed
    assert len(sales) == 5
    assert sales.sale_date.min() > pd.Timestamp("2023-07-01")


def test_price_per_sf(sales):
    lic = sales[(sales.block == 100) & (sales.lot == "1")].iloc[0]
    assert lic.price_per_gsf == 300.0
    zero_sf = sales[(sales.block == 100) & (sales.lot == "3")].iloc[0]
    assert pd.isna(zero_sf.price_per_gsf)


def test_summary(sales):
    s = summarize.summarize(sales).set_index(["neighborhood", "sale_year"])
    lic = s.loc[("LONG ISLAND CITY", 2026)]
    assert lic.sale_count == 3 and lic.sales_with_sf == 2
    assert lic.median_price_per_gsf == 275.0   # median of 300 and 250
    assert s.loc[("MASPETH", 2025)].sale_count == 2
    assert s.loc[("MASPETH", 2025)].median_price_per_gsf == 300.0  # 200 & 400


def test_portfolio_sales_are_merged():
    df = pd.DataFrame({
        "borough": [4, 4, 4], "block": [10, 10, 99], "lot": [1, 2, 5],
        "address": ["A", "B", "C"], "building_class": ["E1", "E9", "E1"],
        "neighborhood": ["X"] * 3, "sale_date": pd.to_datetime(["2026-01-01"] * 3),
        "sale_price": [3_000_000] * 3, "gross_sqft": [5000, 1000, 6000],
        "land_sqft": [1, 1, 1], "source_file": ["f"] * 3,
    })
    out = transform.combine_portfolio_sales(df).set_index("block")
    assert len(out) == 2                     # block 99 is a separate deal
    assert out.loc[10, "gross_sqft"] == 6000 and out.loc[10, "parcels_in_sale"] == 2
    assert out.loc[10, "lot"] == "1; 2"
