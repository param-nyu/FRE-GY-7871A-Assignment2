"""Tables 2 and 3: did Warsh-era tone move the four indicators?

Table 2 puts the one-day change in each indicator next to the tone scores of the
release that preceded it. Table 3 regresses each indicator's one-day change on
each tone score, controlling for the change in the 3-month bill.

The control is the point of the design, not a nuisance. Doh, Kim and Yang (2021)
find that qualitative tone -- the risk-assessment language around the decision --
moves bond prices about as much as the quantitative decision itself. Holding the
3-month bill fixed absorbs the part of the move that is the rate decision, so
what loads on the tone variable is the part attributable to *how* the Committee
said it rather than *what* it did.

N is 8 releases on 6 distinct market days. That is far too small for standard
inference, so this module reports coefficients, signs and R-squared, and does not
report p-values. See `SIGN_PRIORS` for the signs the coefficients are checked
against.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .config import (CONTROL, INDICATORS, INTERIM_DIR, MARKET_DIR, OUTPUT_DIR,
                     SAME_DAY_CUTOFF_HOUR, WARSH_START)

# Units each indicator is reported in, and how its one-day change is computed.
# Yields move in basis points; the dollar index is a price, so it moves in
# percent; GROWTH_VALUE is already a cumulative percent index by construction,
# so differencing it gives the day's growth-minus-value return spread directly.
UNITS = {
    "DXY": ("%", "pct"),
    "T10Y2Y": ("bp", "diff_bp"),
    "DGS1": ("bp", "diff_bp"),
    "GROWTH_VALUE": ("pp", "diff"),
    "DGS3MO": ("bp", "diff_bp"),
}

# The sign each coefficient should take if hawkish tone does what theory says.
# Hawkish surprise -> stronger dollar, higher front-end yields, a flatter curve
# (the front end rises more than the long end), and growth underperforming value
# because long-duration equity is the most rate-sensitive.
SIGN_PRIORS = {"DXY": +1, "T10Y2Y": -1, "DGS1": +1, "GROWTH_VALUE": -1}

# The tone measures carried into Table 3. Method 1 is primary; plain FinBERT is
# included because it is the baseline Parsing the Fed compared against.
TONE_COLS = ["tone_wordlist", "tone_finbert", "tone_finbert_aug"]


# ---------------------------------------------------------------------------
# Event windows
# ---------------------------------------------------------------------------
def event_window(index: pd.DatetimeIndex, stamp: pd.Timestamp,
                 cutoff_hour: int = SAME_DAY_CUTOFF_HOUR
                 ) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """The (base, event) closes bracketing a release, or None if unavailable.

    A release well before the equity close is measured close-to-close over the
    release day itself; one at or after the cut-off is measured over the
    following session, since the release cannot be in the day's closing price.
    """
    day = pd.Timestamp(stamp.date())
    same_day = stamp.hour < cutoff_hour and day in index

    if same_day:
        event = day
    else:
        later = index[index > day]
        if not len(later):
            return None
        event = later[0]

    earlier = index[index < event]
    return (earlier[-1], event) if len(earlier) else None


def _change(series: pd.Series, base: pd.Timestamp, event: pd.Timestamp,
            mode: str) -> float:
    a, b = series.get(base, np.nan), series.get(event, np.nan)
    if pd.isna(a) or pd.isna(b):
        return np.nan
    if mode == "pct":
        return 100.0 * (b / a - 1.0)
    return 100.0 * (b - a) if mode == "diff_bp" else b - a


def build_event_panel(scores: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    """One row per release: its tone scores and the one-day indicator changes."""
    rows = []
    for r in scores.itertuples():
        window = event_window(market.index, r.stamp)
        if window is None:
            continue
        base, event = window
        row = {"doc_id": r.doc_id, "stamp": r.stamp, "doc_type": r.doc_type,
               "chair": r.chair, "base_close": base.date(), "event_close": event.date(),
               "same_day": bool(base.date() == event.date() - dt.timedelta(days=1)
                                and r.stamp.hour < SAME_DAY_CUTOFF_HOUR)}
        for col in TONE_COLS + ["tone_balance", "tone_direction"]:
            row[col] = getattr(r, col, np.nan)
        for name in INDICATORS + [CONTROL]:
            row[f"d_{name}"] = _change(market[name], base, event, UNITS[name][1])
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 2
# ---------------------------------------------------------------------------
def table2(panel: pd.DataFrame) -> pd.DataFrame:
    warsh = panel[panel.chair == "Warsh"].sort_values("stamp")
    out = pd.DataFrame({
        "Release (ET)": warsh.stamp.dt.strftime("%Y-%m-%d %H:%M"),
        "Type": warsh.doc_type,
        "Window": warsh.base_close.astype(str) + " to " + warsh.event_close.astype(str),
        "Tone: word list": warsh.tone_wordlist.round(2),
        "Tone: FinBERT": warsh.tone_finbert.round(3),
        "Tone: FinBERT aug.": warsh.tone_finbert_aug.round(3),
        "DXY (%)": warsh.d_DXY.round(3),
        "10s2s (bp)": warsh.d_T10Y2Y.round(1),
        "1Y (bp)": warsh.d_DGS1.round(1),
        "Growth-value (pp)": warsh.d_GROWTH_VALUE.round(3),
        "3M bill (bp)": warsh.d_DGS3MO.round(1),
    })
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Table 3
# ---------------------------------------------------------------------------
def _ols(y: pd.Series, X: pd.DataFrame) -> dict:
    """OLS with an intercept. No p-values: at this N they would mislead."""
    import statsmodels.api as sm

    data = pd.concat([y, X], axis=1).dropna()
    if len(data) <= X.shape[1] + 1:
        return {}
    fit = sm.OLS(data.iloc[:, 0], sm.add_constant(data.iloc[:, 1:])).fit()
    # The 3-month bill alone explains most of the variation in the yield
    # indicators by construction, so the full-model R-squared flatters the tone
    # variable. What tone is actually worth is the increment over a
    # control-only regression.
    base = sm.OLS(data.iloc[:, 0], sm.add_constant(data.iloc[:, 2])).fit()
    return {"n": int(fit.nobs), "beta_tone": fit.params.iloc[1],
            "beta_control": fit.params.iloc[2], "r2": fit.rsquared,
            "r2_control_only": base.rsquared,
            "r2_increment": fit.rsquared - base.rsquared}


def table3(panel: pd.DataFrame, collapse: bool = False) -> pd.DataFrame:
    """Each indicator's one-day change on each tone score + the 3M bill change.

    With `collapse`, releases sharing a market day are averaged into one
    observation first. Two Warsh-era dates carry both a statement and its press
    conference, so the uncollapsed panel repeats the same dependent variable
    twice; collapsing removes that repetition at the cost of blurring the
    statement's tone into the transcript's.
    """
    data = panel[panel.chair == "Warsh"].copy()
    if collapse:
        num = data.select_dtypes("number").columns
        data = data.groupby("event_close")[list(num)].mean().reset_index()

    rows = []
    for indicator in INDICATORS:
        y = data[f"d_{indicator}"]
        for tone in TONE_COLS:
            X = data[[tone, f"d_{CONTROL}"]]
            fit = _ols(y, X)
            if not fit:
                continue
            expected = SIGN_PRIORS[indicator]
            rows.append({
                "Indicator": indicator,
                "Units": UNITS[indicator][0],
                "Tone measure": tone,
                "N": fit["n"],
                "Beta (tone)": round(fit["beta_tone"], 4),
                "Beta (3M bill)": round(fit["beta_control"], 4),
                "R2": round(fit["r2"], 3),
                "R2 (control only)": round(fit["r2_control_only"], 3),
                "R2 from tone": round(fit["r2_increment"], 3),
                "Expected sign": "+" if expected > 0 else "-",
                "Sign matches": bool(np.sign(fit["beta_tone"]) == expected),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def load_scores() -> pd.DataFrame:
    wl = pd.read_csv(INTERIM_DIR / "scores_wordlist.csv", parse_dates=["stamp"])
    fb = pd.read_csv(INTERIM_DIR / "scores_finbert.csv", parse_dates=["stamp"])
    keep = ["doc_id", "tone_finbert", "tone_finbert_aug", "tone_direction",
            "n_sentences", "n_directional"]
    return wl.merge(fb[keep], on="doc_id")


def main() -> None:
    market = pd.read_csv(MARKET_DIR / "market.csv", index_col=0, parse_dates=True)
    scores = load_scores()
    panel = build_event_panel(scores, market)
    panel.to_csv(INTERIM_DIR / "event_panel.csv", index=False)

    warsh = panel[panel.chair == "Warsh"]
    print(f"Event panel: {len(panel)} releases, {len(warsh)} in the Warsh era "
          f"on {warsh.event_close.nunique()} distinct market days.\n")

    t2 = table2(panel)
    t2.to_csv(OUTPUT_DIR / "table2_warsh_event_changes.csv", index=False)
    print("TABLE 2  One-day indicator changes after each Warsh-era release")
    print(t2.to_string(index=False), "\n")

    for collapse, label in ((False, "by release (N=8)"),
                            (True, "by market day (N=6)")):
        t3 = table3(panel, collapse=collapse)
        suffix = "collapsed" if collapse else "by_release"
        t3.to_csv(OUTPUT_DIR / f"table3_regressions_{suffix}.csv", index=False)
        print(f"TABLE 3  Indicator change ~ tone + 3M bill change, {label}")
        print(t3.to_string(index=False))
        summary = t3.groupby("Tone measure").agg(
            sign_hit_rate=("Sign matches", "mean"),
            mean_R2_from_tone=("R2 from tone", "mean"),
        ).round(3)
        print("\n  expected-sign hit rate, and mean R2 attributable to tone:")
        print(summary.to_string(), "\n")

    print("N is 8 releases on 6 market days. Coefficients and signs are reported;")
    print("p-values are not, because at this N they would imply far more than the")
    print("data supports. Table 3 is a description of the Warsh era, not a test.")


if __name__ == "__main__":
    main()
