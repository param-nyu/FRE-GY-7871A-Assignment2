# AI use disclosure

Course: FRE-GY 7871A, NLP and the Investment Process (Fall 2026)
Assignment 2 — Fed communication tone under Chair Warsh

## Summary

Claude (Anthropic, Claude Code) was used as a coding assistant for the data
collection, scoring and regression code in `src/`, and for drafting the
structure of this repository. The tone lexicon, the interpretation of results,
and the entire forecast and trade recommendation are my own work. Details below.

## What was AI-assisted

**Data collection (`src/collect.py`) — AI-assisted.**
Claude located the Board's JSON news listings (`/json/ne-press.json`,
`ne-speeches.json`, `ne-testimony.json`), which carry release date *and time*,
and wrote the scraping, text-extraction and caching code, including the step
that follows a minutes press release through to the minutes document itself
(the press release is only a ~130-word announcement). Market data plumbing
(Yahoo Finance for DXY/IWF/IWN, keyless FRED CSV for T10Y2Y/DGS1/DGS3MO) was
also AI-written. I verified the resulting corpus by hand against the FOMC
calendar.

**Word list, Method 1 (`src/lexicon.py`, `src/score_wordlist.py`) — mixed.**
The 79 hawkish/dovish phrases in `src/lexicon.py` are my own, written against
FOMC language rather than adapted from an existing dictionary. Claude wrote the
matching engine (the ordered, gap-limited phrase matcher), the tf.idf weighting
and the diagnostics, and proposed the two matching refinements described below
after I inspected the matched spans and found false positives.

Two corrections I made after auditing the matched text:

* The gap budget originally ran across the whole phrase, which let "inflation"
  chain to an "increased" eight tokens away in an unrelated clause. It now
  applies between consecutive tokens of the phrase.
* Inflation *compensation* and *breakeven* language was being scored as
  statements about the inflation outlook. Those tokens now void a match.

I validated the finished list against known policy history rather than against
its own output: it puts 2022-23 at the hawkish extreme and 2020-21 and 2024 at
the dovish extreme, and its single most dovish statement is the emergency
intermeeting cut of March 3, 2020. I did not tune the list to improve any
regression result.

**FinBERT, Method 2 (`src/score_finbert.py`) — AI-assisted.**
_(to be completed)_

**Regression code (`src/validate.py`) — AI-assisted.**
_(to be completed)_

## What is my own

**The forecast section of the report — rate decision probabilities, the
tone-direction probability, the per-indicator probabilities and expected sizes,
the trade recommendation and its falsification condition — is my own analysis.**
It is not generated output. It is my reading of the completed tables.

## Scope decisions made under time pressure

The assignment was completed against a same-day deadline. Where completeness
traded off against finishing, I took the version that finishes, and recorded the
cost here.

**1. Speech collection is scoped, not exhaustive.**
Collecting every speech either Chair gave (hundreds of documents, several
distinct page templates) was not feasible in the time available, and most of
those speeches are not about monetary policy. The `speech` document type is
restricted to the sitting Chair's semiannual congressional testimony, FOMC
press conference transcripts, and major policy speeches, selected by a keyword
and venue filter over the Board's speech feed (see `src/config.py`).

*Cost:* the filter is keyword-based, so it admits a handful of borderline items
(e.g. short "Opening Remarks" at policy conferences) and may miss a
policy-relevant speech with an oblique title. Since statements and minutes are
complete and the press conference transcripts are complete, the Warsh-era
evidence does not hinge on the speech filter.

**2. Method 2 is a rule-based approximation, not a fine-tuned model.**
Doh, Song and Yang (2023) fine-tune a sentence encoder on synthetic numeric data
so the embeddings recognise magnitude and direction. Fine-tuning a model was not
feasible tonight. Instead I run FinBERT sentence-level sentiment and augment it
with a regex extractor for rate-direction language, which addresses FinBERT's
known failure mode — it cannot reliably distinguish "lower by 25 basis points"
from "higher by 25 basis points". This is an approximation of the numeric
property fine-tuning, not a reproduction of it, and the report says so.

**3. Small-N handling.**
The Warsh era contains 8 documents. Table 3 reports coefficients and signs but
does not rest on significance testing, because at this N conventional p-values
would imply far more than the data supports. This is stated in the report rather
than left for the reader to infer.

**4. Alternative-statement calibration is not available.**
Doh, Song and Yang calibrate tone against the FOMC's alternative statements
(Alt A/B/C/D), released with a five-year lag. Warsh-era alternatives will not be
declassified until roughly 2031, so that calibration scale cannot be used here.
