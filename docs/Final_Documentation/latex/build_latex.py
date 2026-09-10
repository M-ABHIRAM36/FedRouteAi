"""Convert 'FEDROUTEAI DOC Final v1.00.docx' into two Overleaf-ready LaTeX projects.

This is a *faithful converter*, not a content generator: every sentence, table
cell, figure, and reference comes straight out of the DOCX. Two variants are
produced from the same source text:

  v1_normal    -- plain B.Tech report: figures/tables placed, references listed.
  v2_citations -- same words, plus inline \\autoref cross-references to every
                  figure and table and \\cite citations woven into the prose,
                  larger figures on their own float pages (longer render).

Run:  python docs/Final_Documentation/latex/build_latex.py
Output: docs/Final_Documentation/latex/{v1_normal,v2_citations}/main.tex (+figures/)
"""
from __future__ import annotations

import os
import re
import shutil

from docx import Document
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "FEDROUTEAI DOC Final v1.00.docx")
FIGDIR = os.path.join(HERE, "figures")

# ---------------------------------------------------------------------------
# Reference keys, in the exact [1]..[34] order they appear in the DOCX.
# ---------------------------------------------------------------------------
BIB_KEYS = [
    "abadi2016", "beutel2020", "bishop2006", "chen2016", "dijkstra1959",
    "dwork2014", "elmanaa2022", "gao2023", "goodfellow2016", "han2019",
    "hendrycks2017", "kairouz2021", "khan2020", "li2018", "liu2020",
    "lu2024", "mcmahan2017", "paszke2019", "raiyn2014", "shokri2015",
    "su2019", "wang2020", "wei2020", "wu2024", "yang2022",
    "yuan2024", "zhang2025", "zheng2015", "zhou2019", "osm",
    "postgis", "fastapi", "react_leaflet", "projsrc",
]

# (regex, comma-separated cite keys). Applied at most once per key per chapter,
# so citations spread naturally through the body instead of clustering.
CITE_RULES = [
    (r"Federated Averaging|\bFedAvg\b", "mcmahan2017"),
    (r"\bAdaptive FedAvg\b", "yuan2024,lu2024"),
    (r"\bfederated learning\b", "mcmahan2017,kairouz2021,beutel2020"),
    (r"\bdifferential privacy\b", "dwork2014,abadi2016,wei2020"),
    (r"\bsecure aggregation\b", "kairouz2021,shokri2015"),
    (r"Dijkstra", "dijkstra1959"),
    (r"\bOpenStreetMap\b", "osm"),
    (r"\bPostGIS\b|PostgreSQL", "postgis"),
    (r"\bFastAPI\b", "fastapi"),
    (r"\bReact\b|Leaflet", "react_leaflet"),
    (r"\bPyTorch\b", "paszke2019"),
    (r"Multilayer Perceptron|\bMLP\b|model artifact|trained model", "goodfellow2016,bishop2006,paszke2019"),
    (r"traffic-event|traffic event|incident", "han2019"),
    (r"anomaly detection", "elmanaa2022,raiyn2014,gao2023"),
    (r"Intelligent Transportation Systems|intelligent transportation|transportation network", "zhang2025,chen2016"),
    (r"edge|scalability|communication|larger-scale|large-scale", "zhou2019,wang2020,khan2020"),
    (r"class imbalance|non-IID|minority", "lu2024"),
    (r"trajector", "zheng2015,su2019,li2018"),
    (r"precision|recall|false positive", "hendrycks2017"),
    (r"privacy-preserving|privacy", "liu2020"),
    (r"topology|distributed", "wu2024"),
    (r"spatiotemporal|spatial-temporal|spatial and temporal|spatial, temporal", "yang2022"),
    (r"reproducible academic prototype|academic prototype|end-to-end", "projsrc"),
]

