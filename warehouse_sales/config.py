"""
STEP 0 — Configuration.

All the "knobs" live here so the rest of the code has no magic numbers.
"""

# Boroughs we want. The key is how DOF spells the borough in its file names;
# the value is the borough code DOF uses inside the data (1=Manhattan,
# 2=Bronx, 3=Brooklyn, 4=Queens, 5=Staten Island).
BOROUGHS = {
    "bronx": 2,
    "brooklyn": 3,
    "queens": 4,
}

# Building classes starting with "E" are warehouses:
#   E1 = fireproof warehouse, E2 = contractor's warehouse,
#   E7 = self-storage warehouse, E9 = miscellaneous warehouse.
BUILDING_CLASS_PREFIX = "E"

# Drop sales below this price. Very low prices are usually not arm's-length
# deals: transfers between related parties, $0 / $10 deeds, partial interests.
MIN_SALE_PRICE = 500_000

# How far back to look, counted back from the most recent sale in the data.
LOOKBACK_YEARS = 3

# DOF publishes two kinds of files:
#   * "Rolling sales": the most recent 12 months, one file per borough.
#   * "Annualized sales": one file per borough per finished calendar year.
# To cover 3 years we need the rolling file plus the last few annual files.
BASE = "https://www.nyc.gov/assets/finance/downloads/pdf/rolling_sales"
ROLLING_URL = BASE + "/rollingsales_{boro}.xlsx"
# DOF has used both .xlsx and .xls over the years, so we try each.
ANNUAL_URLS = [
    BASE + "/annualized-sales/{year}/{year}_{boro}.xlsx",
    BASE + "/annualized-sales/{year}/{year}_{boro}.xls",
]

RAW_DIR = "data/raw"
OUTPUT_DIR = "output"
