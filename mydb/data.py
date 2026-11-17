"""CSV loading, column detection, searching and output formatting.

This module has no GUI dependencies so it can be unit-tested headless.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field

# Header names we recognise automatically (compared after normalisation:
# lower-case, accents removed, only letters/digits kept).
PART_NUMBER_ALIASES = [
    "partnumber", "partno", "partnum", "pn", "part", "sku", "model",
    "modelnumber", "itemnumber", "item", "productcode", "code",
    "numerodeparte", "nodeparte", "numparte", "codigo", "modelo",
]
PRICE_ALIASES = [
    "price", "unitprice", "listprice", "netprice", "priceusd", "usd",
    "msrp", "cost", "unitcost", "precio", "preciounitario", "preciolista",
    "costo", "valor",
]

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def detect_column(headers: list[str], aliases: list[str]) -> str | None:
    """Return the header that best matches one of the aliases, or None."""
    norm = {h: normalise(h) for h in headers}
    for alias in aliases:  # exact match, in alias priority order
        for h, n in norm.items():
            if n == alias:
                return h
    for alias in aliases:  # partial match ("Precio Lista USD" -> precio)
        if len(alias) < 3:
            continue
        for h, n in norm.items():
            if alias in n:
                return h
    return None


def read_text(path: str) -> str:
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


@dataclass
class CsvDatabase:
    name: str
    path: str
    part_number_column: str | None = None  # None/"" = auto-detect
    price_column: str | None = None
    delimiter: str | None = None  # None/"" = auto-detect

    headers: list[str] = field(default_factory=list, init=False)
    rows: list[dict[str, str]] = field(default_factory=list, init=False)
    _haystack: list[str] = field(default_factory=list, init=False, repr=False)
    _mtime: float | None = field(default=None, init=False, repr=False)

    # ---------------------------------------------------------------- loading
    def load(self, force: bool = False) -> None:
        """(Re)load the CSV if it changed on disk since the last load."""
        mtime = os.path.getmtime(self.path)
        if not force and self._mtime == mtime:
            return
        text = read_text(self.path)
        delim = self.delimiter or sniff_delimiter(text[:20000])
        reader = csv.reader(io.StringIO(text), delimiter=delim)
        all_rows = [r for r in reader if any(cell.strip() for cell in r)]
        if not all_rows:
            self.headers, self.rows, self._haystack = [], [], []
            self._mtime = mtime
            return
        headers = [h.strip() or f"Column {i + 1}" for i, h in enumerate(all_rows[0])]
        rows = []
        for r in all_rows[1:]:
            r = [c.strip() for c in r] + [""] * (len(headers) - len(r))
            rows.append(dict(zip(headers, r)))
        self.headers = headers
        self.rows = rows
        self._haystack = [" ".join(r.values()).lower() for r in rows]
        self._mtime = mtime

    @property
    def pn_col(self) -> str | None:
        if self.part_number_column and self.part_number_column in self.headers:
            return self.part_number_column
        return detect_column(self.headers, PART_NUMBER_ALIASES)

    @property
    def price_col(self) -> str | None:
        if self.price_column and self.price_column in self.headers:
            return self.price_column
        return detect_column(self.headers, PRICE_ALIASES)

    # ---------------------------------------------------------------- search
    def search(self, query: str, limit: int = 500) -> tuple[list[int], int]:
        """Return (row indexes to show, total number of matches).

        Every whitespace-separated word must appear somewhere in the row
        (case-insensitive, any order). Rows whose part number starts with the
        query are listed first.
        """
        terms = query.lower().split()
        if not terms:
            return list(range(min(limit, len(self.rows)))), len(self.rows)
        hits = [i for i, hay in enumerate(self._haystack) if all(t in hay for t in terms)]
        pn = self.pn_col
        if pn:
            q = query.strip().lower()
            hits.sort(key=lambda i: 0 if self.rows[i].get(pn, "").lower().startswith(q) else 1)
        return hits[:limit], len(hits)


# -------------------------------------------------------------------- output
def format_part_number(db: CsvDatabase, row: dict[str, str]) -> str:
    col = db.pn_col
    return row.get(col, "") if col else ""


def format_price(db: CsvDatabase, row: dict[str, str]) -> str:
    col = db.price_col
    return row.get(col, "") if col else ""


def format_all(db: CsvDatabase, row: dict[str, str], style: str = "lines") -> str:
    """style: 'lines' (Header: value per line), 'tsv' (pastes as one Excel row
    with headers above), or 'json'."""
    if style == "tsv":
        return "\t".join(db.headers) + "\n" + "\t".join(row.get(h, "") for h in db.headers)
    if style == "json":
        return json.dumps({h: row.get(h, "") for h in db.headers}, ensure_ascii=False, indent=2)
    return "\n".join(f"{h}: {row.get(h, '')}" for h in db.headers)