# ---------------------------------------------------------------------------
# LaTeX escaping
# ---------------------------------------------------------------------------
_SPECIAL = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def esc(s: str) -> str:
    out = []
    for ch in s:
        if ch in _SPECIAL:
            out.append(_SPECIAL[ch])
        elif ch == "\u201c":
            out.append("``")
        elif ch == "\u201d":
            out.append("''")
        elif ch == "\u2018":
            out.append("`")
        elif ch == "\u2019":
            out.append("'")
        elif ch == "\u2013":
            out.append("--")
        elif ch == "\u2014":
            out.append("---")
        elif ch == "\u2192":
            out.append(r" $\rightarrow$ ")
        elif ch == "\u00d7":
            out.append(r"$\times$")
        elif ch == "\u00b5" or ch == "\u03bc":
            out.append(r"$\mu$")
        elif ch == "\u2248":
            out.append(r"$\approx$")
        else:
            out.append(ch)
    return "".join(out)


def collapse_ws(s: str) -> str:
    return re.sub(r"[ \t]+", " ", s).strip()


# ---------------------------------------------------------------------------
# Load document + anchor helpers
# ---------------------------------------------------------------------------
doc = Document(SRC)
PARAS = list(doc.paragraphs)


def anchor(sub: str) -> str:
    for p in PARAS:
        if sub in p.text:
            return collapse_ws(p.text)
    raise SystemExit(f"anchor not found: {sub!r}")


def para_bold(p: Paragraph) -> bool:
    runs = [r for r in p.runs if r.text.strip()]
    return bool(runs) and all(r.bold for r in runs)


def para_maxsize(p: Paragraph) -> float:
    sizes = [r.font.size.pt for r in p.runs if r.font.size]
    return max(sizes) if sizes else 0.0


# figure files keyed by "x_y" -> filename (handles .png / .jpeg)
FIG_FILES: dict[str, str] = {}
for fn in os.listdir(FIGDIR):
    m = re.match(r"fig_(\d+)_(\d+)\.(png|jpe?g)$", fn)
    if m:
        FIG_FILES[f"{m.group(1)}_{m.group(2)}"] = fn

RE_CHAPTER = re.compile(r"^CHAPTER[-\s]*(\d+)$", re.I)
RE_SECTION = re.compile(r"^(\d+)\.(\d+)\s+([A-Za-z].*)$")
RE_FIGCAP = re.compile(r"^Figure\s+(\d+)\.(\d+)\s*:?\s*(.*)$", re.I)
RE_TABCAP = re.compile(r"^Table\s+(\d+)\.(\d+)\s*:?\s*(.*)$", re.I)
RE_REF = re.compile(r"^\[(\d+)\]\s*(.*)$")
RE_LABELCOLON = re.compile(r"^([A-Za-z0-9][A-Za-z0-9 /()\-]{0,45}?):\s*(.*)$")


# ---------------------------------------------------------------------------
# Front matter (pulled verbatim from the DOCX by anchor)
# ---------------------------------------------------------------------------
TITLE = "FEDROUTEAI: ADAPTIVE FEDERATED LEARNING FOR RESILIENT EDGE-BASED TRAFFIC ANOMALY DETECTION"
STUDENTS = [("MOGULOJU ABHIRAM", "23211A6774"), ("RAJULAPUDI ROHITH", "23211A67A0")]
GUIDE_NAME = "Mrs. S. Jyothsna"
GUIDE_TITLE = "Assistant Professor, Computer Science and Engineering (Data Science)"
DEGREE = "BACHELOR OF TECHNOLOGY"
BRANCH = "Computer Science and Engineering (Data Science)"
INSTITUTE = "B V RAJU INSTITUTE OF TECHNOLOGY"
INSTITUTE_SUB = anchor("An UGC Autonomous")
YEAR = "2026 -- 2027"

CERT = anchor("This is to certify")
DECL = anchor("We hereby declare")
ABSTRACT = anchor("FedRouteAI is a traffic intelligence system")
KEYWORDS = anchor("Keywords:")
ACK = [
    anchor("We would like to express"),
    anchor("Our sincere thanks and gratitude"),
    anchor("We are thankful to our Project Coordinator"),
    anchor("We are greatly thankful and indebted"),
    anchor("Finally, we would also like to thank"),
]
HOD = "Dr. R.V. Ramana Chary"


