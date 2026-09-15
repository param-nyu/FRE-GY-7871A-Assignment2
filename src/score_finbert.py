"""Method 2 (secondary): FinBERT sentiment, augmented with rate-direction rules.

FinBERT (ProsusAI/finbert) classifies a sentence as positive, negative or
neutral *financial news*. That axis is not the hawk-dove axis, and the gap is
the known failure mode this method has to work around: "the Committee decided to
lower the target range by 25 basis points" and "...to raise the target range by
25 basis points" are near-identical strings on FinBERT's sentiment axis, but
they are opposite policy signals.

So the score is built in two layers.

**Layer 1, plain FinBERT.** ``sent = P(positive) - P(negative)``, averaged over
the sentences of a document. This is the baseline that Parsing the Fed compared
its word list against, and it is reported unmodified.

**Layer 2, numeric-direction augmentation.** A rule-based extractor reads each
sentence for policy-rate direction language -- raise/lower, hike/cut, tighten/
ease -- anchored to the policy rate, with the magnitude (25 vs 50 basis points,
quarter vs half percentage point) and any negation. Sentences that carry a
direction signal have their sentiment contribution *replaced* by that signal;
the rest keep their FinBERT contribution.

This is a rule-based approximation of the numeric-property fine-tuning in Doh,
Song and Yang (2023), not a reproduction of it. They fine-tune a sentence
encoder on synthetic numeric data so the embeddings themselves carry magnitude
and direction; we bolt a regex layer onto a frozen model because fine-tuning was
not feasible in the time available. See AI_USE.md.

Orientation: both layers are signed so that **positive means hawkish**, matching
Method 1. For the sentiment layer that requires a sign convention, which is
stated and tested in `ORIENTATION` below.
"""

from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from .config import INTERIM_DIR, OUTPUT_DIR

MODEL_NAME = "ProsusAI/finbert"
MAX_TOKENS = 96          # FOMC sentences are long but rarely longer than this
BATCH_SIZE = 64

CACHE_DIR = INTERIM_DIR / "finbert_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Sign convention for the plain-FinBERT layer.
#
# FinBERT reads the *valence of economic conditions*, not the direction of
# policy. In FOMC text, hawkish passages describe problems -- inflation
# elevated, price pressures, upside risks -- which FinBERT scores negative;
# dovish passages describe improvement -- inflation has eased, progress toward
# the goal -- which it scores positive. So hawkishness should map to *negative*
# FinBERT sentiment, and the score is negated to put it on Method 1's scale.
#
# This is a hypothesis, not an assumption: `main()` reports the realised
# correlation between the two methods over the Powell era, where N is large
# enough for the sign to mean something. If that correlation came out with the
# opposite sign, this constant would be wrong and the report would have to say so.
ORIENTATION = -1.0


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------
# Abbreviations that end in a period but not a sentence. Without these the FOMC
# corpus splits on "U.S.", "Mr.", "a.m." and every "No. 3" footnote marker.
# Python's re has no variable-width lookbehind, so the split is done first and
# over-eager breaks are stitched back together.
_ABBREV = frozenset(
    "u.s u.k e.u mr mrs ms dr gov sen rep jr sr st no vs etc inc corp co "
    "fig approx a.m p.m e.g i.e jan feb mar apr jun jul aug sept sep oct nov dec "
    "fed'l cf ch pp vol art sec".split()
)
# A colon introducing a capitalised clause is a sentence break here: the FOMC
# writes "...approved the following statement for release by a 12-0 vote: The
# Committee decided to maintain the target range...", and without this the
# operative decision is swallowed by the preamble.
_SENT_SPLIT = re.compile(r"(?<=[.!?:])\s+(?=[A-Z\"'(])")
_LAST_WORD = re.compile(r"([A-Za-z.]+)\.$")


def _ends_in_abbreviation(fragment: str) -> bool:
    m = _LAST_WORD.search(fragment.strip())
    if m is None:
        return False
    word = m.group(1).rstrip(".").lower()
    # A single capital letter before the period is an initial ("Jerome H. Powell").
    return word in _ABBREV or len(word) == 1


def split_sentences(text: str, min_words: int = 4) -> list[str]:
    """Sentences worth scoring.

    Fragments shorter than `min_words` -- headings, list markers, transcript
    speaker labels -- are dropped rather than scored, because FinBERT returns
    near-random probabilities on them.
    """
    merged: list[str] = []
    for part in _SENT_SPLIT.split(text):
        if merged and _ends_in_abbreviation(merged[-1]):
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return [s.strip() for s in merged if len(s.split()) >= min_words]


# ---------------------------------------------------------------------------
# Numeric rate-direction extraction
# ---------------------------------------------------------------------------
# A direction verb only counts when it is about the policy rate, not about
# inflation, employment or asset prices.
_RATE_ANCHOR = re.compile(
    r"\b(target range|federal funds rate|funds rate|policy rate|target for the"
    r"|interest rates?|the rate|policy stance|target level)\b", re.I)

