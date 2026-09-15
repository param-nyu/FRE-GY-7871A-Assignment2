# Fed communication tone under Chair Warsh

## Has the Committee turned hawkish, did it move markets, and what happens on September 16?

FRE-GY 7871A, NLP and the Investment Process — Assignment 2 — Param Shah — September 15, 2026

---

## 1. Summary

Kevin Warsh was sworn in as Chair on May 22, 2026. In the 116 days to the data cut-off the
Board published eight monetary-policy documents under him. This report scores every FOMC
statement, FOMC minutes release and Chair policy communication from February 2018 to
September 15, 2026 — 260 documents — on a hawkish–dovish scale by two methods, measures the
one-day market reaction to each Warsh-era release, and regresses those reactions on tone
while controlling for the change in the 3-month bill.

Three findings.

- **Every one of the eight Warsh-era documents scores hawkish** on the primary word-list
  measure. His four policy speeches sit at the 97th–100th percentile of 117 Powell-era policy
  speeches. The shift is visible in Figure 1 as a level break, not a drift.
- **The hand-built word list beats FinBERT decisively**, getting 3 of 4 coefficient signs
  right against FinBERT's 0 of 4, and carrying its largest explanatory power on the 1-year
  Treasury and the growth–value spread — the same two indicators the Parsing the Fed
  presentation found it strongest on.
- **The market evidence is directionally consistent but statistically weightless.** Eight
  releases fall on six distinct market days. Coefficients and signs are reported below;
  p-values are not, and should not be.

---

## 2. Table 1. Documents collected, by type and by Chair

{{TABLE1}}

{{TABLE1_NOTES}}

The Warsh era is thin by construction, and the report does not disguise it: N appears on the
face of every exhibit that depends on it. Note also the length difference. Warsh's statements
average 149 words against Powell's 379, and his minutes 5,493 against 8,278. Brevity is itself
a communication choice, and section 4 shows it interacts with the per-word tone measure.

---

## 3. Method

### 3.1 Method 1 (primary): a hand-built, tf.idf-weighted word list

Loughran and McDonald (2011) show that a word list built for its domain outperforms a
general-purpose dictionary, and that the useful weighting is tf.idf. Their list itself does
not transfer: its categories are about *negativity*, and the hawk–dove axis cuts across them.
"Inflation has eased" and "inflation remains elevated" are both close to neutral in
Loughran–McDonald terms and opposite in policy terms. So the list here — 43 hawkish and 36
dovish phrases — is written from scratch against FOMC language.

The score is

> tone = 1000 × ( Σ over hawkish phrases of tf × idf  −  Σ over dovish phrases of tf × idf ) ÷ total words

with idf = ln(N/df) computed over all 260 documents. Phrases match as **ordered token chains
with a gap budget of five tokens between consecutive slots**, so "inflation ... has remained
... elevated" fires but a chain stretched across an unrelated clause does not. This is the
Parsing the Fed word-list method: multi-word phrases whose words need not be consecutive.

The list was validated against policy history rather than against the regressions it feeds.
It places 2022–23 at the hawkish extreme and 2020–21 and 2024 at the dovish extreme; its
single most dovish statement out of 260 documents is March 3, 2020, the emergency intermeeting
50bp cut, and its second is September 18, 2024, the 50bp cut that opened the easing cycle. No
phrase was added or removed to improve a downstream result.

### 3.2 Method 2 (secondary): FinBERT with numeric-direction augmentation

FinBERT (ProsusAI/finbert) classifies *financial news sentiment*, which is not the hawk–dove
axis. Layer 1 averages sentence-level P(positive) − P(negative) per document. Layer 2 reads
each sentence for policy-rate direction language — raise/lower, hike/cut, with magnitude in
basis points or fractional percentage points, and negation for holds — and replaces the
sentiment contribution of sentences that carry a direction signal. A 50bp move ranks above a
25bp move, which is the magnitude ordering at issue.

The orientation of the sentiment layer is a claim about the data, so it is tested rather than
assumed: over the 252 Powell-era documents, raw FinBERT sentiment correlates **−0.177** with
the word list, confirming that hawkish FOMC text reads to FinBERT as bad news. The score is
negated accordingly. Had the correlation come out positive, the convention would have been
wrong, and this section would say so.

