"""Build the PDF report from the exhibits in outputs/.

Renders report/report.md to a styled A4 HTML page and prints it to PDF with
headless Chrome. Tables and the figure are injected from outputs/ at build time,
so the report can never drift from the analysis that produced it.

    python report/build_report.py
"""

from __future__ import annotations

import base64
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
REPORT_DIR = ROOT / "report"
BUILD = REPORT_DIR / "build"

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: A4; margin: 17mm 15mm; }
body { font-family: "Charter","Georgia","Times New Roman",serif; font-size: 10.2pt;
       line-height: 1.45; color: #111; }
h1 { font-size: 17pt; margin: 0 0 2pt; }
h2 { font-size: 12.4pt; margin: 16pt 0 5pt; border-bottom: 1px solid #bbb;
     padding-bottom: 2pt; page-break-after: avoid; }
h3 { font-size: 10.8pt; margin: 10pt 0 3pt; font-weight: 600; page-break-after: avoid; }
p { margin: 0 0 7pt; text-align: justify; hyphens: auto; }
table { border-collapse: collapse; width: 100%; margin: 7pt 0 4pt; font-size: 7.6pt;
        page-break-inside: avoid; }
th, td { border: 1px solid #c4c4c4; padding: 2.5pt 4pt; }
th { background: #eee; font-weight: 600; text-align: left; }
td.num, th.num { text-align: right; }
img { max-width: 100%; page-break-inside: avoid; }
.subtitle { color:#444; font-size: 10.4pt; margin: 1pt 0 3pt; }
.byline { color:#555; font-size: 9pt; margin: 0 0 12pt; }
.notes { font-size: 8.2pt; color:#333; line-height:1.35; margin: 2pt 0 12pt;
         text-align: justify; }
.caution { background:#fbf4e4; border-left: 3px solid #c89b30; padding: 6pt 9pt;
           margin: 8pt 0; font-size: 9.2pt; }
.placeholder { background:#f4f4f4; border-left: 3px solid #999; padding: 6pt 9pt;
               margin: 6pt 0; font-size: 9.4pt; color:#444; font-style: italic; }
blockquote { margin: 6pt 0; padding: 5pt 9pt; background:#f6f6f6;
             border-left: 3px solid #999; font-size: 9.2pt; }
code { font-family: "SF Mono", Menlo, monospace; font-size: 8.8pt;
       background:#f2f2f2; padding: 0 2px; }
ul, ol { margin: 0 0 7pt; padding-left: 16pt; }
li { margin-bottom: 2.5pt; }
"""


def df_to_html(df: pd.DataFrame, numeric_from: int = 0) -> str:
    """Table HTML with right-aligned numeric columns and NA rendered blank."""
    head = "".join(
        f'<th class="num">{c}</th>' if i >= numeric_from else f"<th>{c}</th>"
        for i, c in enumerate(df.columns))
    rows = []
    for _, r in df.iterrows():
        cells = []
        for i, v in enumerate(r):
            text = "" if pd.isna(v) else (
                str(v) if not isinstance(v, bool) else ("yes" if v else "no"))
            cells.append(f'<td class="num">{text}</td>' if i >= numeric_from
                         else f"<td>{text}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (f"<table><thead><tr>{head}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def embed_png(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{b64}" alt="{path.stem}">'


def exhibits() -> dict[str, str]:
    """Every {{PLACEHOLDER}} the markdown can reference."""
    t1 = pd.read_csv(OUTPUTS / "table1_documents_collected.csv")
    t2 = pd.read_csv(OUTPUTS / "table2_warsh_event_changes.csv")
    t3r = pd.read_csv(OUTPUTS / "table3_regressions_by_release.csv")
    t3d = pd.read_csv(OUTPUTS / "table3_regressions_collapsed.csv")
    notes = (OUTPUTS / "table1_notes.txt").read_text()
    return {
        "TABLE1": df_to_html(t1, numeric_from=1),
        "TABLE1_NOTES": '<div class="notes">'
                        + "<br>".join(p.replace("\n", " ")
                                      for p in notes.split("\n\n")) + "</div>",
        "FIGURE1": embed_png(OUTPUTS / "figure1_tone_over_time.png"),
        "TABLE2": df_to_html(t2, numeric_from=3),
        "TABLE3_RELEASE": df_to_html(t3r, numeric_from=3),
        "TABLE3_DAY": df_to_html(t3d, numeric_from=3),
    }


# --- a small markdown subset: enough for this document, no dependency ------
# Blocks are gathered as raw line groups first and only then joined and passed
# through `inline`, so bold and italics may span a line break inside a
# paragraph, a list item or a table cell.
def md_to_html(md: str) -> str:
    lines = md.split("\n")
    html: list[str] = []
    i = 0

    def is_table_row(s: str) -> bool:
        return s.lstrip().startswith("|") and s.rstrip().endswith("|")

    while i < len(lines):
        raw = lines[i]
        s = raw.strip()

        if not s:
            i += 1
            continue

        if s.startswith("<"):
            # Injected exhibit HTML, or a hand-written <div> note. A div that
            # does not close on its own line carries prose over several lines;
            # gather them so the block renders as one paragraph, not as one
            # paragraph per source line.
            block = [s]
            if s.startswith("<div") and "</div>" not in s:
                i += 1
                while i < len(lines) and "</div>" not in lines[i]:
                    if lines[i].strip():
                        block.append(lines[i].strip())
                    i += 1
                if i < len(lines):
                    block.append(lines[i].strip())
            opening, *rest = block
            html.append(opening + " " + inline(" ".join(rest)) if rest else opening)
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            level = len(m.group(1))
            html.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        if s == "---":
            html.append("<hr>")
            i += 1
            continue

        if is_table_row(s):
            rows = []
            while i < len(lines) and is_table_row(lines[i].strip()):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            # A --- separator row marks the line above as the header.
            body = [r for r in rows
                    if not all(re.fullmatch(r":?-{2,}:?", c or "-") for c in r)]
            head, body = (body[0], body[1:]) if len(body) > 1 else (None, body)
            out = ["<table>"]
            if head:
                out.append("<thead><tr>"
                           + "".join(f"<th>{inline(c)}</th>" for c in head)
                           + "</tr></thead>")
            out.append("<tbody>")
            for r in body:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r)
                           + "</tr>")
            out.append("</tbody></table>")
            html.append("".join(out))
            continue

        if s.startswith("> "):
            block = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                block.append(lines[i].strip()[2:])
                i += 1
            html.append("<blockquote>"
                        + "<br>".join(inline(b) for b in block)
                        + "</blockquote>")
            continue

        if re.match(r"^[-*]\s+", s):
            items: list[list[str]] = []
            while i < len(lines):
                cur = lines[i]
                if not cur.strip():
                    # A blank line ends the list only if the next line is not
                    # an indented continuation.
                    nxt = lines[i + 1] if i + 1 < len(lines) else ""
                    if not (nxt.startswith("  ") and nxt.strip()):
                        break
                    i += 1
                    continue
                if re.match(r"^[-*]\s+", cur.strip()):
                    items.append([re.sub(r"^[-*]\s+", "", cur.strip())])
                elif items and cur.startswith("  "):
                    items[-1].append(cur.strip())       # continuation line
                else:
                    break
                i += 1
            html.append("<ul>"
                        + "".join(f"<li>{inline(' '.join(it))}</li>" for it in items)
                        + "</ul>")
            continue

        # paragraph: gather until a blank line or the start of another block
        block = []
        while i < len(lines):
            cur = lines[i].strip()
            if (not cur or cur.startswith("<") or cur == "---"
                    or re.match(r"^(#{1,4})\s", cur) or cur.startswith("> ")
                    or re.match(r"^[-*]\s+", cur) or is_table_row(cur)):
                break
            block.append(cur)
            i += 1
        html.append("<p>" + inline(" ".join(block)) + "</p>")

    return "\n".join(html)


def inline(text: str) -> str:
    """Bold, italics and code. Underscores are left alone: they appear inside
    formulas (tf_h, idf_d) far more often than they mark emphasis here."""
    text = re.sub(r"`(.+?)`", lambda m: f"<code>{m.group(1)}</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*]+?)\*(?![\w*])", r"<em>\1</em>", text)
    return text


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    md = (REPORT_DIR / "report.md").read_text()

    for key, value in exhibits().items():
        md = md.replace(f"{{{{{key}}}}}", value)
    missing = re.findall(r"\{\{([A-Z0-9_]+)\}\}", md)
    if missing:
        sys.exit(f"unresolved placeholders in report.md: {sorted(set(missing))}")

    html = (f"<!doctype html><meta charset='utf-8'><style>{CSS}</style>\n"
            + md_to_html(md))
    html_path = BUILD / "report.html"
    html_path.write_text(html)

    pdf_path = REPORT_DIR / "REPORT.pdf"
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf_path}", html_path.as_uri()],
        check=True, capture_output=True)
    print(f"wrote {pdf_path} ({pdf_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