_UP = re.compile(r"\b(rais(e|ed|es|ing)|increas(e|ed|es|ing)|hik(e|ed|es|ing)"
                 r"|tighten(ed|ing)?|firm(ed|ing)?|higher|up)\b", re.I)
_DOWN = re.compile(r"\b(lower(ed|ing)?|reduc(e|ed|es|ing)|cut(s|ting)?"
                   r"|eas(e|ed|es|ing)|loosen(ed|ing)?|decreas(e|ed|es|ing)|down)\b", re.I)

# Negation / hypothetical markers that flip or void a direction.
_NEGATION = re.compile(r"\b(not|no|never|without|refrain(ed|ing)? from|declined to"
                       r"|unchanged|maintain(ed|ing)?|leave|left|held|hold)\b", re.I)

# Magnitude, in basis points.
_BPS = re.compile(r"\b(\d{1,3})\s*basis points?\b", re.I)
_PCT_FRAC = re.compile(
    r"\b(?:(\d)[/⁄](\d)|(one[- ]quarter|quarter|one[- ]half|half|three[- ]quarters"
    r"|full|one))\s+(?:of\s+a\s+)?percentage point", re.I)
_PCT_DEC = re.compile(r"\b(\d?\.\d{1,2})\s*percentage point", re.I)

_WORD_FRACTIONS = {
    "one-quarter": 25, "quarter": 25, "one quarter": 25,
    "one-half": 50, "half": 50, "one half": 50,
    "three-quarters": 75, "three quarters": 75,
    "full": 100, "one": 100,
}


def extract_magnitude(sentence: str) -> int | None:
    """Size of the move in basis points, or None if the sentence gives no size."""
    m = _BPS.search(sentence)
    if m:
        return int(m.group(1))
    m = _PCT_FRAC.search(sentence)
    if m:
        if m.group(1) and m.group(2):                      # "1/4 percentage point"
            num, den = int(m.group(1)), int(m.group(2))
            return round(100 * num / den) if den else None
        return _WORD_FRACTIONS.get(m.group(3).lower().replace("- ", "-"))
    m = _PCT_DEC.search(sentence)
    if m:
        return round(float(m.group(1)) * 100)
    return None


def direction_signal(sentence: str) -> tuple[float, int | None]:
    """Policy-rate direction for one sentence, as (score, magnitude_bps).

    The score is bounded to [-1, 1] so it is on the same scale as the FinBERT
    sentiment it replaces. A move of unstated size scores +/-0.50; 25 bp scores
    +/-0.75; 50 bp scores +/-1.00 -- so "raise by 50 basis points" is read as
    more hawkish than "raise by 25 basis points", which is the magnitude
    ordering Doh, Song and Yang fine-tune their encoder to recognise.
    Returns (0.0, None) when the sentence carries no policy-rate direction.
    """
    if not _RATE_ANCHOR.search(sentence):
        return 0.0, None

    up, down = bool(_UP.search(sentence)), bool(_DOWN.search(sentence))
    if up == down:          # neither, or both ("raise or lower") -- no clean signal
        return 0.0, None

    sign = 1.0 if up else -1.0
    bps = extract_magnitude(sentence)

    # "decided to maintain the target range" / "did not raise" carry a direction
    # verb but no move. Treat as no signal rather than guessing which way.
    if _NEGATION.search(sentence) and bps is None:
        return 0.0, None

    magnitude = 0.5 if bps is None else min(1.0, 0.5 + 0.25 * (bps / 25.0))
    return sign * magnitude, bps