def abbreviations() -> list[tuple[str, str]]:
    """First content table = LIST OF ABBREVIATIONS (Abbr | Meaning)."""
    for t in doc.tables:
        cells0 = [c.text.strip() for c in t.rows[0].cells]
        if cells0 and cells0[0].upper() in ("AI",):
            rows = []
            for r in t.rows:
                a = collapse_ws(r.cells[0].text)
                b = collapse_ws(r.cells[1].text) if len(r.cells) > 1 else ""
                if a or b:
                    rows.append((a, b))
            return rows
    return []


ABBR = abbreviations()


# ---------------------------------------------------------------------------
# Body walk -> intermediate block list
# Blocks: ('chapter', title) ('section', title) ('label', label, rest)
#         ('sublabel', text) ('para', text) ('flow', [lines])
#         ('figure', x, y, desc) ('table', x, y, desc, rows)
# ---------------------------------------------------------------------------
def build_blocks() -> list[tuple]:
    blocks: list[tuple] = []
    started = False
    expect_title = False
    pending_tab = None  # (x, y, desc)

    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            text = collapse_ws(p.text)

            if not started:
                if RE_CHAPTER.match(text) and RE_CHAPTER.match(text).group(1) == "1":
                    started = True
                else:
                    continue

            if text.upper().startswith("REFERENCES"):
                break
            if not text:
                continue

            mchap = RE_CHAPTER.match(text)
            if mchap:
                expect_title = True
                continue
            if expect_title:
                blocks.append(("chapter", text))
                expect_title = False
                continue

            mfig = RE_FIGCAP.match(text)
            if mfig:
                blocks.append(("figure", mfig.group(1), mfig.group(2),
                               collapse_ws(mfig.group(3))))
                continue

            mtab = RE_TABCAP.match(text)
            if mtab:
                pending_tab = (mtab.group(1), mtab.group(2), collapse_ws(mtab.group(3)))
                continue

            if "\u2192" in text:
                lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
                blocks.append(("flow", lines))
                continue

            msec = RE_SECTION.match(text)
            if msec and len(text) < 70 and not text.endswith("."):
                blocks.append(("section", collapse_ws(msec.group(3))))
                continue

            if para_bold(p):
                mlab = RE_LABELCOLON.match(text)
                if mlab:
                    blocks.append(("label", collapse_ws(mlab.group(1)),
                                   collapse_ws(mlab.group(2))))
                    continue
                if len(text) < 60:
                    blocks.append(("sublabel", text))
                    continue

            blocks.append(("para", text))

        elif isinstance(child, CT_Tbl):
            if not started:
                continue
            t = Table(child, doc)
            rows = []
            for r in t.rows:
                cells = [collapse_ws(c.text) for c in r.cells]
                if any(cells):
                    rows.append(cells)
            if pending_tab is not None:
                x, y, desc = pending_tab
                blocks.append(("table", x, y, desc, rows))
                pending_tab = None
            else:
                blocks.append(("table", None, None, "", rows))

    return blocks


def build_references() -> list[tuple[str, str]]:
    refs = []
    seen = False
    for p in PARAS:
        t = collapse_ws(p.text)
        if t.upper().startswith("REFERENCES"):
            seen = True
            continue
        if not seen:
            continue
        m = RE_REF.match(t)
        if m:
            n = int(m.group(1))
            key = BIB_KEYS[n - 1] if n - 1 < len(BIB_KEYS) else f"ref{n}"
            refs.append((key, collapse_ws(m.group(2))))
    return refs


BLOCKS = build_blocks()
REFS = build_references()


