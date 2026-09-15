"""Method 1 (primary): the hand-built, tf.idf-weighted hawkish/dovish word list.

    tone = 1000 * ( sum_h tf_h * idf_h  -  sum_d tf_d * idf_d ) / total words

where ``h`` ranges over hawkish phrases and ``d`` over dovish ones, ``tf`` is the
number of times the phrase fires in the document, and ``idf = ln(N / df)`` is
computed over the whole 260-document corpus, as in Loughran and McDonald (2011).
The scale factor of 1,000 just puts the numbers in a readable range; it is a
constant and changes nothing about signs, rankings or regression fit.

A phrase fires when its required tokens appear **in order and within
``lexicon.MAX_GAP`` tokens of each other**, not necessarily consecutively. Runs
``python -m src.score_wordlist`` to score the cached corpus.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .config import INTERIM_DIR, OUTPUT_DIR
from .lexicon import ALL_PHRASES, BLOCKERS, MAX_GAP

# Tokens keep internal hyphens and apostrophes, so "broad-based" and
# "second-round" survive as single tokens and the patterns can match them.
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-']*")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


# ---------------------------------------------------------------------------
# Turning a phrase pattern into an ordered list of single-token regexes
# ---------------------------------------------------------------------------
def _split_top_level(pattern: str) -> list[str]:
    """Split on spaces that are not inside parentheses."""
    pieces, depth, current = [], 0, []
    for ch in pattern:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == " " and depth == 0:
            if current:
                pieces.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        pieces.append("".join(current))
    return pieces


# An optional group whose content contains a space -- "(has )?", "(of the )?" --
# is a filler word, not a token slot. Proximity matching skips over it anyway,
# so it is dropped rather than matched.
_FILLER_RE = re.compile(r"\([^()]*\s[^()]*\)\?")


def compile_phrase(pattern: str) -> list[re.Pattern]:
    slots = []
    for piece in _split_top_level(pattern):
        piece = _FILLER_RE.sub("", piece).strip()
        if piece:
            slots.append(re.compile(rf"^(?:{piece})$"))
    return slots


def match_spans(tokens: list[str], slots: list[re.Pattern],
                max_gap: int = MAX_GAP) -> list[tuple[int, int]]:
    """Non-overlapping ordered matches, as (start, end) token indices.

    Consecutive slots must be within `max_gap` tokens of each other, so the
    phrase may be interrupted but not stretched across a whole sentence. Once a
    chain completes the scan resumes after its last token, so a single mention
    is never counted twice.
    """
    n, i, spans = len(tokens), 0, []
    first = slots[0]
    while i < n:
        if not first.match(tokens[i]):
            i += 1
            continue
        pos, ok = i, True
        for slot in slots[1:]:
            limit = min(n, pos + max_gap + 1)
            nxt = next((j for j in range(pos + 1, limit) if slot.match(tokens[j])), None)
            if nxt is None:
                ok = False
                break
            pos = nxt
        if ok and not BLOCKERS.intersection(tokens[i:pos + 1]):
            spans.append((i, pos))
            i = pos + 1
        else:
            i += 1
    return spans


def count_phrase(tokens: list[str], slots: list[re.Pattern],
                 max_gap: int = MAX_GAP) -> int:
    return len(match_spans(tokens, slots, max_gap))


# ---------------------------------------------------------------------------
# Scoring the corpus
# ---------------------------------------------------------------------------
def build_counts(texts: dict[str, str]) -> tuple[pd.DataFrame, pd.Series]:
    """Per-document phrase counts, and the token count of each document."""
    compiled = [(p, pol, compile_phrase(p)) for p, pol in ALL_PHRASES]
    counts, lengths = {}, {}
    for doc_id, text in texts.items():
        tokens = tokenize(text)
        lengths[doc_id] = len(tokens)
        counts[doc_id] = {p: count_phrase(tokens, slots) for p, _, slots in compiled}
    return (pd.DataFrame(counts).T.fillna(0).astype(int),
            pd.Series(lengths, name="n_tokens"))


def idf_weights(counts: pd.DataFrame) -> pd.Series:
    """ln(N / df), as in Loughran & McDonald. Phrases that never fire get 0."""
    n_docs = len(counts)
    df = (counts > 0).sum()
    idf = np.log(n_docs / df.where(df > 0))
    return idf.fillna(0.0).rename("idf")


def score(texts: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Document-level tone, plus the counts and idf weights behind it."""
    counts, lengths = build_counts(texts)
    idf = idf_weights(counts)
    polarity = pd.Series(dict(ALL_PHRASES))

    weighted = counts.mul(idf, axis=1)
    hawk = weighted.loc[:, polarity == "hawkish"].sum(axis=1)
    dove = weighted.loc[:, polarity == "dovish"].sum(axis=1)

    out = pd.DataFrame({
        "n_tokens": lengths,
        "hawk_hits": counts.loc[:, polarity == "hawkish"].sum(axis=1),
        "dove_hits": counts.loc[:, polarity == "dovish"].sum(axis=1),
        "hawk_tfidf": hawk,
        "dove_tfidf": dove,
        "tone_wordlist": 1000 * (hawk - dove) / lengths,
        # Length-free robustness check. Dividing by total words is what the
        # assignment specifies, but it makes a short document with two hawkish
        # phrases score like a long one with nine -- which matters here, because
        # Warsh's statements run about 185 words against Powell's 410. This
        # polarity ratio lives in [-1, 1] and ignores document length entirely;
        # where the two measures disagree, the report says so.
        "tone_balance": ((hawk - dove) / (hawk + dove)).fillna(0.0),
    })
    return out, counts, idf


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def load_corpus() -> tuple[pd.DataFrame, dict[str, str]]:
    manifest = pd.read_csv(INTERIM_DIR / "manifest.csv", parse_dates=["stamp"])
    root = INTERIM_DIR.parent.parent
    texts = {r.doc_id: (root / r.path).read_text(encoding="utf-8")
             for r in manifest.itertuples()}
    return manifest, texts


