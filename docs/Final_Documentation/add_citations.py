"""Add CLICKABLE, blue citations + figure/table cross-references INTO the DOCX.

Works on a COPY (docs/Final_Documentation/with_citations/) so the original file
is never touched. Front matter (title, certificate, declaration, acknowledgement,
abstract, index, lists -- the first ~5-6 pages) is NOT edited: insertion starts
only at CHAPTER-1 and stops at REFERENCES.

What it adds (nothing else changes -- structure, justification, fonts, spacing,
images, tables and the reference list are all preserved):

  1. Inline numeric citations [n] after key terms in the chapter body, each a
     real internal hyperlink (blue + underline) that jumps to reference [n].
  2. In-text references to every figure/table, with "Figure X.Y" / "Table X.Y"
     as blue hyperlinks that jump to that figure/table.
  3. Bookmarks on every reference-list entry and every figure/table caption so
     the hyperlinks have somewhere to land.

Ctrl+Click in Word follows a link (Word's default). The links are blue.
"""
from __future__ import annotations

import copy
import os
import re
import shutil
from collections import Counter

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "FEDROUTEAI DOC Final v1.00.docx")
OUTDIR = os.path.join(HERE, "with_citations")
OUT = os.path.join(OUTDIR, "FEDROUTEAI DOC Final v1.00 (citations).docx")

XMLSPACE = "{http://www.w3.org/XML/1998/namespace}space"
BLUE = "0000FF"

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
RE_REF = re.compile(r"^\[(\d+)\]")


# --------------------------------------------------------------------------
# low-level OXML helpers
# --------------------------------------------------------------------------
def clone_rpr(run):
    if run is None:
        return None
    rpr = run._r.find(qn("w:rPr"))
    return copy.deepcopy(rpr) if rpr is not None else None


def text_run(text, rpr_clone):
    r = OxmlElement("w:r")
    if rpr_clone is not None:
        r.append(copy.deepcopy(rpr_clone))
    t = OxmlElement("w:t")
    t.set(XMLSPACE, "preserve")
    t.text = text
    r.append(t)
    return r


def hyperlink(anchor, text, font_name, sz_half):
    """Internal hyperlink (w:anchor) -> blue, underlined run. Schema-ordered rPr."""
    h = OxmlElement("w:hyperlink")
    h.set(qn("w:anchor"), anchor)
    h.set(qn("w:history"), "1")
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rstyle = OxmlElement("w:rStyle")
    rstyle.set(qn("w:val"), "Hyperlink")
    rpr.append(rstyle)
    if font_name:
        rf = OxmlElement("w:rFonts")
        rf.set(qn("w:ascii"), font_name)
        rf.set(qn("w:hAnsi"), font_name)
        rpr.append(rf)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), BLUE)
    rpr.append(color)
    if sz_half:
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(sz_half))
        rpr.append(sz)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rpr.append(u)
    r.append(rpr)
    t = OxmlElement("w:t")
    t.set(XMLSPACE, "preserve")
    t.text = text
    r.append(t)
    h.append(r)
    return h


def set_r_text(r_el, text):
    for t in r_el.findall(qn("w:t")):
        r_el.remove(t)
    t = OxmlElement("w:t")
    t.set(XMLSPACE, "preserve")
    t.text = text
    r_el.append(t)


def insert_after_match(run, end_offset, nodes):
    """Split `run` at end_offset, drop `nodes` in the gap, keep the tail run."""
    r = run._r
    full = run.text
    before, after = full[:end_offset], full[end_offset:]
    r_after = copy.deepcopy(r)
    run.text = before
    set_r_text(r_after, after)
    parent = r.getparent()
    idx = list(parent).index(r)
    for i, el in enumerate([*nodes, r_after]):
        parent.insert(idx + 1 + i, el)


def add_bookmark(paragraph, name, bmid):
    el = paragraph._p
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bmid))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bmid))
    pPr = el.find(qn("w:pPr"))
    if pPr is not None:
        pPr.addnext(start)
    else:
        el.insert(0, start)
    el.append(end)


def last_text_run(p):
    runs = [r for r in p.runs if r.text and r.text.strip()]
    if runs:
        return runs[-1]
    return p.runs[-1] if p.runs else None


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------
def is_heading(text):
    return bool(RE_HEADING.match(text)) and len(text) < 70 and not text.endswith(".")


def is_body(text):
    if len(text) < 120:
        return False
    if text.startswith("[") or text.startswith("Figure ") or text.startswith("Table "):
        return False
    if "\u2192" in text:
        return False
    return True