# ---------------------------------------------------------------------------
# Emit LaTeX
# ---------------------------------------------------------------------------
PREAMBLE = r"""%% =====================================================================
%% FedRouteAI B.Tech Major Project Report -- __VARIANT__
%% Auto-generated from "FEDROUTEAI DOC Final v1.00.docx".
%% Compiles on Overleaf with pdfLaTeX. Edit main.tex freely.
%% =====================================================================
\documentclass[12pt,a4paper,oneside]{report}

\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{newtxtext,newtxmath}   % Times New Roman look
\usepackage[a4paper,left=3.25cm,right=2.5cm,top=2.5cm,bottom=2.5cm]{geometry}
\usepackage{graphicx}
\graphicspath{{figures/}}
\usepackage{float}
\usepackage{array}
\usepackage{tabularx}
\usepackage{booktabs}
\usepackage{ragged2e}
\usepackage{setspace}
\usepackage{enumitem}
\usepackage[font=small,labelfont=bf,justification=centering,labelsep=colon]{caption}
\usepackage{titlesec}
\usepackage{fancyhdr}
__HYPERREF__

% ---- wrapping table column ----
\newcolumntype{L}{>{\RaggedRight\arraybackslash}X}

% ---- chapter / section styling ----
\titleformat{\chapter}[display]
  {\centering\normalfont\bfseries}
  {\Large CHAPTER-\thechapter}{1ex}{\LARGE}
\titlespacing*{\chapter}{0pt}{6pt}{26pt}
\titleformat{\section}{\normalfont\large\bfseries}{\thesection}{1em}{}
\titleformat{\subsection}{\normalfont\normalsize\bfseries}{\thesubsection}{1em}{}

% ---- footer: centered page number ----
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0pt}
\fancypagestyle{plain}{\fancyhf{}\fancyfoot[C]{\thepage}\renewcommand{\headrulewidth}{0pt}}

\setlength{\parindent}{0.3in}
__SPACING__
__PARSKIP__

% ---- helper for centered institute block ----
\newcommand{\instituteblock}[1]{%
  \begin{center}\includegraphics[width=3cm]{logo_bvrit.png}\\[4pt]
  {\Large\bfseries #1}\\[2pt]
  {\small Vishnupur, Narsapur, Medak, Telangana, India 502313}\end{center}}

\begin{document}
\pagenumbering{roman}
"""

HYPERREF_V1 = r"\usepackage[hidelinks]{hyperref}"
HYPERREF_V2 = (
    r"\usepackage[colorlinks=true,linkcolor=black,citecolor=blue,"
    r"urlcolor=blue,linktoc=all]{hyperref}"
    "\n"
    r"\usepackage{cleveref}"
)


def title_page() -> str:
    s = []
    s.append(r"\thispagestyle{empty}")
    s.append(r"\begin{center}")
    s.append(r"{\large\bfseries A Major Project Phase-1 Report}\\[6pt]")
    s.append(r"{\large\bfseries On}\\[10pt]")
    s.append(r"{\large\bfseries " + esc(TITLE) + r"}\\[14pt]")
    s.append(r"{In partial fulfillment of the requirements for the award of the degree}\\[4pt]")
    s.append(r"{\itshape Of}\\[6pt]")
    s.append(r"{\large\bfseries " + esc(DEGREE) + r"}\\[4pt]")
    s.append(r"{\itshape In}\\[6pt]")
    s.append(r"{\large\bfseries " + esc(BRANCH) + r"}\\[16pt]")
    s.append(r"{Submitted by,}\\[8pt]")
    for name, roll in STUDENTS:
        s.append(r"{\large " + esc(name) + r" (" + esc(roll) + r")}\\[2pt]")
    s.append(r"\vspace{10pt}{Under the Guidance of}\\[4pt]")
    s.append(r"{\large\bfseries " + esc(GUIDE_NAME) + r"}\\[2pt]")
    s.append(r"{" + esc(GUIDE_TITLE) + r"}\\[14pt]")
    s.append(r"\includegraphics[width=3.2cm]{logo_bvrit.png}\\[10pt]")
    s.append(r"{\large\bfseries " + esc(INSTITUTE) + r"}\\[2pt]")
    s.append(r"{\small " + esc(INSTITUTE_SUB) + r"}\\[10pt]")
    s.append(r"{\bfseries " + esc(YEAR) + r"}")
    s.append(r"\end{center}")
    s.append(r"\clearpage")
    return "\n".join(s)


