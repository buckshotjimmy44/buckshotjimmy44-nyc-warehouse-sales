"""
STEP 1 — Download the raw DOF spreadsheets.

For each borough we fetch:
  * the rolling-sales file (last 12 months), and
  * the annualized file for each prior calendar year we need.

Files are cached in data/raw/, so a second run does not download them again.
(Use --refresh to force a fresh download.) If DOF has not published a year
yet, or has moved the file, we warn and carry on. You can also download the
files by hand and drop them into data/raw/ with the names this script expects.
"""
from __future__ import annotations

import logging
from pathlib import Path

import requests

from . import config

log = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (warehouse-sales-research script)"}


def _fetch(url: str, dest: Path, refresh: bool) -> bool:
    """Download url to dest. Returns True if the file is now on disk."""
    if dest.exists() and not refresh:
        log.info("cached   %s", dest.name)
        return True
    try:
        resp = requests.get(url, headers=HEADERS, timeout=120)
    except requests.RequestException as exc:
        log.warning("failed   %s (%s)", url, exc)
        return False
    if resp.status_code != 200 or len(resp.content) < 1000:
        # nyc.gov sometimes answers a missing file with a small HTML page,
        # so we also check that we actually got a sizeable file.
        log.warning("missing  %s (HTTP %s)", url, resp.status_code)
        return False
    dest.write_bytes(resp.content)
    log.info("saved    %s (%.1f MB)", dest.name, len(resp.content) / 1e6)
    return True


def download_all(years: list[int], raw_dir: str = config.RAW_DIR,
                 refresh: bool = False) -> list[Path]:
    """Download the rolling file plus each annual file. Returns local paths."""
    out = Path(raw_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for boro in config.BOROUGHS:
        # 1a. Rolling sales (the latest 12 months)
        dest = out / f"rolling_{boro}.xlsx"
        if _fetch(config.ROLLING_URL.format(boro=boro), dest, refresh):
            paths.append(dest)

        # 1b. Annualized sales for each earlier calendar year
        for year in years:
            for template in config.ANNUAL_URLS:
                ext = template.rsplit(".", 1)[1]
                dest = out / f"annual_{year}_{boro}.{ext}"
                if _fetch(template.format(year=year, boro=boro), dest, refresh):
                    paths.append(dest)
                    break  # got this year; skip the other extensions
            else:
                log.warning("no annual file found for %s %s", boro, year)
    return paths
