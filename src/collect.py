"""Collect the document corpus and the market series.

Documents come from federalreserve.gov; the Board publishes its news listings as
JSON (``/json/ne-*.json``), and each record carries the release date *and time*,
which is what the one-day return window keys off. Press conference transcripts
are the exception -- they are PDFs at a date-keyed path with no feed entry.

Running ``python -m src.collect`` writes:

    data/docs/<doc_id>.txt        extracted plain text, one file per document
    data/interim/manifest.csv     one row per document (date, time, type, chair)
    data/market/market.csv        the four indicators plus the 3-month bill

Nothing under data/ is committed; this script rebuilds all of it.
"""

from __future__ import annotations

import datetime as dt
import html
import io
import json
import re
import time

import pandas as pd
import requests

from .config import (
    CHAIRS, DOC_DIR, FED, FEED_PRESS, FEED_SPEECHES, FEED_TESTIMONY,
    FRED_CSV, FRED_SERIES, INTERIM_DIR, JACKSON_HOLE_HINTS, MARKET_DIR,
    POLICY_SPEECH_KEYWORDS, PRESCONF_URL, REQUEST_PAUSE, SAMPLE_END,
    SAMPLE_START, USER_AGENT, YAHOO_SERIES, chair_for,
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
def _get(url: str) -> requests.Response:
    time.sleep(REQUEST_PAUSE)
    r = SESSION.get(url, timeout=60)
    r.raise_for_status()
    return r


def _feed(url: str) -> list[dict]:
    """A Board JSON listing. The files are served with a UTF-8 BOM."""
    return json.loads(_get(url).content.decode("utf-8-sig"))


def _parse_stamp(rec: dict) -> dt.datetime | None:
    """Release timestamp. The feeds use '9/17/2025 2:00:00 PM' (ET)."""
    try:
        return dt.datetime.strptime(rec["d"], "%m/%d/%Y %I:%M:%S %p")
    except (KeyError, ValueError):
        return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------
def _html_text(raw: bytes) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "lxml")
    # The Board wraps article bodies in #article or #content; footnotes, nav and
    # the "Last Update" block are stripped so they do not enter the word counts.
    node = soup.select_one("#article") or soup.select_one("#content") or soup
    for bad in node.select("nav, script, style, .footnotes, #lastUpdate, .pdf-link"):
        bad.decompose()
    return _clean(node.get_text(" "))


