# FedRouteAI Report Format Audit

Audit target: `FedRouteAI_Major_Project_Report.docx`

Generated from `build_report.py` on 2026-08-21. The audit uses both
`docs/docs1.01/team_19_mini_project for reference.docx` and the formal rules in
`docs/clg_docs/report_formats/B.Tech Project Report Format26.docx`.

## Structural Checks

| Check | Result |
|---|---|
| Chapters | 10 dedicated chapter separator pages detected |
| Paragraphs | Expanded document structure generated successfully |
| Chapter layout | `CHAPTER n` and title are centered on a separate page; content starts on the following page |
| Tables | 12 tables |
| Figure placeholders | 22 placeholders |
| Embedded images | 0; figures are intentionally reserved placeholders |
| Front matter | Title page, certificate, declaration, acknowledgement, abstract, contents, lists, and abbreviations are present |
| Front-matter order | Contents, List of Tables, List of Figures, then abbreviations |
| Page size | A4 configured in the generator |
| Margins | 1 inch on all four sides configured in the generator |
| Word-rendered page count | 76 pages |

## Typography And Color

| Check | Result |
|---|---|
| Body typeface | Times New Roman, 12 pt |
| Body alignment | Justified |
| Body line spacing | 1.5 |
| First-line indent | 0.3 inch for normal body paragraphs |
| Chapter headings | Black, bold, centered |
| Section headings | Times New Roman, black, bold; Heading 2 is 13 pt |
| Subsection headings | Times New Roman, black, bold; Heading 3 is 12 pt |
| Content run colors | `000000` only |
| Table shading | `FFFFFF` only |
| Table borders | `000000` only |
| Figure placeholder borders | `000000` only |
| Embedded images | None |
| Certificate spacing | Double spacing applied |
| Acknowledgement spacing | Double spacing applied |
| Abstract spacing | 1.5 spacing and followed by keywords |
| Captions | 11 pt Times New Roman, centered, single spaced |
| References | Left justified and single spaced |

The audit inspected `word/document.xml` for content colors, table shading, and table/figure border colors. The resulting sets were respectively `000000`, `FFFFFF`, and `000000`. Built-in unused Word styles may contain theme definitions, but no colored style is applied to report content.

## Content Integrity

- The exact Geo V2 23-feature order is included in Chapter 4.
- The report identifies eight regional clients: `REGION_01` through `REGION_08`.
- The report records the verified OSM/PostGIS network counts: 2,968 canonical segments and 11,259 directed transitions.
- Controlled demonstrations are limited to Normal, Congestion, and Accident.
- Scenario behavior is explicitly separated from independent model output with the statement: `Traffic behavior only. Not ground truth.`
- Frozen model metrics are reported with their class-imbalance and minority-class limitations.
- The report does not claim differential privacy, secure aggregation, measured production capacity, or unattended safety-critical suitability.

## Pagination

Microsoft Word automation rendered the current document at 76 pages. The DOCX
contains two numbering sections: lower-case Roman numbering for prefacing parts
and Arabic numbering restarted at 1 for Chapter 1 onward. Page numbers are
centered in the footer. The title page is counted as part of the prefacing
sequence, consistent with the formal guideline, even when the visible first-page
number is conventionally omitted during final printing.

The formal format asks for not less than 75 pages of typed matter from Chapter 1
through the appendices. The expanded report includes detailed technical
appendices to meet the intended report depth without changing or fabricating
project results. Final pagination can still shift by one or more pages when
figures are inserted or fields are refreshed.

## Remaining Manual Review

1. Open the DOCX in Word and confirm that no heading is orphaned at the bottom of a page.
2. Refresh contents and list page numbers after final figure insertion.
3. Replace figure placeholders only with reviewed black-and-white or grayscale project figures.
4. Recheck inserted screenshots for secrets, colored UI remnants, and confusion between scenario labels and model predictions.
