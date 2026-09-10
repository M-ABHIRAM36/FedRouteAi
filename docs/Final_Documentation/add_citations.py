"""Add inline citations + figure/table cross-references INTO the DOCX itself.

Works on a COPY (docs/Final_Documentation/with_citations/) so the original file
is never touched. Nothing about structure, justification, fonts, spacing, images,
tables, or the reference list is changed -- we only:

  1. insert numeric citation markers [n] after key technical terms in the
     chapter body text (linked to the existing [1]-[34] reference list), and
  2. append short in-text references to every figure and table inside the most
     relevant section paragraph.

Citations are inserted by editing the text of the *single run* that already
contains the term, so each run keeps its exact formatting.
"""
from __future__ import annotations

import os
import re
import shutil

from docx import Document

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "FEDROUTEAI DOC Final v1.00.docx")
OUTDIR = os.path.join(HERE, "with_citations")
OUT = os.path.join(OUTDIR, "FEDROUTEAI DOC Final v1.00 (citations).docx")

# term  ->  citation string (numbers match the existing REFERENCES list order).
# Applied at most once per citation-group per chapter, so cites spread naturally.
CITE_RULES = [
    (r"Federated Averaging|\bFedAvg\b", "[17]"),
    (r"\bAdaptive FedAvg\b", "[26]"),
    (r"\bfederated learning\b", "[17], [12]"),
    (r"federated aggregation|aggregation process|aggregation mechanism|\bregional client", "[2]"),
    (r"\bdifferential privacy\b", "[6], [1]"),
    (r"\bsecure aggregation\b", "[12], [20]"),
    (r"Dijkstra", "[5]"),
    (r"\bOpenStreetMap\b|\bOSM\b", "[30]"),
    (r"\bPostGIS\b|PostgreSQL", "[31]"),
    (r"\bFastAPI\b", "[32]"),
    (r"\bReact\b|Leaflet", "[33]"),
    (r"Multilayer Perceptron|\bMLP\b", "[9], [3]"),
    (r"traffic-event|traffic event|\bincident", "[10]"),
    (r"anomaly detection", "[7], [19], [8]"),
    (r"Intelligent Transportation Systems|intelligent transportation|transportation network", "[27], [4]"),
    (r"\bedge\b|large-scale|larger-scale|scalab", "[29], [22], [13]"),
    (r"class imbalance|non-IID|minority", "[16]"),
    (r"trajector", "[28], [21], [14]"),
    (r"precision|recall|false positive", "[11]"),
    (r"privacy-preserving|preserving privacy|\bprivacy\b", "[15], [23]"),
    (r"\bdistributed\b|topology", "[24]"),
    (r"spatiotemporal|spatial-temporal|spatial and temporal|spatial, temporal", "[25]"),
    (r"PyTorch|model artifact|trained model", "[18]"),
    (r"reproducible academic prototype|academic prototype|end-to-end", "[34]"),
]

# figure X.Y  ->  section whose first body paragraph gets the in-text reference
FIG_SECTION = {
    "4.1": "4.1", "4.2": "4.2", "4.3": "4.2", "4.4": "4.4", "4.5": "4.3",
    "4.6": "4.4", "4.7": "4.5", "4.8": "4.5", "4.9": "4.6", "4.10": "4.6",
    "4.11": "4.7", "5.1": "5.1", "5.2": "5.4", "5.3": "5.6", "5.4": "5.6",
    "5.5": "5.7", "5.6": "5.7", "5.7": "5.7", "6.1": "6.4", "6.2": "6.4",
    "6.3": "6.6", "7.1": "7.1",
}
TAB_SECTION = {
    "2.1": "2.5", "3.1": "3.2", "3.2": "3.2", "4.1": "4.3",
    "5.1": "5.1", "5.2": "5.4", "5.3": "5.7", "6.1": "6.1",
}

RE_CHAPTER = re.compile(r"^CHAPTER[-\s]*(\d+)\s*$", re.I)
RE_HEADING = re.compile(r"^(\d+)\.(\d+)\s+\S")
RE_FIGCAP = re.compile(r"^Figure\s+(\d+)\.(\d+)\s*:?\s*(.*)$", re.I)
RE_TABCAP = re.compile(r"^Table\s+(\d+)\.(\d+)\s*:?\s*(.*)$", re.I)