def certificate_page() -> str:
    s = []
    s.append(r"\thispagestyle{empty}")
    s.append(r"\instituteblock{" + esc(INSTITUTE) + r"}")
    s.append(r"\vspace{6pt}\begin{center}{\Large\bfseries BONAFIDE CERTIFICATE}\end{center}\vspace{6pt}")
    s.append(r"\begin{justify}" + esc(CERT) + r"\end{justify}")
    s.append(r"\vspace{28pt}")
    s.append(r"\noindent\textbf{SIGNATURE}\hfill\textbf{SIGNATURE}\\[2pt]")
    s.append(esc(GUIDE_NAME) + r"\hfill " + esc(HOD) + r"\\[1pt]")
    s.append(r"Supervisor\hfill Head of the Department\\[1pt]")
    s.append(r"Assistant Professor, CSD\hfill Professor, CSD")
    s.append(r"\vspace{34pt}")
    s.append(r"\noindent\textbf{Submitted for Major Project Phase-1 viva-voce examination held on}\\[26pt]")
    s.append(r"\noindent\textbf{INTERNAL EXAMINER}\hfill\textbf{EXTERNAL EXAMINER}")
    return "\n".join(s)


def declaration_page() -> str:
    s = []
    s.append(r"\clearpage")
    s.append(r"\instituteblock{" + esc(INSTITUTE) + r"}")
    s.append(r"\vspace{6pt}\begin{center}{\large\bfseries DECLARATION}\end{center}\vspace{6pt}")
    s.append(r"\begin{justify}" + esc(DECL) + r"\end{justify}")
    s.append(r"\vspace{30pt}\begin{flushright}\textbf{Signature(s)}\end{flushright}\vspace{6pt}")
    for name, roll in STUDENTS:
        s.append(r"\noindent " + esc(name) + r"\hfill " + esc(roll) + r"\\[2pt]")
    s.append(r"\vspace{10pt}\noindent Place:\hspace{4cm}Date:")
    return "\n".join(s)


def acknowledgement_page() -> str:
    s = []
    s.append(r"\clearpage")
    s.append(r"\instituteblock{" + esc(INSTITUTE) + r"}")
    s.append(r"\vspace{6pt}\begin{center}{\large\bfseries ACKNOWLEDGEMENT}\end{center}\vspace{6pt}")
    for a in ACK:
        s.append(r"\begin{justify}" + esc(a) + r"\end{justify}\vspace{4pt}")
    s.append(r"\vspace{16pt}\begin{flushright}")
    for name, roll in STUDENTS:
        s.append(esc(name) + r"\quad " + esc(roll) + r"\\[2pt]")
    s.append(r"\end{flushright}")
    return "\n".join(s)


def abstract_page() -> str:
    s = []
    s.append(r"\clearpage")
    s.append(r"\begin{center}{\Large\bfseries ABSTRACT}\end{center}\vspace{8pt}")
    s.append(r"\begin{justify}" + esc(ABSTRACT) + r"\end{justify}\vspace{8pt}")
    kw = KEYWORDS
    if kw.lower().startswith("keywords:"):
        body = kw.split(":", 1)[1].strip()
        s.append(r"\noindent\textbf{Keywords:} " + esc(body))
    else:
        s.append(r"\begin{justify}" + esc(kw) + r"\end{justify}")
    return "\n".join(s)


def abbreviations_page() -> str:
    s = []
    s.append(r"\clearpage")
    s.append(r"\begin{center}{\Large\bfseries LIST OF ABBREVIATIONS}\end{center}\vspace{8pt}")
    s.append(r"\renewcommand{\arraystretch}{1.3}")
    s.append(r"\noindent\begin{tabularx}{\textwidth}{@{}p{3cm} L@{}}")
    s.append(r"\toprule \textbf{Abbreviation} & \textbf{Description} \\ \midrule")
    for a, b in ABBR:
        s.append(esc(a) + r" & " + esc(b) + r" \\")
    s.append(r"\bottomrule\end{tabularx}")
    return "\n".join(s)


