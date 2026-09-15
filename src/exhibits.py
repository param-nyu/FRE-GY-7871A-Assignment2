"""Table 1 and Figure 1: what was collected, and how tone moved over time."""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .config import INTERIM_DIR, OUTPUT_DIR, SAMPLE_END, SAMPLE_START, WARSH_START

TYPE_LABELS = {"statement": "Press release (FOMC statement)",
               "minutes": "Minutes", "speech": "Chair speech / testimony"}
TYPE_ORDER = ["statement", "minutes", "speech"]

TABLE1_NOTES = f"""\
Notes. Sample window {SAMPLE_START} to {SAMPLE_END}; documents are assigned to a
Chair by release date, with the Warsh era beginning {WARSH_START}, the date he was
sworn in. Statements and minutes are complete: every FOMC statement and every FOMC
minutes release in the window is included. Minutes of the Board's discount rate
meetings are a separate document and are excluded.

The speech row is deliberately scoped rather than exhaustive. It covers monetary-
policy communication by the sitting Chair only -- semiannual Monetary Policy Report
testimony to Congress, FOMC post-meeting press conference transcripts, and major
policy speeches (Jackson Hole, and speeches whose title or venue concerns the
outlook, inflation, the labour market or the policy framework). Speeches by other
Governors, supervision and regulation testimony, and ceremonial remarks are
excluded. Collecting every speech either Chair gave was not feasible in the time
available; because statements, minutes and press conference transcripts are all
complete, the Warsh-era evidence does not rest on the speech filter.

The Warsh era is short by construction: he had been in office under four months at
the data cut-off. Every result that depends on it states N on its face."""


def table1(manifest: pd.DataFrame) -> pd.DataFrame:
    counts = pd.crosstab(manifest.doc_type, manifest.chair)
    counts = counts.reindex(TYPE_ORDER).fillna(0).astype(int)
    counts = counts[["Powell", "Warsh"]]
    counts["Total"] = counts.sum(axis=1)

    words = manifest.pivot_table(index="doc_type", columns="chair",
                                 values="n_words", aggfunc="mean")
    words = words.reindex(TYPE_ORDER)[["Powell", "Warsh"]].round(0).astype("Int64")

    out = pd.DataFrame({
        "Document type": [TYPE_LABELS[t] for t in TYPE_ORDER],
        "Powell (2018-02-01 to 2026-05-21)": counts["Powell"].values,
        "Warsh (2026-05-22 to 2026-09-15)": counts["Warsh"].values,
        "Total": counts["Total"].values,
        "Mean words, Powell": words["Powell"].values,
        "Mean words, Warsh": words["Warsh"].values,
    })
    total = {
        "Document type": "All documents",
        "Powell (2018-02-01 to 2026-05-21)": counts["Powell"].sum(),
        "Warsh (2026-05-22 to 2026-09-15)": counts["Warsh"].sum(),
        "Total": counts["Total"].sum(),
        "Mean words, Powell": pd.NA, "Mean words, Warsh": pd.NA,
    }
    return pd.concat([out, pd.DataFrame([total])], ignore_index=True)


def figure1(panel: pd.DataFrame, path=None):
    """Tone over time by document type, with Warsh's start date marked.

    Individual releases are drawn as faint points and a rolling mean as the
    line, so the reader can see both the level shift and how noisy the
    underlying series is -- which matters, given how few Warsh points there are.
    """
    path = path or OUTPUT_DIR / "figure1_tone_over_time.png"
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    colours = {"statement": "#1f4e79", "minutes": "#2e7d32", "speech": "#a1441c"}

    for ax, doc_type in zip(axes, TYPE_ORDER):
        sub = panel[panel.doc_type == doc_type].sort_values("stamp")
        ax.axhline(0, color="0.75", lw=0.8, zorder=1)
        ax.scatter(sub.stamp, sub.tone_wordlist, s=16, alpha=0.35,
                   color=colours[doc_type], zorder=2)
        ax.plot(sub.stamp, sub.tone_wordlist.rolling(5, min_periods=2).mean(),
                color=colours[doc_type], lw=1.8, zorder=3,
                label="5-release rolling mean")

        ax.axvline(pd.Timestamp(WARSH_START), color="crimson", lw=1.4,
                   ls="--", zorder=4)
        ax.annotate("Warsh sworn in\n22 May 2026",
                    xy=(pd.Timestamp(WARSH_START), ax.get_ylim()[1]),
                    xytext=(-96, -34), textcoords="offset points",
                    fontsize=8.5, color="crimson", ha="left")

        warsh = sub[sub.chair == "Warsh"]
        ax.scatter(warsh.stamp, warsh.tone_wordlist, s=42, color="crimson",
                   zorder=5, label=f"Warsh era (n={len(warsh)})")

        ax.set_title(f"{TYPE_LABELS[doc_type]}  (n={len(sub)})",
                     fontsize=10, loc="left")
        ax.set_ylabel("Net hawkish tone\nper 1,000 words", fontsize=9)
        ax.legend(fontsize=8, loc="lower left", framealpha=0.9)
        ax.grid(alpha=0.2)

    axes[-1].set_xlabel("Release date")
    fig.suptitle("Figure 1. Hawkish-dovish tone of Fed communication, 2018-2026\n"
                 "Hand-built tf.idf-weighted word list; positive is hawkish",
                 fontsize=12, y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.955])
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def main() -> None:
    from .validate import load_scores

    manifest = pd.read_csv(INTERIM_DIR / "manifest.csv", parse_dates=["stamp"])
    t1 = table1(manifest)
    t1.to_csv(OUTPUT_DIR / "table1_documents_collected.csv", index=False)
    (OUTPUT_DIR / "table1_notes.txt").write_text(TABLE1_NOTES)
    print("TABLE 1  Documents collected, by type and Chair")
    print(t1.to_string(index=False), "\n")
    print(TABLE1_NOTES, "\n")

    panel = load_scores()
    path = figure1(panel)
    print(f"Figure 1 written to {path}")

    print("\nMean tone by era (word list, positive = hawkish):")
    print(panel.pivot_table(index="doc_type", columns="chair",
                            values="tone_wordlist", aggfunc="mean")
          .reindex(TYPE_ORDER).round(2).to_string())


if __name__ == "__main__":
    main()