def main() -> None:
    manifest, texts = load_corpus()
    print(f"Scoring {len(texts)} documents against "
          f"{len(ALL_PHRASES)} phrases (max gap={MAX_GAP}) ...")
    scores, counts, idf = score(texts)

    panel = manifest.merge(scores, left_on="doc_id", right_index=True)
    panel.to_csv(INTERIM_DIR / "scores_wordlist.csv", index=False)

    # Phrase-level diagnostics: which phrases actually carry the signal.
    polarity = pd.Series(dict(ALL_PHRASES))
    diag = pd.DataFrame({
        "polarity": polarity,
        "total_hits": counts.sum(),
        "doc_freq": (counts > 0).sum(),
        "idf": idf.round(3),
        "tfidf_mass": (counts.sum() * idf).round(1),
    }).sort_values("tfidf_mass", ascending=False)
    diag.index.name = "phrase"
    diag.to_csv(OUTPUT_DIR / "table_a1_phrase_diagnostics.csv")

    dead = diag[diag.total_hits == 0]
    print(f"  {len(diag) - len(dead)} of {len(diag)} phrases fired; "
          f"{len(dead)} never fired")
    if len(dead):
        print("  never fired:", ", ".join(dead.index[:10]))

    print("\nMean tone by document type and Chair:")
    print(panel.pivot_table(index="doc_type", columns="chair",
                            values="tone_wordlist", aggfunc="mean").round(3))
    print("\nWarsh-era documents:")
    cols = ["stamp", "doc_type", "n_tokens", "hawk_hits", "dove_hits",
            "tone_wordlist", "tone_balance"]
    warsh = panel[panel.chair == "Warsh"][cols]
    print(warsh.to_string(index=False, float_format=lambda v: f"{v:8.3f}"))


if __name__ == "__main__":
    main()