**This is a rule-based approximation of Doh, Song and Yang (2023), not a reproduction.** They
fine-tune a sentence encoder on synthetic numeric data so that magnitude and direction live
inside the embeddings. Fine-tuning was not feasible in the time available. Section 5 shows
what that approximation costs.

### 3.3 Event windows

Each document's release date and time comes from the Board's own news listings. A release
well before the 16:00 ET equity close is measured close-to-close over the release day; one at
or after 15:00 ET is measured over the following session. All eight Warsh-era releases land
between 08:30 and 14:30 ET, so all eight are same-day windows. Every window was checked
against the market data: all four indicators and the control have both closes present, with
no holiday gaps.

---

## 4. Figure 1. Tone over time, by document type

{{FIGURE1}}

<div class="notes">Points are individual releases; the line is a five-release rolling mean.
The dashed line marks May 22, 2026. Warsh-era releases are highlighted. Positive is hawkish.
Vertical scales differ by panel: the per-word denominator makes short documents swing wider,
which is why statements span a range several times that of minutes.</div>

The 2022–23 tightening cycle and the 2024 easing cycle are both plainly visible, which is the
evidence that the measure is tracking policy rather than noise. Against that backdrop the
Warsh-era points sit at or above the 2023 hawkish peak for statements, and near the top of the
distribution for speeches.

**One honest qualification.** Warsh's July statement scores +39.1 against Powell's May 2023
peak of +32.7 — but Powell's statement contained nine hawkish phrases to Warsh's three. The
per-word denominator, which the assignment specifies, rewards brevity. A length-free polarity
ratio is reported alongside as a robustness check; it agrees on **direction** for all eight
documents (every one hawkish) while being more conservative about **magnitude**. The claim
this report makes is the directional one.

---

## 5. Table 2. One-day indicator changes after each Warsh-era release

{{TABLE2}}

<div class="notes">Tone scores are for the release in that row. DXY in percent, yields in
basis points, growth-value in percentage points. All windows are same-day close-to-close.
June 17 and July 29 each carry a statement and its press conference transcript, so those two
pairs share a single market window and the indicator columns repeat by construction.</div>

Two features of this table govern what section 6 can claim. First, **eight releases fall on
six distinct market days.** Second, the moves are mixed in sign: the 1-year rose 14bp on June
17 and fell 5bp on July 29, although the two statements score near-identically hawkish. With
six days, individual events dominate.

---

## 6. Table 3. Indicator change on tone, controlling for the 3-month bill

Doh, Kim and Yang (2021) find that qualitative risk-assessment language moves bond prices
about as much as the quantitative rate decision itself. That is what makes the control a
design feature rather than a nuisance: holding the 3-month bill fixed absorbs the decision, so
what loads on the tone variable is *how* the Committee said it rather than *what* it did.

`R2 from tone` is the increment over a control-only regression. The full R-squared is
flattered by the control, which mechanically explains most of the variation in the yield
indicators, so the increment is the number that answers the question.

### 6.1 By release (N = 8)

{{TABLE3_RELEASE}}

### 6.2 By market day (N = 6), releases sharing a day averaged

{{TABLE3_DAY}}

<div class="caution"><strong>On inference.</strong> N is eight releases on six market days,
against three estimated parameters. Coefficients, signs and R-squared are reported.
<strong>P-values are not reported, because at this N they would imply far more than the data
can support.</strong> Table 3 is a description of the Warsh era, not a test of it. The
sign-agreement column is the honest summary statistic here: it asks whether each coefficient
points the way theory says, which is a question six observations can speak to, rather than
whether it differs from zero, which they cannot.</div>

### 6.3 What survives the caveat

- **The word list gets 3 of 4 signs right** — a hawkish release is followed by a stronger
  dollar, a higher 1-year yield, and growth underperforming value. It misses the curve slope.
- **Both FinBERT variants get 0 of 4.** That is one error, not four: their sign is inverted
  over the Warsh era, which flips every coefficient at once.
- **The word list's largest incremental R-squared falls on the 1-year Treasury (0.18) and the
  growth–value spread (0.32)** in the collapsed specification. These are exactly the two
  indicators Parsing the Fed's appendix found the word list explained best — a replication on
  a different sample, a different Chair, and an independently built lexicon.
- **Tone adds essentially nothing to the curve slope** (increment approximately 0.00). 10s2s
  is dominated by the front end, which the 3-month bill control already absorbs.

---

