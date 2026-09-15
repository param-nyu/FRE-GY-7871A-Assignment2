# FRE-GY 7871A — Assignment 2

Has Fed communication turned hawkish under Chair Kevin Warsh, did the tone move
markets, and what does that imply for the September 16, 2026 FOMC meeting?

## What this repo does

1. **Collects** every FOMC statement, FOMC minutes release, and monetary-policy
   Chair communication (semiannual testimony, post-meeting press conference
   transcripts, major policy speeches) published by the Board between
   February 2018 and September 15, 2026, with the **release date and time** of
   each. It also pulls the four market indicators plus the 3-month bill control.
2. **Scores** each document for hawkish/dovish tone two ways — a hand-built,
   tf.idf-weighted FOMC word list (primary) and FinBERT augmented with a
   rule-based numeric rate-direction extractor (secondary).
3. **Validates** the scores against the one-day move in each indicator across
   the Warsh-era releases, controlling for the change in the 3-month bill.

## Running it

```bash
pip install -r requirements.txt

python -m src.collect          # ~4 min   documents + market data -> data/
python -m src.score_wordlist   # ~10 sec  Method 1  -> data/interim/scores_wordlist.csv
python -m src.score_finbert    # ~12 min  Method 2  -> data/interim/scores_finbert.csv
python -m src.exhibits         #          Table 1, Figure 1 -> outputs/
python -m src.validate         #          Tables 2 and 3    -> outputs/
python report/build_report.py  #          outputs/ -> report/REPORT.pdf

jupyter lab notebook.ipynb     # the same analysis, with saved output
```

`src.collect` caches every document as a text file and `src.score_finbert` caches
per-document scores, so re-runs are cheap. Deleting `data/` forces a full refresh.

`src/collect.py` caches every document as a text file under `data/docs/`, so
re-runs are cheap. Deleting `data/` forces a full refresh.

## Sample

| | |
|---|---|
| Window | 2018-02-01 – 2026-09-15 |
| Powell era | 2018-02-01 – 2026-05-21 |
| Warsh era | 2026-05-22 – 2026-09-15 |
| Documents | 260 (252 Powell, 8 Warsh) |

The Warsh era is short by construction — he was sworn in less than four months
before the data cut-off. Table 1 reports the exact counts, and every result that
depends on the Warsh-era sample states N on its face.

## Document scope

`statement` and `minutes` are complete: every FOMC statement and every FOMC
minutes release in the window. Board *discount rate* minutes are a different
document and are excluded.

`speech` is **deliberately scoped**, not exhaustive. It covers monetary-policy
communication by the sitting Chair only:

* semiannual Monetary Policy Report testimony to Congress,
* FOMC post-meeting press conference transcripts,
* major policy speeches (Jackson Hole, and speeches whose title or venue is
  about the outlook, inflation, the labor market or the policy framework).

Governor speeches, supervision and regulation testimony, and ceremonial remarks
are excluded. The rationale and the cost of this choice are in `AI_USE.md`.

## Layout

```
notebook.ipynb          main analysis, saved output
src/collect.py          federalreserve.gov + FRED/Yahoo collection
src/lexicon.py          the hand-built hawkish/dovish phrase list
src/score_wordlist.py   Method 1: tf.idf-weighted word list
src/score_finbert.py    Method 2: FinBERT + numeric-direction augmentation
src/exhibits.py         Table 1, Figure 1
src/validate.py         event windows, Tables 2 and 3
report/report.md        report source; exhibits injected at build time
report/build_report.py  builds report/REPORT.pdf
AI_USE.md               AI assistance and scope decisions
```

No data files are committed; `src/collect.py` rebuilds all of `data/`.

## Results in one paragraph

All eight Warsh-era documents score hawkish on the primary word-list measure, with
his four policy speeches at the 97th-100th percentile of 117 Powell-era policy
speeches. The word list gets 3 of 4 regression coefficient signs right; both
FinBERT variants get 0 of 4, because plain FinBERT reads Warsh's terse,
"solid growth / strong investment" statements as good news and therefore as dovish.
The word list's largest incremental explanatory power falls on the 1-year Treasury
and the growth-value spread, the same two indicators the Parsing the Fed
presentation found it strongest on. With eight releases on six market days, none of
this is offered as statistical inference, and the report says so on the face of
Table 3.