def render_table(x, y, desc, rows, place) -> str:
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    colspec = " ".join(["L"] * ncol)
    s = [r"\begin{table}[" + place + "]", r"\centering"]
    if x and y:
        s.append(r"\caption{" + esc(desc) + r"}")
        s.append(r"\label{tab:" + f"{x}-{y}" + r"}")
    s.append(r"\renewcommand{\arraystretch}{1.25}")
    s.append(r"\begin{tabularx}{\textwidth}{@{}" + colspec + r"@{}}")
    s.append(r"\toprule")
    header = rows[0] + [""] * (ncol - len(rows[0]))
    s.append(" & ".join(r"\textbf{" + esc(c) + "}" for c in header) + r" \\")
    s.append(r"\midrule")
    for row in rows[1:]:
        row = row + [""] * (ncol - len(row))
        s.append(" & ".join(esc(c) for c in row) + r" \\")
    s.append(r"\bottomrule")
    s.append(r"\end{tabularx}")
    s.append(r"\end{table}")
    return "\n".join(s)


def render_figure(x, y, desc, width, place) -> str:
    key = f"{x}_{y}"
    fn = FIG_FILES.get(key)
    if not fn:
        return "% missing figure %s" % key
    s = [r"\begin{figure}[" + place + "]", r"\centering"]
    s.append(r"\includegraphics[width=" + width + r",height=0.82\textheight,keepaspectratio]{" + fn + r"}")
    s.append(r"\caption{" + esc(desc) + r"}")
    s.append(r"\label{fig:" + f"{x}-{y}" + r"}")
    s.append(r"\end{figure}")
    return "\n".join(s)


def inject_citations(text_escaped: str, used: set) -> str:
    """Insert \\cite after the first match of each rule not yet used this chapter."""
    for pattern, keys in CITE_RULES:
        if keys in used:
            continue
        m = re.search(pattern, text_escaped, flags=re.I)
        if m:
            end = m.end()
            text_escaped = text_escaped[:end] + r"~\cite{" + keys + "}" + text_escaped[end:]
            used.add(keys)
    return text_escaped


def build_body(cite: bool, crossref: bool, figw: str, figplace: str, tabplace: str) -> str:
    out = []
    used_keys: set = set()
    for blk in BLOCKS:
        kind = blk[0]
        if kind == "chapter":
            out.append(r"\chapter{" + esc(blk[1]) + r"}")
            used_keys = set()
        elif kind == "section":
            out.append(r"\section{" + esc(blk[1]) + r"}")
        elif kind == "sublabel":
            out.append(r"\subsection*{" + esc(blk[1]) + r"}")
        elif kind == "label":
            label, rest = blk[1], blk[2]
            body = esc(rest)
            if cite and rest:
                body = inject_citations(body, used_keys)
            line = r"\smallskip\noindent\textbf{" + esc(label) + r":}"
            if rest:
                line += " " + body
            out.append(line + r"\par")
        elif kind == "para":
            body = esc(blk[1])
            if cite:
                body = inject_citations(body, used_keys)
            out.append(body + r"\par")
        elif kind == "flow":
            lines = [esc(ln) for ln in blk[1]]
            out.append(r"\begin{center}\ttfamily\small " + r" \\ ".join(lines) + r"\end{center}")
        elif kind == "figure":
            x, y, desc = blk[1], blk[2], blk[3]
            if crossref:
                out.append(r"The " + esc(desc) + r" is illustrated in Figure~\ref{fig:" + f"{x}-{y}" + r"}.\par")
            out.append(render_figure(x, y, desc, figw, figplace))
        elif kind == "table":
            x, y, desc, rows = blk[1], blk[2], blk[3], blk[4]
            if crossref and x and y:
                out.append(r"Table~\ref{tab:" + f"{x}-{y}" + r"} summarizes the " + esc(desc) + r".\par")
            out.append(render_table(x, y, desc, rows, tabplace))
    return "\n\n".join(out)