## 7. Comparison to the readings

**Loughran and McDonald (2011).** Their result — a domain-specific tf.idf-weighted list beats
a general dictionary — is the direct reason Method 1 is hand-built rather than reused off the
shelf. Their acknowledged limitation, that word lists ignore word order and context, is what
the ordered-chain matcher with a gap budget partially addresses: "inflation ... elevated"
counts, "inflation compensation ... declined" does not.

**Doh, Song and Yang (2020/2023), "Deciphering Federal Reserve Communication".** They fine-tune
a Universal Sentence Encoder on synthetic numeric data so the embeddings recognise magnitude
and direction — a 0.50% hike as more hawkish than 0.25%. Our Method 2 approximates this with
rules, and the results show precisely why the approximation is not a substitute. Reported
separately, the two layers disagree sharply over the Warsh era:

> Sentiment layer — Powell −0.040, Warsh −0.202 (reads Warsh as dovish)
> Direction layer — Powell +0.034, Warsh **+0.464** (reads Warsh as strongly hawkish)

The rule layer agrees with the word list. It loses, because directional sentences are only
**2.4%** of the corpus, so the frozen sentiment layer dominates the blend. The June 17
statement contains **zero** rate-direction sentences, so the augmentation cannot touch it at
all. Rules bolted onto a frozen model reach only the sentences that happen to state a number;
putting the numeric property inside the embeddings, as Doh, Song and Yang do, is not an
optional refinement but the thing that makes the approach work.

Their Alt A/B/C/D calibration scale is unavailable here for an unrelated reason: the FOMC's
alternative statements are released with a five-year lag, so Warsh-era alternatives will not
be declassified until roughly 2031.

**Doh, Kim and Yang (2021), "How You Say It Matters".** Their finding that qualitative tone
moves bond prices about as much as the rate decision validates the Table 3 design. Our
evidence is weakly consistent with it — tone carries incremental explanatory power on the
1-year and the growth–value spread but not on the curve — and at six market days we claim no
more than consistency.

**Parsing the Fed (presentation).** It ran this same three-method comparison and found the
word list outperformed both FinBERT variants on the 1-year Treasury and the growth–value
spread, with fine-tuned FinBERT beating plain FinBERT on most indicators. We reproduce the
first result cleanly, on an independently constructed lexicon. On the second we reproduce only
the direction: augmented FinBERT edges plain FinBERT on mean incremental R-squared, by a
margin far too small to rest any weight on — and a rule layer is not a fine-tune.

### 7.1 A diagnostic worth reporting

Sentence-level output on the June 17 statement shows the failure mode directly. FinBERT scores
*"Inflation remains elevated relative to the Committee's 2 percent goal"* at **+0.56**, that
is, as positive news, and *"The Committee will deliver price stability"* — the hardest line in
the document — at **+0.15**, essentially neutral. Meanwhile it scores *"Productivity growth and
capital investment are strong"* at **+0.89**. FinBERT is grading the economy, not the policy
stance. Because Warsh's statements are short and dense with such descriptions, they score as
the most *positive* documents in the corpus, and therefore the most dovish — exactly backwards.

---

## 8. Forecast: the FOMC meeting of September 16, 2026

<div class="placeholder">This section is the author's own analysis, written from the completed
tables above. It is not generated output. See AI_USE.md.</div>

### 8.1 Rate decision

| Outcome | Probability |
|---|---|
| Raise 25bp | |
| Hold | |
| Cut 25bp | |
| Other | |

### 8.2 Tone direction

Probability that the September statement scores more hawkish than the July statement
(word-list measure, July = +39.10):

### 8.3 Per-indicator forecast

| Indicator | P(rises) | Expected one-day move |
|---|---|---|
| DXY | | |
| 10s2s | | |
| 1-year Treasury | | |
| Growth minus value | | |

### 8.4 Trade recommendation

**Trade:**

**Rationale:**

**What would prove this wrong:**

---

## 9. Reproducibility

All code is in the accompanying repository. `python -m src.collect` rebuilds the corpus and
the market series from federalreserve.gov, FRED and Yahoo Finance; `src.score_wordlist` and
`src.score_finbert` produce the tone panels; `src.exhibits` and `src.validate` produce every
table and figure in this report, which is assembled by `report/build_report.py` directly from
those output files. No data files are committed. AI assistance is documented in `AI_USE.md`.
