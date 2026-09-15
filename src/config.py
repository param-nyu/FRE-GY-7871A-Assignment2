"""Central configuration: sample window, document scope, market series, paths.

Everything the rest of the pipeline treats as a fixed choice lives here, so the
scoping decisions the assignment asks us to document are readable in one place.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOC_DIR = DATA / "docs"           # raw + extracted document text
MARKET_DIR = DATA / "market"      # cached price / yield series
INTERIM_DIR = DATA / "interim"    # manifests, scored panels
OUTPUT_DIR = ROOT / "outputs"     # tables and figures that go into the report

for _d in (DOC_DIR, MARKET_DIR, INTERIM_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Sample window and the Chair split
# ---------------------------------------------------------------------------
SAMPLE_START = dt.date(2018, 2, 1)     # Powell sworn in 2018-02-05
WARSH_START = dt.date(2026, 5, 22)     # Warsh sworn in 2026-05-22
SAMPLE_END = dt.date(2026, 9, 15)      # data cut-off: the day before the Sept meeting

NEXT_MEETING = dt.date(2026, 9, 16)    # the meeting this report forecasts


def chair_for(d: dt.date) -> str:
    """Which Chair was in office on `d`. Documents are assigned by release date."""
    return "Warsh" if d >= WARSH_START else "Powell"


# ---------------------------------------------------------------------------
# Federal Reserve sources
# ---------------------------------------------------------------------------
FED = "https://www.federalreserve.gov"

# The Board publishes its news listings as JSON. Each record carries the release
# date AND time, which is what the one-day return window keys off.
FEED_PRESS = f"{FED}/json/ne-press.json"
FEED_SPEECHES = f"{FED}/json/ne-speeches.json"
FEED_TESTIMONY = f"{FED}/json/ne-testimony.json"

# Post-meeting press conference transcripts are not in any JSON feed; they are
# PDFs at a date-keyed path (the date is the second day of the meeting).
PRESCONF_URL = FED + "/mediacenter/files/FOMCpresconf{ymd}.pdf"

USER_AGENT = (
    "FRE-GY-7871A coursework (NYU Tandon); contact shahparam87@gmail.com"
)
REQUEST_PAUSE = 0.4   # seconds between requests to federalreserve.gov

# --- Speech scope -----------------------------------------------------------
# Scoping decision (documented in Table 1 notes and AI_USE.md): we do NOT
# collect every speech either Chair gave. The "speech" document type is
# restricted to monetary-policy-relevant Chair communication, namely
#   (1) semiannual Monetary Policy Report testimony to Congress,
#   (2) FOMC post-meeting press conference transcripts,
#   (3) major policy speeches by the sitting Chair -- Jackson Hole and
#       speeches whose title/venue is about the economic or policy outlook.
# Governor speeches, supervision/regulation testimony, and ceremonial remarks
# are excluded.
POLICY_SPEECH_KEYWORDS = [
    "economic outlook", "monetary policy", "inflation", "policy outlook",
    "economy", "price stability", "labor market", "interest rate",
    "financial stability", "policy framework",
]
JACKSON_HOLE_HINTS = ["jackson hole", "economic policy symposium", "kansas city"]

CHAIRS = {
    "Powell": ["powell"],
    "Warsh": ["warsh"],
}

# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------
# The four indicators, plus the 3-month bill used as the control in Table 3.
YAHOO_SERIES = {
    "DXY": "DX-Y.NYB",
    "IWF": "IWF",      # Russell 1000 Growth
    "IWN": "IWN",      # Russell 2000 Value
}
FRED_SERIES = {
    "T10Y2Y": "T10Y2Y",    # 10s2s slope, percentage points
    "DGS1": "DGS1",        # 1-year Treasury, percent
    "DGS3MO": "DGS3MO",    # 3-month bill, percent (control)
}
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

# The four indicators as they appear in Tables 2 and 3.
INDICATORS = ["DXY", "T10Y2Y", "DGS1", "GROWTH_VALUE"]
CONTROL = "DGS3MO"

# Release-time rule for the one-day window. A release that lands well before the
# 16:00 ET equity close is measured close-to-close over the release day; a
# release at or after the cut-off is measured over the following session.
# FOMC statements and minutes both land at 14:00 ET, i.e. before the cut-off.
SAME_DAY_CUTOFF_HOUR = 15   # 15:00 ET