def detect_font(doc):
    names, szs = Counter(), Counter()
    for p in doc.paragraphs:
        if len(p.text.strip()) > 150:
            for r in p.runs:
                if r.text and r.font.name:
                    names[r.font.name] += 1
                if r.text and r.font.size:
                    szs[r.font.size.pt] += 1
    name = names.most_common(1)[0][0] if names else "Times New Roman"
    pt = szs.most_common(1)[0][0] if szs else 12.0
    return name, int(round(pt * 2))


# --------------------------------------------------------------------------
def main():
    os.makedirs(OUTDIR, exist_ok=True)
    shutil.copyfile(SRC, OUT)
    doc = Document(OUT)
    paras = doc.paragraphs
    font, sz = detect_font(doc)

    bmid = 1000
    # ---- pass A: bookmarks on references + figure/table captions ----
    ref_bm = fig_bm = tab_bm = 0
    for p in paras:
        t = p.text.strip()
        mref = RE_REF.match(t)
        if mref:
            add_bookmark(p, "ref" + mref.group(1), bmid); bmid += 1; ref_bm += 1
            continue
        mfig = RE_FIGCAP.match(t)
        if mfig:
            add_bookmark(p, f"figure{mfig.group(1)}_{mfig.group(2)}", bmid); bmid += 1; fig_bm += 1
            continue
        mtab = RE_TABCAP.match(t)
        if mtab:
            add_bookmark(p, f"table{mtab.group(1)}_{mtab.group(2)}", bmid); bmid += 1; tab_bm += 1

    # ---- pass B: citations + capture first body paragraph per section ----
    section_body = {}
    fig_desc, tab_desc = {}, {}
    started = False
    current_section = None
    used = set()
    chap = "0"
    cite_count = 0
    per_chapter = {}

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
            for pattern, cite in CITE_RULES:
                if cite in used:
                    continue
                for run in list(p.runs):
                    if not run.text:
                        continue
                    m = re.search(pattern, run.text, flags=re.I)
                    if m:
                        # extend to the end of the whole word so we never split it
                        # (e.g. "trajector"->"trajectory", "scalab"->"scalability",
                        #  "MLP"->"MLP-based", "Dijkstra"->"Dijkstra's")
                        rt = run.text
                        e = m.end()
                        while e < len(rt):
                            c = rt[e]
                            if c.isalpha() or c in "'\u2019":
                                e += 1
                            elif c == "-" and e + 1 < len(rt) and rt[e + 1].isalpha():
                                e += 1
                            else:
                                break
                        nums = re.findall(r"\d+", cite)
                        rpr = clone_rpr(run)
                        nodes = [text_run(" ", rpr)]
                        for i, num in enumerate(nums):
                            if i:
                                nodes.append(text_run(", ", rpr))
                            nodes.append(hyperlink("ref" + num, "[" + num + "]", font, sz))
                        insert_after_match(run, e, nodes)
                        used.add(cite)
                        cite_count += 1
                        per_chapter[chap] += 1
                        break

    # ---- pass C: clickable figure references ----
    fig_refs = 0
    for num in sorted(FIG_SECTION, key=lambda s: tuple(int(x) for x in s.split("."))):
        p = section_body.get(FIG_SECTION[num])
        desc = fig_desc.get(num, "")
        if p is not None and desc:
            rpr = clone_rpr(last_text_run(p))
            p._p.append(text_run(f" The {desc} is shown in ", rpr))
            p._p.append(hyperlink(f"figure{num.replace('.', '_')}", f"Figure {num}", font, sz))
            p._p.append(text_run(".", rpr))
            fig_refs += 1

    # ---- pass D: clickable table references ----
    tab_refs = 0
    for num in sorted(TAB_SECTION, key=lambda s: tuple(int(x) for x in s.split("."))):
        p = section_body.get(TAB_SECTION[num])
        desc = tab_desc.get(num, "")
        if p is not None and desc:
            rpr = clone_rpr(last_text_run(p))
            p._p.append(text_run(" ", rpr))
            p._p.append(hyperlink(f"table{num.replace('.', '_')}", f"Table {num}", font, sz))
            p._p.append(text_run(f" presents the {desc}.", rpr))
            tab_refs += 1

    doc.save(OUT)

    print(f"saved: {OUT}")
    print(f"body font detected: {font} {sz//2}pt")
    print(f"bookmarks -> references={ref_bm} figures={fig_bm} tables={tab_bm}")
    print(f"citation hyperlinks inserted: {cite_count}")
    print("  per chapter: " + ", ".join(f"ch{k}={v}" for k, v in sorted(per_chapter.items())))
    print(f"figure hyperlinks added: {fig_refs}/22")
    print(f"table hyperlinks added:  {tab_refs}/8")


if __name__ == "__main__":
    main()
