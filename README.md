# NYC Warehouse Sales: Queens, Brooklyn, Bronx

This project downloads NYC Department of Finance (DOF) property sales for the
Bronx, Brooklyn and Queens, keeps warehouse sales (building class `E*`) of
$500,000 or more from the last 3 years, works out price per gross square foot,
and summarizes median $/SF and sale count by neighborhood and year.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m warehouse_sales.main
```

Outputs, written to `output/`:

| File | What it is |
|---|---|
| `warehouse_sales.csv` | One row per qualifying sale, including `price_per_gsf` |
| `summary_by_neighborhood_year.csv` | Borough / neighborhood / year with `sale_count`, `sales_with_sf`, `median_price_per_gsf`, `median_sale_price` |
| `summary_wide.csv` | The same numbers with one row per neighborhood and one column per year |

The summary is also printed in the terminal.

## How it works, step by step

### Step 0: Settings (`warehouse_sales/config.py`)
All the adjustable values are in this file: the boroughs, the `E` prefix, the
$500k minimum, the 3-year lookback, and the download URLs. To change a rule,
edit it here.

### Step 1: Download (`download.py`)
DOF publishes two kinds of Excel files for each borough:

- **Rolling sales**: the most recent 12 months.
- **Annualized sales**: one file for each completed calendar year.

One file can't cover 3 years, so the script downloads the rolling file plus
the last 4 annual files. It fetches one extra year because the 3-year window
usually starts partway through a year. Files are saved in `data/raw/` and
reused on later runs; use `--refresh` to download them again. If a year isn't
published yet, or DOF has moved a file, the script prints a warning and keeps
going.

### Step 2: Load (`load.py`, `pdf_reader.py`)
The loader reads `.xlsx`, `.xls` and `.pdf` files. DOF files are sometimes
passed around as PDFs printed from the spreadsheet. A PDF has no cells, only
characters at x/y positions, so `pdf_reader.py` rebuilds the table. It finds
the header row on each page and works out where each column starts and ends
from the header positions (Excel centers each header in its cell). Then it
places every character in its column. Column positions differ between
boroughs' PDFs, so they are worked out for each page. On the Nov 2025 –
Oct 2026 files, the row counts matched an independent `pdftotext` count
exactly: 26,507 for Queens, 23,044 for Brooklyn and 6,507 for the Bronx.

For Excel files:
DOF formats these spreadsheets for people to read: they have title rows above
the real column headers, and the number of those rows changes between files.
For each file the loader:
1. reads the sheet as plain text,
2. finds the header row by looking for the cell "SALE PRICE",
3. cleans up the header text (extra spaces, line breaks, mixed case),
4. keeps the columns we need and gives them short names, such as
   `gross_sqft` and `sale_price`,
5. records which file each row came from in `source_file`.

It then stacks all the files into one table.

### Step 3: Clean, filter, calculate (`transform.py`)
These steps run in order, and each one logs how many rows it kept:

- **3a. Fix data types.** Turns `"$1,250,000"` into the number 1250000 and
  text dates into real dates.
- **3b. Remove duplicates.** The rolling file overlaps the latest annual
  file, so some sales appear twice. Two rows count as the same sale when they
  share the parcel (borough + block + lot), the address, the sale date and
  the price. The address matters because co-op apartments in one building
  share a block and lot, and only the apartment number tells them apart.
- **3c. 3-year window.** Keeps sales from the 3 years ending on the most
  recent sale in the data. The window is tied to the data rather than to
  today's date, so a publishing delay doesn't shorten it. Use `--end-date`
  to pick the end date yourself.
- **3d. Warehouses only.** Keeps rows whose *building class at time of
  sale* starts with `E`: E1 fireproof, E2 contractor's, E7 self-storage,
  E9 miscellaneous.
- **3e. $500k minimum.** Drops cheaper sales, which are mostly not true
  market deals: $0 or $10 transfers between related parties, partial
  interests, and similar.
- **3f. Merge portfolio deals.** When several lots sell together, DOF lists
  the *total* price on every lot. Lots on the **same block** that sell on
  the same date for the same price become one sale: the price is counted
  once and the gross SF of the lots is added together. `parcels_in_sale`
  says how many lots were combined. For example, a $28M Jamaica deal had
  been showing up as three sales at $5,333–$53,333/SF; merged, it is one
  sale at $1,023/SF.
- **3g. Price per gross SF.** `price_per_gsf = sale_price / gross_sqft`.
  When gross SF is 0 or blank, `price_per_gsf` is left empty instead of
  dividing by zero. Those sales stay in the CSV and in `sale_count`, but
  they are left out of the median. Comparing `sales_with_sf` with
  `sale_count` shows how many sales the median actually uses.
  It also adds `gsf_to_land_ratio` (building SF ÷ lot SF). A value well
  below 0.5 means a small building on a big lot, so the buyer is mostly
  paying for land and $/SF of building looks inflated. Those sales are kept
  but are worth checking.

### Step 4: Summarize (`summarize.py`)
Groups the sales by borough, neighborhood and sale year, then calculates the
count and the **median** $/SF. The median is the middle value, so a few
strange deals barely move it. An average can be pulled far off by a single
bad record.

### Step 5: Write outputs (`main.py`)
Writes the three CSVs and prints the summary.

## Things to watch when reading the results

- **Partial years.** The first and last years in the window are only partly
  covered, so their sale counts are lower than a full year's would be.
- **Portfolio sales across blocks.** Step 3f only merges deals within one
  block. A portfolio that spans blocks, or that includes non-warehouse lots
  such as a parking lot, is not fully merged.
- **Small samples.** A neighborhood with 1 or 2 sales in a year gives a
  median that is really just one deal. Always read the median next to
  `sale_count`.
- **DOF data is raw.** Gross SF can be wrong or missing, especially on older
  buildings.

## Command-line options

```
--refresh        re-download files that are already in data/raw/
--skip-download  use only the files already in data/raw/ (no internet needed)
--end-date DATE  end the 3-year window on DATE (YYYY-MM-DD)
--raw-dir/--out-dir  change the input and output folders
```

If DOF changes a URL, download the files yourself from the
[DOF Rolling Sales page](https://www.nyc.gov/site/finance/property/property-rolling-sales-data.page)
and the Annualized Sales page, save them in `data/raw/` with names such as
`rolling_queens.xlsx` and `annual_2025_queens.xlsx`, and run with `--skip-download`.

## Tests

```bash
python -m pytest
```
The tests build small fake DOF spreadsheets that include title rows,
duplicates, cheap sales, non-warehouse classes and a 0-SF record, then check
that each step handles them correctly.
