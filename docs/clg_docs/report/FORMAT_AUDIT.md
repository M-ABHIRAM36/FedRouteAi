# FedRouteAI Report Format Audit

Audit target: `FedRouteAI_Major_Project_Report.docx`

Generated from `build_report.py` on 2026-08-21.

## Structural Checks

| Check | Result |
|---|---|
| Chapters | 10 chapter breaks detected |
| Paragraphs | 446 document paragraphs |
| Section headings | 118 Heading-style paragraphs |
| Tables | 12 tables |
| Figure placeholders | 22 placeholders |
| Embedded images | 0; figures are intentionally reserved placeholders |
| Front matter | Title page, certificate, declaration, acknowledgement, abstract, contents, lists, and abbreviations are present |
| Page size | A4 configured in the generator |
| Margins | 1 inch on all four sides configured in the generator |

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

The audit inspected `word/document.xml` for content colors, table shading, and table/figure border colors. The resulting sets were respectively `000000`, `FFFFFF`, and `000000`. Built-in unused Word styles may contain theme definitions, but no colored style is applied to report content.

## Content Integrity

- The exact Geo V2 23-feature order is included in Chapter 4.
- The report identifies eight regional clients: `REGION_01` through `REGION_08`.
- The report records the verified OSM/PostGIS network counts: 2,968 canonical segments and 11,259 directed transitions.
- Controlled demonstrations are limited to Normal, Congestion, and Accident.
- Scenario behavior is explicitly separated from independent model output with the statement: `Traffic behavior only. Not ground truth.`
- Frozen model metrics are reported with their class-imbalance and minority-class limitations.
- The report does not claim differential privacy, secure aggregation, measured production capacity, or unattended safety-critical suitability.

## Pagination Note

The environment does not contain LibreOffice, `soffice`, or another DOCX layout renderer, so a final Word-rendered page count could not be measured here. Based on the A4 dimensions, one-inch margins, 12 pt Times New Roman body text, 1.5 spacing, 10 chapter breaks, 22 reserved figure areas, and 12 tables, the generated document is expected to render in the requested approximately 50–60 page range. The contents page uses planned chapter positions and should be refreshed in Word after the final visual review if exact page numbers are required.

## Remaining Manual Review

1. Open the DOCX in Word or LibreOffice and confirm that no heading is orphaned at the bottom of a page.
2. Refresh the table of contents and list-of-figures page numbers after final pagination.
3. Replace figure placeholders only with reviewed black-and-white or grayscale project figures.
4. Recheck inserted screenshots for secrets, colored UI remnants, and confusion between scenario labels and model predictions.