def _pdf_text(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    return _clean(" ".join(page.extract_text() or "" for page in reader.pages))


def _fetch_text(url: str) -> str:
    raw = _get(url).content
    return _pdf_text(raw) if url.lower().endswith(".pdf") else _html_text(raw)


_MINUTES_HREF = re.compile(r"/monetarypolicy/fomcminutes\d{8}[a-z]?\.htm", re.I)


def _fetch_minutes_text(url: str) -> str:
    """The minutes press release is only an announcement; follow it to the text.

    The release at /newsevents/pressreleases/monetary*.htm is a ~130-word notice
    linking to the minutes themselves at /monetarypolicy/fomcminutes<meeting>.htm,
    which is the ~10,000-word document we actually want to score.
    """
    announcement = _get(url).content.decode("utf-8", "replace")
    match = _MINUTES_HREF.search(announcement)
    if match is None:
        raise ValueError(f"no minutes link found on {url}")
    return _fetch_text(FED + match.group(0))


# ---------------------------------------------------------------------------
# Document selection
# ---------------------------------------------------------------------------
_STATEMENT_RE = re.compile(r"federal reserve issues fomc statement", re.I)
_MINUTES_RE = re.compile(r"minutes of the federal open market committee", re.I)


def _speaker_chair(rec: dict) -> str | None:
    """The Chair who gave this speech/testimony, or None if not a Chair item.

    Matched on the URL slug rather than the title so that a speech *about*
    a Chair is not picked up, and so that Powell's pre- and post-Chair remarks
    are separated by the date filter below.
    """
    slug = rec.get("l", "").rsplit("/", 1)[-1].lower()
    for chair, keys in CHAIRS.items():
        if any(slug.startswith(k) for k in keys):
            return chair
    return None


def _is_policy_speech(rec: dict) -> bool:
    """Monetary-policy-relevant Chair speech? See the scope note in config.py."""
    blob = f"{rec.get('t', '')} {rec.get('lo', '')}".lower()
    if any(h in blob for h in JACKSON_HOLE_HINTS):
        return True
    return any(k in blob for k in POLICY_SPEECH_KEYWORDS)


def gather_records() -> pd.DataFrame:
    """One row per in-scope document, before any text is downloaded."""
    rows: list[dict] = []

    # --- statements and minutes, from the Monetary Policy press releases -----
    for rec in _feed(FEED_PRESS):
        if rec.get("pt") != "Monetary Policy":
            continue
        stamp = _parse_stamp(rec)
        if stamp is None:
            continue
        title = _clean(rec.get("t", ""))
        if _STATEMENT_RE.search(title):
            doc_type = "statement"
        elif _MINUTES_RE.search(title):
            # Board *discount rate* minutes are a different document and are
            # excluded; only FOMC minutes match this pattern.
            doc_type = "minutes"
        else:
            continue
        rows.append({"stamp": stamp, "doc_type": doc_type, "title": title,
                     "url": FED + rec["l"], "source": "press_feed"})

    # --- Chair testimony: semiannual Monetary Policy Report only ------------
    for rec in _feed(FEED_TESTIMONY):
        stamp = _parse_stamp(rec)
        chair = _speaker_chair(rec)
        if stamp is None or chair is None:
            continue
        if "semiannual" not in rec.get("t", "").lower():
            continue
        rows.append({"stamp": stamp, "doc_type": "speech",
                     "title": _clean(rec.get("t", "")),
                     "url": FED + rec["l"], "source": "testimony_feed"})

    # --- Chair policy speeches ---------------------------------------------
    for rec in _feed(FEED_SPEECHES):
        stamp = _parse_stamp(rec)
        chair = _speaker_chair(rec)
        if stamp is None or chair is None:
            continue
        # Only remarks given *as Chair*: the speaker field carries the title in
        # office at the time, which is how Powell's and Warsh's governor-era
        # speeches are dropped.
        if "chair" not in rec.get("s", "").lower():
            continue
        if not _is_policy_speech(rec):
            continue
        rows.append({"stamp": stamp, "doc_type": "speech",
                     "title": _clean(rec.get("t", "")),
                     "url": FED + rec["l"], "source": "speech_feed"})

    df = pd.DataFrame(rows)

    # --- press conference transcripts, keyed to each statement date ---------
    conf = []
    for stamp in df.loc[df.doc_type == "statement", "stamp"]:
        url = PRESCONF_URL.format(ymd=stamp.strftime("%Y%m%d"))
        if SESSION.head(url, timeout=30, allow_redirects=True).status_code == 200:
            # The transcript is published a few hours after the statement, so it
            # is stamped at the press conference itself (14:30 ET).
            conf.append({"stamp": stamp.replace(hour=14, minute=30),
                         "doc_type": "speech",
                         "title": f"FOMC press conference transcript, {stamp:%B %d, %Y}",
                         "url": url, "source": "presconf_pdf"})
        time.sleep(REQUEST_PAUSE)
    df = pd.concat([df, pd.DataFrame(conf)], ignore_index=True)

    df["date"] = df.stamp.dt.date
    df = df[(df.date >= SAMPLE_START) & (df.date <= SAMPLE_END)]
    df["chair"] = df.date.map(chair_for)
    df["doc_id"] = (
        df.stamp.dt.strftime("%Y%m%d") + "_" + df.doc_type + "_"
        + df.groupby([df.stamp.dt.strftime("%Y%m%d"), "doc_type"]).cumcount().astype(str)
    )
    return df.sort_values("stamp").reset_index(drop=True)


def download_documents(records: pd.DataFrame) -> pd.DataFrame:
    """Fetch and cache the text of each record. Cached files are not re-fetched."""
    texts, words, failed = [], [], []
    for row in records.itertuples():
        path = DOC_DIR / f"{row.doc_id}.txt"
        if path.exists():
            text = path.read_text(encoding="utf-8")
        else:
            fetch = _fetch_minutes_text if row.doc_type == "minutes" else _fetch_text
            try:
                text = fetch(row.url)
            except Exception as exc:                      # noqa: BLE001
                failed.append((row.doc_id, row.url, repr(exc)))
                texts.append(None)
                words.append(0)
                continue
            path.write_text(text, encoding="utf-8")
        texts.append(str(path.relative_to(DOC_DIR.parent.parent)))
        words.append(len(text.split()))

    out = records.copy()
    out["path"] = texts
    out["n_words"] = words
    if failed:
        print(f"  {len(failed)} document(s) failed to download:")
        for doc_id, url, exc in failed:
            print(f"    {doc_id}  {url}  {exc}")
    return out[out.path.notna()].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------
def download_market(start: dt.date = SAMPLE_START,
                    end: dt.date = SAMPLE_END) -> pd.DataFrame:
    """Daily levels of the four indicators plus the 3-month bill control.

    DXY, T10Y2Y, DGS1 and DGS3MO are levels; GROWTH_VALUE is a cumulative return
    index built from IWF minus IWN daily total returns, so that a one-day change
    in it *is* the growth-minus-value return spread for that day.
    """
    import yfinance as yf

    cache = MARKET_DIR / "market.csv"
    if cache.exists():
        return pd.read_csv(cache, index_col=0, parse_dates=True)

    px = yf.download(list(YAHOO_SERIES.values()), start=str(start),
                     end=str(end + dt.timedelta(days=1)),
                     auto_adjust=True, progress=False)["Close"]
    px = px.rename(columns={v: k for k, v in YAHOO_SERIES.items()}).sort_index()

    spread = px["IWF"].pct_change() - px["IWN"].pct_change()
    market = pd.DataFrame({
        "DXY": px["DXY"],
        # Index level: differencing it returns the daily growth-value spread.
        "GROWTH_VALUE": spread.fillna(0).cumsum() * 100,
    })

    for name, sid in FRED_SERIES.items():
        csv = _get(FRED_CSV.format(sid=sid)).content.decode("utf-8")
        s = pd.read_csv(io.StringIO(csv), index_col=0, parse_dates=True).iloc[:, 0]
        market[name] = pd.to_numeric(s, errors="coerce")   # FRED marks holidays '.'

    market = market.loc[str(start):str(end)].sort_index()
    market.to_csv(cache)
    return market


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    print("Gathering document records from federalreserve.gov ...")
    records = gather_records()
    print(f"  {len(records)} records in scope ({SAMPLE_START} to {SAMPLE_END})")

    print("Downloading document text ...")
    manifest = download_documents(records)
    manifest.to_csv(INTERIM_DIR / "manifest.csv", index=False)
    print(f"  {len(manifest)} documents cached in {DOC_DIR}")

    print("Downloading market data ...")
    market = download_market()
    print(f"  {len(market)} trading days, {list(market.columns)}")

    print("\nDocuments by type and Chair:")
    print(pd.crosstab(manifest.doc_type, manifest.chair, margins=True))
    print("\nWarsh-era documents:")
    warsh = manifest[manifest.chair == "Warsh"]
    for row in warsh.itertuples():
        print(f"  {row.stamp:%Y-%m-%d %H:%M}  {row.doc_type:<10} "
              f"{row.n_words:>6,}w  {row.title[:70]}")


if __name__ == "__main__":
    main()
