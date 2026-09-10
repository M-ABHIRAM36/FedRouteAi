# FedRouteAI — LaTeX report (Overleaf-ready)

Two LaTeX versions generated **faithfully** from `FEDROUTEAI DOC Final v1.00.docx`.
No new content was written — same text, tables, figures, and 34 references.

## The two versions

| | `v1_normal/` | `v2_citations/` |
|---|---|---|
| Text / tables / figures | Identical (from your docx) | Identical (from your docx) |
| Figure & table cross-references | none (placed as-is) | `Figure~\ref{}` / `Table~\ref{}` woven into the prose |
| Reference citations | listed only (`[1]`–`[34]`) | inline `\cite{}` throughout (all 34 cited) |
| Hyperlinks | off (`hidelinks`) | on (colored links + `cleveref`) |
| Figure size / placement | 0.72\textwidth, inline | 0.9\textwidth, own float pages |
| Approx. length | ~40 pp | ~70+ pp (target ≈ 72) |

Both compile with **pdfLaTeX** and use Times New Roman (`newtxtext`), A4, 1.5 spacing,
centered page numbers, and per-chapter figure/table numbering (Figure 4.1, Table 5.2, …).

## Use in Overleaf (easiest path)

1. Overleaf → **New Project → Upload Project**.
2. Upload `FedRouteAI_LaTeX_v1_normal.zip` (or `..._v2_citations.zip`).
3. Menu → **Compiler = pdfLaTeX**. Click **Recompile**.

Each folder is self-contained (`main.tex` + `figures/`), so you can also just upload
a folder's contents. `main.tex` is a single editable file.

## Front-matter order (corrected)

Your docx had the Index before the Abstract and Abbreviations before the figure/table
lists. The LaTeX follows the standard B.Tech order and auto-numbers the pages:

Title → Certificate → Declaration → Acknowledgement → Abstract →
Index (Table of Contents) → List of Tables → List of Figures →
List of Abbreviations → **Chapter 1 (page 1, arabic)** → … → References.

Front matter is lowercase roman; body restarts at arabic `1`. The TOC / List of
Tables / List of Figures are generated automatically, so their page numbers always
match the body — no manual mismatch possible.

## Tuning Version 2 to exactly ~72 pages

Open `v2_citations/main.tex` and adjust any of these (near the top / in figures):

- Line spacing: change `\onehalfspacing` → `\doublespacing` (longer) or `\setstretch{1.4}`.
- `\setlength{\parskip}{0.5em}` — increase for more space between paragraphs.
- Figure width: the `width=0.9\textwidth` inside `\includegraphics` (larger = longer).
- To force **one figure per page**, add `\clearpage` after any `\end{figure}`.

## Regenerating (optional)

If you edit the source docx, rerun the converter:

```
python docs/Final_Documentation/latex/build_latex.py
```

It rewrites both `main.tex` files and refreshes each `figures/` folder.

## Notes

- Figures 4.1–7.1 are the real images extracted from the docx (`figures/fig_<chap>_<n>`).
- References use a `thebibliography` block (numbered `[1]`–`[34]`), editable directly in
  `main.tex`; no `.bib` / bibtex run needed.
- Pipeline "flow" lines (e.g. `Telemetry → … → Map`) are set as centered monospace.