def build_bibliography() -> str:
    s = [r"\begingroup", r"\setlength{\parindent}{0pt}",
         r"\renewcommand{\bibname}{REFERENCES}",
         r"\begin{thebibliography}{99}",
         r"\setlength{\itemsep}{2pt}"]
    for key, text in REFS:
        s.append(r"\bibitem{" + key + "} " + esc(text))
    s.append(r"\end{thebibliography}")
    s.append(r"\endgroup")
    return "\n".join(s)


def front_matter_lists(cite: bool) -> str:
    """TOC + list of tables + list of figures (auto), correctly ordered."""
    s = []
    s.append(r"\clearpage")
    s.append(r"\renewcommand{\contentsname}{INDEX}")
    s.append(r"\tableofcontents")
    s.append(r"\clearpage")
    s.append(r"\addcontentsline{toc}{chapter}{LIST OF TABLES}")
    s.append(r"\renewcommand{\listtablename}{LIST OF TABLES}")
    s.append(r"\listoftables")
    s.append(r"\clearpage")
    s.append(r"\addcontentsline{toc}{chapter}{LIST OF FIGURES}")
    s.append(r"\renewcommand{\listfigurename}{LIST OF FIGURES}")
    s.append(r"\listoffigures")
    return "\n".join(s)


def assemble(variant: str) -> str:
    v2 = variant == "v2_citations"
    pre = PREAMBLE.replace("__VARIANT__", variant)
    pre = pre.replace("__HYPERREF__", HYPERREF_V2 if v2 else HYPERREF_V1)
    pre = pre.replace("__SPACING__", r"\onehalfspacing")
    pre = pre.replace("__PARSKIP__", r"\setlength{\parskip}{0.5em}" if v2 else r"\setlength{\parskip}{0.2em}")

    figw = r"0.9\textwidth" if v2 else r"0.72\textwidth"
    figplace = "p" if v2 else "htbp"
    tabplace = "htbp"

    parts = [pre]
    # front matter, corrected order:
    # title -> certificate -> declaration -> acknowledgement -> abstract
    #        -> index(toc) -> list of tables -> list of figures -> abbreviations
    parts.append(title_page())
    parts.append(certificate_page())
    parts.append(declaration_page())
    parts.append(acknowledgement_page())
    parts.append(abstract_page())
    parts.append(front_matter_lists(v2))
    parts.append(abbreviations_page())

    # body
    parts.append(r"\clearpage")
    parts.append(r"\pagenumbering{arabic}")
    parts.append(build_body(cite=v2, crossref=v2, figw=figw, figplace=figplace, tabplace=tabplace))

    # references
    parts.append(r"\clearpage")
    parts.append(r"\addcontentsline{toc}{chapter}{REFERENCES}")
    parts.append(build_bibliography())

    parts.append(r"\end{document}")
    return "\n\n".join(parts) + "\n"


def write_variant(variant: str) -> None:
    outdir = os.path.join(HERE, variant)
    os.makedirs(outdir, exist_ok=True)
    # figures copy (self-contained project for Overleaf upload)
    dst_fig = os.path.join(outdir, "figures")
    if os.path.exists(dst_fig):
        shutil.rmtree(dst_fig)
    shutil.copytree(FIGDIR, dst_fig)
    with open(os.path.join(outdir, "main.tex"), "w", encoding="utf-8") as f:
        f.write(assemble(variant))
    n = len(open(os.path.join(outdir, "main.tex"), encoding="utf-8").read())
    print(f"  wrote {variant}/main.tex ({n} bytes) + figures/ ({len(os.listdir(dst_fig))} files)")


if __name__ == "__main__":
    print(f"blocks={len(BLOCKS)}  refs={len(REFS)}  figures={len(FIG_FILES)}  abbr={len(ABBR)}")
    write_variant("v1_normal")
    write_variant("v2_citations")
    print("done.")