def is_heading(text: str) -> bool:
    return bool(RE_HEADING.match(text)) and len(text) < 70 and not text.endswith(".")


def is_body(text: str) -> bool:
    if len(text) < 120:
        return False
    if text.startswith("[") or text.startswith("Figure ") or text.startswith("Table "):
        return False
    if "\u2192" in text:
        return False
    return True


def cite_paragraph(p, used: set) -> int:
    """Insert [n] after the first in-run match of each unused rule. Returns count."""
    n = 0
    for pattern, cite in CITE_RULES:
        if cite in used:
            continue
        for r in p.runs:
            if not r.text:
                continue
            m = re.search(pattern, r.text, flags=re.I)
            if m:
                e = m.end()
                r.text = r.text[:e] + " " + cite + r.text[e:]
                used.add(cite)
                n += 1
                break
    return n


def append_sentence(p, text: str) -> None:
    """Append a sentence to a paragraph, inheriting the last run's formatting."""
    runs = [r for r in p.runs if r.text and r.text.strip()]
    if runs:
        runs[-1].text = runs[-1].text.rstrip() + " " + text
    else:
        p.add_run(" " + text)


def main() -> None:
    os.makedirs(OUTDIR, exist_ok=True)
    shutil.copyfile(SRC, OUT)

    doc = Document(OUT)
    paras = doc.paragraphs

    # ---- pass 1: citations + capture first body paragraph per section ----
    section_body: dict[str, object] = {}
    fig_desc: dict[str, str] = {}
    tab_desc: dict[str, str] = {}

    started = False
    current_section = None
    used: set = set()
    cite_count = 0
    per_chapter: dict[str, int] = {}
    chap = "0"

    for p in paras:
        text = p.text.strip()
        if not text:
            continue

        mchap = RE_CHAPTER.match(text)
        if mchap:
            started = True
            chap = mchap.group(1)
            used = set()
            per_chapter.setdefault(chap, 0)
            current_section = None
            continue
        if text.upper().startswith("REFERENCES"):
            started = False
            continue

        mfig = RE_FIGCAP.match(text)
        if mfig:
            fig_desc[f"{mfig.group(1)}.{mfig.group(2)}"] = mfig.group(3).strip()
            continue
        mtab = RE_TABCAP.match(text)
        if mtab:
            tab_desc[f"{mtab.group(1)}.{mtab.group(2)}"] = mtab.group(3).strip()
            continue

        if not started:
            continue

        if is_heading(text):
            m = RE_HEADING.match(text)
            current_section = f"{m.group(1)}.{m.group(2)}"
            continue

        if is_body(text):
            if current_section and current_section not in section_body:
                section_body[current_section] = p
            added = cite_paragraph(p, used)
            cite_count += added
            per_chapter[chap] = per_chapter.get(chap, 0) + added

    # ---- pass 2: figure references into relevant section paragraphs ----
    fig_refs = 0
    for num in sorted(FIG_SECTION, key=lambda s: tuple(int(x) for x in s.split("."))):
        sec = FIG_SECTION[num]
        p = section_body.get(sec)
        desc = fig_desc.get(num, "")
        if p is not None and desc:
            append_sentence(p, f"The {desc} is shown in Figure {num}.")
            fig_refs += 1

    # ---- pass 3: table references into relevant section paragraphs ----
    tab_refs = 0
    for num in sorted(TAB_SECTION, key=lambda s: tuple(int(x) for x in s.split("."))):
        sec = TAB_SECTION[num]
        p = section_body.get(sec)
        desc = tab_desc.get(num, "")
        if p is not None and desc:
            append_sentence(p, f"Table {num} presents the {desc}.")
            tab_refs += 1

    doc.save(OUT)

    print(f"saved: {OUT}")
    print(f"citation markers inserted: {cite_count}")
    print(f"  per chapter: " + ", ".join(f"ch{k}={v}" for k, v in sorted(per_chapter.items())))
    print(f"figure references added: {fig_refs}/22")
    print(f"table references added:  {tab_refs}/8")


if __name__ == "__main__":
    main()
