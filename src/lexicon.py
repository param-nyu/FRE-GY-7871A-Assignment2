"""The hand-built hawkish / dovish phrase list.

Loughran and McDonald (2011) show that a word list built for the domain beats a
general-purpose dictionary, and that the useful weighting is tf.idf rather than
raw counts. Their list is built for 10-K filings, though, and its categories
(Negative, Uncertainty, Litigious) do not map onto the policy axis we care
about: "inflation has eased" and "inflation remains elevated" are both roughly
neutral in LM terms but sit at opposite ends of the hawk-dove scale. So the list
below is written from scratch against FOMC language.

Each entry is an ordered sequence of token patterns that must all appear within
``WINDOW`` tokens of one another, in order, but *not* necessarily consecutively
-- the Parsing the Fed word-list method. That matters because the Committee
writes "inflation ... remains elevated", "inflation has remained elevated" and
"inflation is still somewhat elevated" and all three should score the same.

Token patterns are regexes matched against a whole token, so ``eas(e|ed|es|ing)``
covers the inflected forms without a stemmer -- a stemmer would collapse
"tightening" (hawkish) and "tight" (descriptive) into one bucket.
"""

from __future__ import annotations

# Maximum number of tokens between *consecutive* slots of a phrase match. A
# gap budget between adjacent tokens rather than across the whole phrase, so
# "inflation ... has remained ... elevated" still fires but "inflation
# compensation were mixed ... the broad dollar index increased" does not.
MAX_GAP = 5

# Tokens that void a match if they fall inside the matched span. These turn
# inflation-*level* language into market-*pricing* language: a decline in
# inflation compensation is a move in breakeven rates, not the Committee saying
# inflation has come down.
BLOCKERS = frozenset({"compensation", "breakeven", "breakevens", "swap", "swaps"})

# ---------------------------------------------------------------------------
# Hawkish: language that implies firmer policy, or that justifies it.
# ---------------------------------------------------------------------------
HAWKISH: list[str] = [
    # --- the inflation problem, stated as a problem -------------------------
    "inflation elevated",
    "inflation remain(s|ed)? (too )?high",
    "inflation unacceptably high",
    "inflation (has )?(risen|increased|picked up)",
    "inflation above target",
    "inflation above (the )?(committee|2|two) percent",
    "upside risks? inflation",
    "inflation(ary)? pressures?",
    "price pressures?",
    "broad-?based price increases?",
    "wage pressures?",
    "overheating",
    "second-?round effects?",
    "inflation expectations? (rising|rose|drifted|unanchored)",

    # --- firmer policy, stated or signalled ---------------------------------
    "raise target range",
    "increase target range",
    "raising target range",
    "additional (firming|tightening)",
    "further (firming|tightening)",
    "additional rate increases?",
    "further rate increases?",
    "policy firming",
    "tighten(ing)? (of )?(monetary )?policy",
    "restrictive stance",
    "sufficiently restrictive",
    "more restrictive",
    "keep(ing)? policy restrictive",
    "remov(al|e|ing) (of )?(policy )?accommodation",
    "reduce (the )?(size of the )?balance sheet",
    "runoff (of )?(the )?(securities )?holdings",
    "higher (for|longer)",
    "basis points? (increase|higher)",

    # --- resolve language ---------------------------------------------------
    "strongly committed (to )?(returning )?inflation",
    "resolute",
    "vigilant",
    "will deliver price stability",
    "restore price stability",
    "restoring price stability",
    "whatever (takes|necessary)",

    # --- a labour market that argues for firmness ---------------------------
    "labor market (remains? )?tight",
    "tight labor market",
    "labor market tightness",
    "unemployment rate (declined|fell|low)",
    "job gains (robust|strong|solid)",
    "demand exceeds supply",
]

# ---------------------------------------------------------------------------
# Dovish: language that implies easier policy, or that justifies it.
# ---------------------------------------------------------------------------
DOVISH: list[str] = [
    # --- the inflation problem, receding ------------------------------------
    "inflation (has )?eas(ed|ing)",
    "inflation (has )?(declined|moderated|slowed|fallen|cooled)",
    "inflation (has )?(moved|coming) (down|toward)",
    "inflation subdued",
    "inflation (is )?(muted|low|below)",
    "progress (on|toward) (2|inflation) (percent )?(objective|goal|target)",
    "greater confidence inflation",
    "inflation expectations? (well )?anchored",
    "transitory",

    # --- easier policy, stated or signalled ---------------------------------
    "lower target range",
    "reduce target range",
    "lowering target range",
    "cut(ting)? (the )?(target )?rates?",
    "eas(e|ing) (of )?(monetary )?policy",
    "policy easing",
    "accommodat(ive|ion|e)",
    "less restrictive",
    "patient",
    "gradual",
    "increase (the )?(size of the )?balance sheet",
    "purchases? (of )?(treasury|agency|longer-?term) securities",
    "basis points? (decrease|lower|cut)",
    "recalibrat(e|ion|ing)",

    # --- a labour market or economy that argues for ease --------------------
    "downside risks? (to )?(employment|activity|economy|growth)",
    "labor market (has )?(cooled|softened|weakened|eased)",
    "softening (in )?(the )?labor market",
    "job gains (slowed|moderated|weakened)",
    "unemployment rate (rose|risen|increased|edged up)",
    "slack",
    "headwinds",
    "weaker than (expected|anticipated)",
    "activity (slowed|softened|weakened|moderated)",
    "support (employment|economy|recovery)",
    "sustain the expansion",
]

ALL_PHRASES: list[tuple[str, str]] = (
    [(p, "hawkish") for p in HAWKISH] + [(p, "dovish") for p in DOVISH]
)
