# FedRouteAI Report Format Audit

Audit target: `FedRouteAI_Major_Project_Report_FINAL.docx`

Generated from `build_report.py` on 2026-08-21 using the college reference
report and `B.Tech Project Report Format26.docx` as formatting references.

## Structural Checks

| Check | Result |
|---|---|
| Chapters | 10 dedicated chapter separator pages |
| Chapter layout | Centered `CHAPTER n` and title; content starts in the next section |
| Paragraph XML elements | 769 |
| Tables | 12 |
| Figure positions | 22 |
| Embedded technical figures | 17 grayscale PNG images |
| Intentional placeholders | 5 (`5.3` through `5.7`) because no verified UI screenshots are available |
| Front matter | Title, certificate, declaration, acknowledgement, abstract, contents, lists, and abbreviations |
| Page size and margins | A4 with one-inch margins |
| Word-rendered page count | 75 pages |
| Word-rendered word count | 11,762 words |

## Typography And Color

| Check | Result |
|---|---|
| Body typeface | Times New Roman, 12 pt |
| Body alignment and spacing | Justified, 1.5 line spacing, 0.3-inch first-line indent |
| Heading and caption typeface | Times New Roman |
| Content run colors | `000000` only |
| Table shading | `FFFFFF` only |
| Table and placeholder borders | `000000` only |
| Captions | Centered, 11 pt, single spaced |
| References | Left justified and single spaced |

The package audit inspected `word/document.xml`. It found 17 drawings and 17
media files. Applied report content uses only black text, white table fill, and
black borders. Generated diagrams use black, white, and intentional grayscale.

## Content Integrity

- The exact ordered Geo V2 23-feature contract is included.
- The report identifies eight regional clients.
- Verified network counts are 2,968 canonical segments and 11,259 directed transitions.
- Controlled demonstrations remain limited to Normal, Congestion, and Accident.
- Demonstration behavior is explicitly separated from independent model output.
- Frozen model metrics and minority-class limitations are reported without fabrication.
- No differential privacy, secure aggregation, measured production capacity, or safety-critical suitability is claimed.

## Pagination

- Physical title, certificate, declaration, and acknowledgement pages have no footer number.
- Abstract begins a lower-case Roman section configured at `v`; Roman numbering continues through the front matter.
- Chapter separator sections have no footer number.
- Chapter 1 content begins at Arabic `1`.
- Later chapter-content sections use explicit continuation values so numbering does not restart.
- Footer fields are centered, black, and Times New Roman.

Microsoft Word automation rendered the final package at 75 physical pages.
Chapter content starts were derived from that rendering and encoded in the
generator. The DOCX XML contains the section starts `v`, `1`, `4`, `8`, `12`,
`18`, `26`, `31`, `35`, `37`, and `55`. Word’s COM readback was read-only
because the file was open elsewhere, so cached PAGE field text still appeared
as `i`/`1`; updating fields once in an editable Word session refreshes the
displayed values for the local Word version.

## Final Review

The generated package passes structural, image-count, typography, and color
audits. The five UI/demo figure positions remain visibly marked placeholders
because no real screenshots were available and fabricated screenshots were not
permitted.
