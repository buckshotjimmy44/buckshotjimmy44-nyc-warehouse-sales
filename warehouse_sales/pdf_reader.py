"""
STEP 2 (PDF variant): read a DOF sales file that was printed to PDF.

DOF's sales spreadsheets are sometimes shared as PDFs printed from Excel.
A PDF has no cells. It only says "draw this character at position (x, y)",
so we have to rebuild the table ourselves:

1. Group the characters on each page into lines by their vertical position.
2. Find the column-header block: the line that starts with "BOROUGH", plus
   the lines just above it. Headers such as "GROSS / SQUARE / FEET" are
   stacked over several lines.
3. Work out where each column starts and ends. Excel centers each header
   in its cell, so a cell's right edge is as far from the header's center
   as its left edge: right = 2 * center - left. Starting at the page
   margin, we apply that rule one column at a time. After each step we
   nudge the boundary into the nearest vertical strip that no data character
   touches, which stops small errors from building up across the page.
   Characters are used instead of words because the PDF prints some columns
   so close together that they read as one word; for example, year built
   1945 and tax class 1 come out as "19451".
4. Place every character in its column and join the characters into cell text.

Column positions differ between boroughs' PDFs, so they are computed for
each page rather than hard-coded.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

LINE_TOLERANCE = 2.0    # chars whose tops differ by less than this share a line
HEADER_HEIGHT = 12.0    # header text sits within this many points above "BOROUGH"
WORD_GAP = 4.0          # header words closer than this belong to one column


def _lines(chars):
    """Group chars into lines (top to bottom); each line is sorted left to right."""
    lines, current, top = [], [], None
    for c in sorted(chars, key=lambda c: (c["top"], c["x0"])):
        if top is None or c["top"] - top > LINE_TOLERANCE:
            if current:
                lines.append(sorted(current, key=lambda c: c["x0"]))
            current, top = [], c["top"]
        current.append(c)
    if current:
        lines.append(sorted(current, key=lambda c: c["x0"]))
    return lines


def _words(line):
    """Split a line of chars into (text, x0, x1) words, breaking on gaps."""
    words, buf = [], []
    for c in line:
        if c["text"].isspace() or (buf and c["x0"] - buf[-1]["x1"] > WORD_GAP):
            if buf:
                words.append(buf)
            buf = [] if c["text"].isspace() else [c]
        else:
            buf.append(c)
    if buf:
        words.append(buf)
    return [("".join(c["text"] for c in w), w[0]["x0"], w[-1]["x1"]) for w in words]


def _cell_text(chars) -> str:
    """Join chars into text, adding a space where there is a visible gap."""
    out, prev = [], None
    for c in sorted(chars, key=lambda c: c["x0"]):
        if prev is not None and c["x0"] - prev["x1"] > 1.0 and not c["text"].isspace():
            out.append(" ")
        out.append(c["text"])
        prev = c
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _parse_page(chars) -> tuple[list[str], list[list[str]]]:
    lines = _lines([c for c in chars if c["text"].strip() or c["text"] == " "])
    hdr_idx = next((i for i, ln in enumerate(lines)
                    if _cell_text(ln[:7]).startswith("BOROUGH")), None)
    if hdr_idx is None:
        return [], []

    # Column groups from the bottom header line ("BOROUGH  NEIGHBORHOOD ...")
    groups = []  # [x0, x1]
    for _, x0, x1 in _words(lines[hdr_idx]):
        if groups and x0 - groups[-1][1] <= WORD_GAP:
            groups[-1][1] = x1
        else:
            groups.append([x0, x1])
    centers = [(a + b) / 2 for a, b in groups]

    # Data lines: below the header, starting with a borough digit at the margin
    data = [ln for ln in lines[hdr_idx + 1:]
            if ln[0]["text"] in "12345" and ln[0]["x0"] < groups[0][1]]

    # Find which x positions have ink on any data line
    ink = sorted({x for ln in data for c in ln if not c["text"].isspace()
                  for x in range(int(c["x0"]), int(c["x1"]) + 1)})
    inked = set(ink)

    def snap(x: float) -> float:
        """Move x to the nearest position with no ink (searching up to 8pt)."""
        for d in range(0, 9):
            for cand in (x + d, x - d):
                if int(cand) not in inked:
                    return float(int(cand))
        return x

    # Walk left to right: each cell is centered on its header
    cuts, left = [], min(ink) - 1.0
    for center in centers[:-1]:
        left = snap(2 * center - left)
        cuts.append(left)
    def col_of(x):
        return sum(x > cut for cut in cuts)

    # Full header text: words from the header lines, grouped by column
    names = [[] for _ in centers]
    hdr_top = lines[hdr_idx][0]["top"]
    for ln in lines[:hdr_idx + 1]:
        if ln[0]["top"] < hdr_top - HEADER_HEIGHT:
            continue
        for text, x0, x1 in _words(ln):
            names[col_of((x0 + x1) / 2)].append(text)
    headers = [" ".join(n) for n in names]

    rows = []
    for ln in data:
        cells = [[] for _ in centers]
        for c in ln:
            cells[col_of((c["x0"] + c["x1"]) / 2)].append(c)
        rows.append([_cell_text(cell) for cell in cells])
    return headers, rows


def _parse_range(args):
    """Worker: parse pages [start, stop) of one PDF."""
    import pdfplumber
    path, start, stop = args
    out = []
    with pdfplumber.open(path) as pdf:
        for i in range(start, stop):
            page = pdf.pages[i]
            chars = [{k: c[k] for k in ("text", "x0", "x1", "top")} for c in page.chars]
            out.append(_parse_page(chars))
            page.flush_cache()
    return out


def read_pdf(path: Path, workers: int = 4) -> pd.DataFrame:
    """Read a DOF sales PDF and return it as text columns named like the Excel file."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
    step = max(1, -(-n // (workers * 4)))
    chunks = [(str(path), s, min(s + step, n)) for s in range(0, n, step)]
    with ProcessPoolExecutor(workers) as pool:
        pages = [p for chunk in pool.map(_parse_range, chunks) for p in chunk]

    frames, expected = [], None
    for page_no, (headers, rows) in enumerate(pages, 1):
        if not headers:
            log.warning("%s page %d: no header found, skipped", path.name, page_no)
            continue
        expected = expected or headers
        if headers != expected:
            raise ValueError(f"{path.name} page {page_no}: columns {headers} "
                             f"differ from page 1 {expected}")
        frames.append(pd.DataFrame(rows, columns=headers))
    df = pd.concat(frames, ignore_index=True).replace("", pd.NA)
    log.info("parsed   %-28s %4d pages %7d rows", path.name, n, len(df))
    return df