# ---------------------------------------------------------------------------
# FinBERT
# ---------------------------------------------------------------------------
def _load_model():
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = "mps" if torch.backends.mps.is_available() else (
        "cuda" if torch.cuda.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.to(device).eval()
    # Read the label order off the config rather than assuming it.
    labels = {v.lower(): k for k, v in model.config.id2label.items()}
    return tok, model, device, labels


def sentiment_scores(sentences: list[str], bundle) -> np.ndarray:
    """P(positive) - P(negative) for each sentence."""
    import torch

    tok, model, device, labels = bundle
    pos_i, neg_i = labels["positive"], labels["negative"]
    out = np.empty(len(sentences), dtype=float)
    with torch.no_grad():
        for start in range(0, len(sentences), BATCH_SIZE):
            batch = sentences[start:start + BATCH_SIZE]
            enc = tok(batch, padding=True, truncation=True,
                      max_length=MAX_TOKENS, return_tensors="pt").to(device)
            probs = torch.softmax(model(**enc).logits, dim=-1).cpu().numpy()
            out[start:start + len(batch)] = probs[:, pos_i] - probs[:, neg_i]
    return out


# ---------------------------------------------------------------------------
# Document scoring
# ---------------------------------------------------------------------------
def score_document(text: str, bundle) -> dict:
    sentences = split_sentences(text)
    if not sentences:
        return {"n_sentences": 0, "n_directional": 0, "finbert_plain": 0.0,
                "tone_finbert": 0.0, "tone_finbert_aug": 0.0, "mean_bps": None}

    sent = sentiment_scores(sentences, bundle)
    signals = [direction_signal(s) for s in sentences]
    direction = np.array([d for d, _ in signals])
    sized = [b for _, b in signals if b is not None]
    is_dir = direction != 0.0

    # Augmented: directional sentences speak for themselves, the rest keep the
    # (oriented) FinBERT reading.
    augmented = np.where(is_dir, direction, ORIENTATION * sent)

    return {
        "n_sentences": len(sentences),
        "n_directional": int(is_dir.sum()),
        "finbert_plain": float(sent.mean()),                  # raw, unoriented
        "tone_finbert": float(ORIENTATION * sent.mean()),     # Layer 1
        "tone_finbert_aug": float(augmented.mean()),          # Layer 2
        # Layer 2 in isolation: what the rules see when the sentiment layer is
        # taken away. Reported separately because the two layers disagree on the
        # Warsh era, and the blended score hides which one is driving the sign.
        "tone_direction": float(direction[is_dir].mean()) if is_dir.any() else None,
        "mean_bps": float(np.mean(sized)) if sized else None,
    }


def score_corpus(texts: dict[str, str]) -> pd.DataFrame:
    """Score every document, caching per document so re-runs are cheap."""
    bundle = None
    rows = {}
    for n, (doc_id, text) in enumerate(texts.items(), 1):
        cache = CACHE_DIR / f"{doc_id}.json"
        if cache.exists():
            rows[doc_id] = json.loads(cache.read_text())
            continue
        if bundle is None:
            print(f"  loading {MODEL_NAME} ...")
            bundle = _load_model()
            print(f"  device: {bundle[2]}")
        rows[doc_id] = score_document(text, bundle)
        cache.write_text(json.dumps(rows[doc_id]))
        if n % 20 == 0:
            print(f"  {n}/{len(texts)} documents")
    return pd.DataFrame(rows).T


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    from .score_wordlist import load_corpus

    manifest, texts = load_corpus()
    print(f"Scoring {len(texts)} documents with FinBERT ...")
    scores = score_corpus(texts)

    panel = manifest.merge(scores, left_on="doc_id", right_index=True)
    panel.to_csv(INTERIM_DIR / "scores_finbert.csv", index=False)

    # Does the orientation hypothesis hold? Powell era only: N is large enough
    # there for the sign of the correlation to mean something.
    wl = pd.read_csv(INTERIM_DIR / "scores_wordlist.csv")
    both = panel.merge(wl[["doc_id", "tone_wordlist"]], on="doc_id")
    powell = both[both.chair == "Powell"]
    print(f"\nOrientation check (Powell era, N={len(powell)}):")
    print(f"  corr(raw FinBERT sentiment, word list) = "
          f"{powell.finbert_plain.corr(powell.tone_wordlist):+.3f}"
          "   (expected negative: hawkish text reads as bad news)")
    for col in ("tone_finbert", "tone_finbert_aug"):
        print(f"  corr({col:<17}, word list) = "
              f"{powell[col].corr(powell.tone_wordlist):+.3f}")

    print("\nThe two layers, separately (mean by Chair):")
    layers = panel.groupby("chair")[["tone_finbert", "tone_direction",
                                     "tone_finbert_aug"]].mean().round(3)
    print(layers.to_string())
    print("  positive = hawkish. Where the sentiment layer and the direction")
    print("  layer disagree, the blend follows the sentiment layer, because")
    print("  directional sentences are a small share of any document.")

    print("\nDirection extractor coverage:")
    print(f"  {int(panel.n_directional.sum()):,} directional sentences out of "
          f"{int(panel.n_sentences.sum()):,} ("
          f"{100 * panel.n_directional.sum() / panel.n_sentences.sum():.1f}%)")
    sized = panel.mean_bps.dropna()
    print(f"  {len(sized)} documents state a move size; mean {sized.mean():.0f} bp")

    print("\nMean tone by document type and Chair:")
    for col in ("tone_finbert", "tone_finbert_aug"):
        print(f"\n  {col}")
        print(panel.pivot_table(index="doc_type", columns="chair",
                                values=col, aggfunc="mean").round(3))

    print("\nWarsh-era documents:")
    cols = ["stamp", "doc_type", "n_sentences", "n_directional",
            "tone_finbert", "tone_direction", "tone_finbert_aug"]
    print(panel[panel.chair == "Warsh"][cols].to_string(
        index=False, float_format=lambda v: f"{v:8.3f}"))

    panel[cols + ["chair"]].to_csv(OUTPUT_DIR / "table_a2_finbert_warsh.csv", index=False)


if __name__ == "__main__":
    main()
