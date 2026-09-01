from __future__ import annotations

from pathlib import Path
import re
import zipfile
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "FedRouteAI_Major_Project_Report.docx"

TITLE = "FedRouteAI: Adaptive Federated Learning for Resilient Edge-Based Traffic Anomaly Detection"
STUDENTS = [("MOGULOJU ABHIRAM", "23211A6774"), ("RAJULAPUDI ROHITH", "23211A67A0")]
GUIDE = "Mrs. S. Jyothsna"
DEPARTMENT = "Computer Science and Engineering (Data Science)"
COLLEGE = "B V RAJU INSTITUTE OF TECHNOLOGY"
ADDRESS = "Vishnupur, Narsapur, Medak, Telangana, India 502313"
# Chapter separator pages are intentionally unnumbered and do not consume the
# displayed Arabic sequence. Values are measured from the current Word layout.
MAIN_PAGE_STARTS: dict[int, int] = {1: 1, 2: 4, 3: 8, 4: 12, 5: 19, 6: 25, 7: 30, 8: 33}
FIGURE_IMAGES = {
    "4.1": "fig_4_1_overall_architecture.png",
    "4.2": "fig_4_2_federated_learning.png",
    "4.3": "fig_4_3_regional_client_server.png",
    "4.4": "fig_4_4_end_to_end_pipeline.png",
    "4.5": "fig_4_5_geo_v2_features.png",
    "4.6": "fig_4_6_historical_memory.png",
    "4.7": "fig_4_7_osm_postgis.png",
    "4.8": "fig_4_8_directed_network.png",
    "4.9": "fig_4_9_backend_architecture.png",
    "4.10": "fig_4_10_frontend_architecture.png",
    "4.11": "fig_4_11_directed_shortest_path.png",
    "5.1": "fig_5_1_live_gps_ingestion.png",
    "6.1": "fig_6_1_model_validation.png",
    "6.2": "fig_6_2_confusion_matrix.png",
    "6.3": "fig_6_3_test_evidence.png",
    "7.1": "fig_7_1_local_deployment.png",
}
RESERVED_SCREENSHOT_FIGURES = {"5.2", "5.3", "5.4", "5.5", "5.6", "5.7"}


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "FFFFFF")
    tc_pr.append(shd)


def set_cell_text(cell, text: str, bold: bool = False, size: float = 9) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.bold = bold
    r.font.name = "Times New Roman"
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor(0, 0, 0)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0


def add_page_number(paragraph, initial: str = "1") -> None:
    paragraph.clear()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "separate")
    result = OxmlElement("w:t")
    result.text = initial
    fld_char3 = OxmlElement("w:fldChar")
    fld_char3.set(qn("w:fldCharType"), "end")
    run._r.extend([fld_char1, instr, fld_char2, result, fld_char3])
    run.font.name = "Times New Roman"
    run.font.size = Pt(10)


def configure_section(section, *, fmt: str, start: int | None, show_number: bool) -> None:
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(3.25)
    section.right_margin = Cm(2.5)
    section.header_distance = Inches(0.5)
    section.footer_distance = Inches(0.5)
    section.footer.is_linked_to_previous = False
    section.footer.paragraphs[0].clear()
    if show_number:
        add_page_number(section.footer.paragraphs[0], str(start or 1))
    for element in list(section._sectPr):
        if element.tag == qn("w:pgNumType"):
            section._sectPr.remove(element)
    pg_num_type = OxmlElement("w:pgNumType")
    pg_num_type.set(qn("w:fmt"), fmt)
    if start is not None:
        pg_num_type.set(qn("w:start"), str(start))
    section._sectPr.append(pg_num_type)


def front_section(doc: Document, *, roman_start: int | None = None, show_number: bool = False) -> None:
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    configure_section(section, fmt="lowerRoman", start=roman_start, show_number=show_number)


def add_field(paragraph, instruction: str) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, end])
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)


def configure_document(doc: Document) -> None:
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3.25)
        section.right_margin = Cm(2.5)
        section.header_distance = Inches(0.5)
        section.footer_distance = Inches(0.5)
        section.footer.is_linked_to_previous = False
        section.footer.paragraphs[0].clear()
        pg_num_type = OxmlElement("w:pgNumType")
        pg_num_type.set(qn("w:fmt"), "lowerRoman")
        pg_num_type.set(qn("w:start"), "1")
        section._sectPr.append(pg_num_type)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.first_line_indent = Inches(0.3)
    normal.font.color.rgb = RGBColor(0, 0, 0)

    for name, size in (("Heading 1", 14), ("Heading 2", 13), ("Heading 3", 13)):
        style = doc.styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.line_spacing = 1.5
        style.paragraph_format.space_before = Pt(6)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True

    if "Table Text" not in [s.name for s in doc.styles]:
        style = doc.styles.add_style("Table Text", WD_STYLE_TYPE.PARAGRAPH)
        style.font.name = "Times New Roman"
        style.font.size = Pt(10)
        style.paragraph_format.line_spacing = 1.0
        style.paragraph_format.space_after = Pt(0)
        style.font.color.rgb = RGBColor(0, 0, 0)

    for name in ("Figure Caption", "Table Caption", "Application Screenshot Caption"):
        if name not in [s.name for s in doc.styles]:
            style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
            style.font.name = "Times New Roman"
            style.font.size = Pt(11)
            style.font.color.rgb = RGBColor(0, 0, 0)
            style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            style.paragraph_format.line_spacing = 1.0
            style.paragraph_format.space_after = Pt(6)

    # Remove theme-dependent colors from the styles that Word may apply when
    # opening a generated document with a different template.
    for style in doc.styles:
        if hasattr(style, "font"):
            style.font.name = "Times New Roman"
            if style.font.color is not None:
                style.font.color.rgb = RGBColor(0, 0, 0)


def p(doc: Document, text: str, *, align=None, indent=True, after=6, bold=False, size=12):
    para = doc.add_paragraph()
    para.alignment = align or WD_ALIGN_PARAGRAPH.JUSTIFY
    para.paragraph_format.line_spacing = 1.5
    para.paragraph_format.space_after = Pt(after)
    para.paragraph_format.first_line_indent = Inches(0.3) if indent and align != WD_ALIGN_PARAGRAPH.CENTER else Inches(0)
    run = para.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0, 0, 0)
    run.bold = bold
    return para


def chapter(doc: Document, number: int, title: str) -> None:
    title_section = doc.add_section(WD_SECTION.NEW_PAGE)
    configure_section(title_section, fmt="decimal", start=None, show_number=False)
    chapter_label = p(doc, f"CHAPTER {number}", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=12, bold=True, size=14)
    chapter_label.paragraph_format.space_before = Inches(1.5)
    title_para = p(doc, title.upper(), align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=12, bold=True, size=14)
    title_para.style = doc.styles["Heading 1"]
    content_section = doc.add_section(WD_SECTION.NEW_PAGE)
    configure_section(content_section, fmt="decimal", start=MAIN_PAGE_STARTS.get(number), show_number=True)


def heading(doc: Document, text: str, level: int = 2) -> None:
    para = doc.add_paragraph(style=f"Heading {level}")
    para.paragraph_format.first_line_indent = Inches(0)
    para.add_run(text)


def table(doc: Document, caption: str, headers: list[str], rows: list[list[str]]) -> None:
    caption_para = p(doc, caption, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=6, bold=True, size=11)
    caption_para.style = doc.styles["Table Caption"]
    add_field(caption_para, f'TC "{caption}" \\f T')
    caption_para.paragraph_format.line_spacing = 1.0
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, value in enumerate(headers):
        set_cell_text(t.rows[0].cells[i], value, bold=True)
        set_cell_shading(t.rows[0].cells[i], "FFFFFF")
    for row in rows:
        cells = t.add_row().cells
        for i, value in enumerate(row):
            set_cell_text(cells[i], value)
        tr_pr = t.rows[-1]._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def figure(doc: Document, number: str, caption: str, height: float = 1.45) -> None:
    box = doc.add_paragraph()
    box.alignment = WD_ALIGN_PARAGRAPH.CENTER
    box.paragraph_format.first_line_indent = Inches(0)
    box.paragraph_format.space_before = Pt(6)
    box.paragraph_format.space_after = Pt(4)
    box.paragraph_format.line_spacing = 1.0
    image = ROOT.parent / "figures" / "png" / FIGURE_IMAGES[number] if number in FIGURE_IMAGES and number not in RESERVED_SCREENSHOT_FIGURES else None
    if image is not None and image.exists():
        run = box.add_run()
        run.add_picture(str(image), width=Inches(5.5))
    else:
        run = box.add_run(f"[Verified application screenshot not yet available: {caption}]")
        run.font.name = "Times New Roman"
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0, 0, 0)
        boxPr = OxmlElement("w:pBdr")
        for edge in ("top", "left", "bottom", "right"):
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), "8")
            el.set(qn("w:space"), "6")
            el.set(qn("w:color"), "000000")
            boxPr.append(el)
        box._p.get_or_add_pPr().append(boxPr)
        box.paragraph_format.space_after = Pt(3)
        box.paragraph_format.keep_together = True
    box.paragraph_format.line_spacing = 1.5
    box.paragraph_format.keep_with_next = True
    is_screenshot = number in RESERVED_SCREENSHOT_FIGURES
    label = f"Application Screenshot {number} {caption}" if is_screenshot else f"Figure {number} {caption}"
    caption_para = p(doc, label, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=8, size=11)
    caption_para.style = doc.styles["Application Screenshot Caption" if is_screenshot else "Figure Caption"]
    add_field(caption_para, f'TC "{label}" \\f {"S" if is_screenshot else "F"}')
    caption_para.paragraph_format.line_spacing = 1.0


def application_screenshot_entry(doc: Document, number: str, caption: str) -> None:
    """Add a compact register entry without pretending a screenshot exists."""
    label = f"Application Screenshot {number} {caption}"
    caption_para = p(doc, f"{label} - verified screenshot not yet available.", indent=False, after=3, size=10)
    caption_para.style = doc.styles["Application Screenshot Caption"]
    add_field(caption_para, f'TC "{label}" \\f S')


def front_matter(doc: Document) -> None:
    p(doc, "A MAJOR PROJECT REPORT", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=12, bold=True, size=16)
    p(doc, "ON", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=8, bold=True, size=13)
    p(doc, TITLE.upper(), align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=24, bold=True, size=16)
    p(doc, "Submitted by,", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=10, size=12)
    for name, roll in STUDENTS:
        p(doc, f"{name}    {roll}", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=4, bold=True, size=12)
    p(doc, "\nIn partial fulfillment of the requirements for the award of the degree\nOf\nBACHELOR OF TECHNOLOGY\nIn\n" + DEPARTMENT, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=20, size=12)
    p(doc, f"Under the Guidance of\n{GUIDE}\nAssistant Professor, {DEPARTMENT}", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=28, size=12)
    p(doc, f"{COLLEGE}\n(An UGC Autonomous Institution, Approved by AICTE, New Delhi and Affiliated to JNTUH, Hyderabad)\n{ADDRESS}\n\nAPRIL - 2026", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=0, bold=True, size=12)

    front_section(doc)
    certificate_start = len(doc.paragraphs)
    p(doc, COLLEGE, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=4, bold=True, size=13)
    p(doc, ADDRESS, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=18, size=11)
    p(doc, "BONAFIDE CERTIFICATE", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=18, bold=True, size=14)
    p(doc, f'This is to certify that this major project work entitled "{TITLE}", submitted by MOGULOJU ABHIRAM ({STUDENTS[0][1]}) and RAJULAPUDI ROHITH ({STUDENTS[1][1]}) to B V Raju Institute of Technology affiliated to JNTUH, Hyderabad, in partial fulfillment for the award of Bachelor of Technology in Computer Science and Engineering (Data Science), is a bonafide record of project work carried out under my supervision during the academic year 2025 - 2026 and that this work has not been submitted elsewhere for a degree.', after=36)
    table(doc, "", ["Supervisor", "Head of the Department"], [[f"{GUIDE}\nAssistant Professor", "Dr. R. V. Ramana Chary\nProfessor"]])
    p(doc, "Project Coordinator: Mr. Purnachandrarao Murala, Assistant Professor, CSE (Data Science)", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=32, size=11)
    p(doc, "Internal Examiner                         External Examiner", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=0, bold=True, size=11)
    for para in doc.paragraphs[certificate_start:]:
        para.paragraph_format.line_spacing = 2.0

    front_section(doc)
    declaration_start = len(doc.paragraphs)
    p(doc, COLLEGE, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=4, bold=True, size=13)
    p(doc, "DECLARATION", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=18, bold=True, size=14)
    p(doc, f'We hereby declare that the project titled "{TITLE}", submitted to B V Raju Institute of Technology (Autonomous) and affiliated with JNTUH, Hyderabad, in partial fulfillment of the requirements for the award of a Bachelor of Technology in Computer Science and Engineering (Data Science), represents our work and ideas in our own words. Wherever other authors\' ideas, methods, software, datasets, or words have been used, the original sources have been acknowledged through appropriate citations and references. We further declare that no claim of differential privacy, secure aggregation, formal privacy guarantee, or production deployment is made beyond the capabilities verified in the current implementation. We have adhered to the principles of academic honesty and integrity and have not fabricated or falsified any technical result.', after=18)
    p(doc, "Signatures:\n\n\nMOGULOJU ABHIRAM                         RAJULAPUDI ROHITH\n\nPlace: ____________________              Date: ____________________", indent=False, after=0)
    for para in doc.paragraphs[declaration_start:]:
        para.paragraph_format.line_spacing = 1.5

    front_section(doc)
    acknowledgement_start = len(doc.paragraphs)
    p(doc, COLLEGE, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=4, bold=True, size=13)
    p(doc, "ACKNOWLEDGEMENT", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=18, bold=True, size=14)
    p(doc, "We express our sincere thanks to the Principal of B V Raju Institute of Technology for providing the facilities and academic environment required to complete this major project.")
    p(doc, "We are grateful to Dr. R. V. Ramana Chary, Professor and Head of the Department of Computer Science and Engineering (Data Science), for the support, review, and encouragement provided throughout the project work.")
    p(doc, "We thank Mr. Purnachandrarao Murala, Assistant Professor and Project Coordinator, for coordinating the project activities and providing timely suggestions during the development and documentation stages.")
    p(doc, f"We are especially thankful to our internal guide, {GUIDE}, Assistant Professor, Department of Computer Science and Engineering (Data Science), for her continuous guidance, technical feedback, and encouragement throughout the project.")
    p(doc, "Finally, we thank all faculty members, staff, parents, and friends who supported us directly or indirectly in completing this work.")
    for para in doc.paragraphs[acknowledgement_start:]:
        para.paragraph_format.line_spacing = 2.0

    front_section(doc, roman_start=5, show_number=True)
    p(doc, "ABSTRACT", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=18, bold=True, size=14)
    p(doc, "FedRouteAI is a traffic intelligence system for detecting temporary road events from GPS-derived traffic behavior and supporting route inspection. The system combines geographically grounded synthetic traffic data, OpenStreetMap road geometry, PostGIS persistence, historical traffic memory, causal feature construction, federated learning, a frozen Geo V2 multilayer perceptron, and a React-Leaflet live map. Eight regional clients train locally and contribute model updates through FedAvg-style aggregation with adaptive weighting. Raw training or live traffic records are not required to be centralized for model inference.")
    p(doc, "The current Geo V2 runtime uses an ordered 23-feature contract containing current traffic state, temporal encodings, road metadata, historical baselines, baseline deviations, prior-window trends, low-speed persistence, and directed-neighbor information. The model is executed in a label-free manner: scenario labels and ground-truth metadata are excluded from inference features. Live telemetry is ingested, associated with road segments, aggregated, combined with history, passed through the frozen model, and persisted as prediction state for the map. The system also imports a Beeramguda/Ashok Nagar OSM network containing 2,968 canonical segments and 11,259 directed transitions.")
    p(doc, "The project includes a five-hour controlled demonstration with 1,000 persistent vehicles and 150 simulated ten-minute ticks. It also provides a route-bound demonstration in which the user calculates a directed route of at least 1.5 km and selects Normal, Congestion, or Accident behavior. Such scenario behavior is explicitly treated as demonstration traffic and not as model ground truth. The completed implementation demonstrates an end-to-end academic prototype while retaining clear limitations in event-class recall, data realism, operational privacy controls, and traffic-aware routing.")
    p(doc, "Keywords: Federated Learning, Traffic Anomaly Detection, Geo V2, GPS Telemetry, Historical Traffic Memory, OpenStreetMap, PostGIS, Multilayer Perceptron, Adaptive FedAvg, Directed Routing.", indent=False, after=0)


def lists(doc: Document) -> None:
    doc.add_page_break()
    p(doc, "CONTENTS", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14, bold=True, size=14)
    toc = doc.add_paragraph()
    toc.alignment = WD_ALIGN_PARAGRAPH.LEFT
    toc.paragraph_format.line_spacing = 1.0
    add_field(toc, 'TOC \\o "1-2" \\h \\z \\u')
    p(doc, "ABSTRACT", indent=False, after=3, size=11)
    p(doc, "DECLARATION", indent=False, after=3, size=11)
    p(doc, "LIST OF TABLES", indent=False, after=3, size=11)
    p(doc, "LIST OF FIGURES", indent=False, after=3, size=11)
    p(doc, "LIST OF SYMBOLS, ABBREVIATIONS AND NOMENCLATURE", indent=False, after=3, size=11)
    doc.add_page_break()
    p(doc, "LIST OF TABLES", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14, bold=True, size=14)
    table_list = doc.add_paragraph()
    table_list.paragraph_format.line_spacing = 1.0
    add_field(table_list, 'TOC \\f T \\h \\z')
    doc.add_page_break()
    p(doc, "LIST OF FIGURES", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14, bold=True, size=14)
    figure_list = doc.add_paragraph()
    figure_list.paragraph_format.line_spacing = 1.0
    add_field(figure_list, 'TOC \\f F \\h \\z')
    doc.add_page_break()
    p(doc, "LIST OF APPLICATION SCREENSHOTS", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14, bold=True, size=14)
    screenshot_list = doc.add_paragraph()
    screenshot_list.paragraph_format.line_spacing = 1.0
    add_field(screenshot_list, 'TOC \\f S \\h \\z')
    doc.add_page_break()
    p(doc, "LIST OF SYMBOLS, ABBREVIATIONS AND NOMENCLATURE", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14, bold=True, size=14)
    table(doc, "Table 0.1: Symbols and abbreviations", ["Symbol / abbreviation", "Meaning"], [["AI", "Artificial Intelligence"], ["API", "Application Programming Interface"], ["CPU", "Central Processing Unit"], ["F1", "Harmonic mean of precision and recall"], ["FL", "Federated Learning"], ["FedAvg", "Federated Averaging"], ["FPR", "False Positive Rate"], ["GPS", "Global Positioning System"], ["GIS", "Geographic Information System"], ["JSON", "JavaScript Object Notation"], ["MLP", "Multilayer Perceptron"], ["OSM", "OpenStreetMap"], ["PostGIS", "PostgreSQL spatial database extension"], ["REST", "Representational State Transfer"], ["SRID", "Spatial Reference Identifier"], ["V1 / V2", "Version 1 / Geo V2 system contracts"], ["km/h", "Kilometres per hour"], ["m", "Metres"]])


def start_main_numbering(doc: Document) -> None:
    return None


def add_paragraphs(doc: Document, paragraphs: list[str]) -> None:
    for text in paragraphs:
        for paragraph_text in text.split("\n\n"):
            p(doc, paragraph_text)


def equation(doc: Document, number: str, expression: str, explanation: str) -> None:
    para = p(doc, expression, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=3, size=12)
    para.paragraph_format.keep_with_next = True
    label = p(doc, f"({number})", align=WD_ALIGN_PARAGRAPH.RIGHT, indent=False, after=4, size=11)
    label.paragraph_format.keep_with_next = True
    p(doc, explanation)


def appendix_heading(doc: Document, title: str) -> None:
    heading(doc, title, level=2)


def appendix_numbered_title(title: str) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if not title.startswith("APPENDIX "):
        return title
    letter = title[9:10]
    if letter in letters:
        return title.replace(f"APPENDIX {letter}", f"APPENDIX {letters.index(letter) + 1}", 1)
    return title


def grouped_sections(
    doc: Document,
    sections: list[tuple[str, str]],
    *,
    figures_after: dict[str, list[tuple[str, str]]] | None = None,
    figure_interpretations: dict[str, str] | None = None,
) -> None:
    """Render independent sections and attach figures to their introducing section."""
    previous_heading: str | None = None
    for section_heading, text in sections:
        if section_heading != previous_heading:
            heading(doc, section_heading)
            previous_heading = section_heading
        p(doc, text)
        for number, caption in (figures_after or {}).get(section_heading, []):
            figure(doc, number, caption)
            interpretation = (figure_interpretations or {}).get(number)
            if interpretation:
                p(doc, interpretation)


def chapter1_expansion(doc: Document) -> None:
    sections = [
        ("1.2 Background", "Traffic intelligence begins with the observation that a road segment is not static. Its average speed, dispersion of speeds, vehicle count, occupancy, flow, and stopped fraction vary with time of day, road type, weather, nearby activity, and the behavior of adjacent segments. A useful system therefore needs a reference for normal operation and a method for comparing the current state with that reference. FedRouteAI models the road segment as the unit of analysis because segment-level state can be joined to road geometry, historical memory, spatial neighbors, and route topology."),
        ("1.2 Background", "GPS telemetry is attractive for this purpose because it can be produced by mobile devices, fleet systems, or controlled vehicle simulators. Raw positions alone are not sufficient for event classification. They must be associated with a canonical segment, aggregated into a consistent time interval, and interpreted with road metadata. The project follows this sequence and keeps the original telemetry, derived segment state, model features, predictions, and demonstration metadata conceptually separate."),
        ("1.2 Background", "The current project contains two related but distinct data paths. The training and evaluation path uses geographically grounded synthetic data with event labels available for dataset construction and evaluation. The runtime path uses label-free telemetry and constructs only the features permitted by the frozen model contract. A controlled demonstration can intentionally change vehicle behavior, but its selected scenario is not passed as a model input and is not automatically treated as a prediction."),
        ("1.3 Motivation", "The project is motivated by the need to observe temporary road-state changes without treating every slow road as the same condition. Historical context, recent behavior, road attributes, and neighboring segments provide the evidence needed to distinguish ordinary variation from an unusual local pattern. Federated training is studied because traffic examples are naturally partitioned by region and raw regional records need not be assembled into one training table."),
        ("1.4 Problem Statement", "The problem is to build and validate an end-to-end system that transforms GPS-derived observations into segment-level traffic state, constructs causal and label-free features, applies a federatedly trained classifier, serves predictions on a live map, and supports directed route inspection. The system must preserve explicit boundaries among training labels, runtime telemetry, model predictions, controlled scenarios, and routing decisions."),
        ("1.5 Need for the Proposed System", "A simple map of GPS points does not tell an operator whether a slow road is experiencing an accident-like disturbance, recurring congestion, or normal low-speed operation. FedRouteAI addresses this need by comparing current traffic aggregates with normal baselines, strictly prior windows, road metadata, and directed-neighbor behavior. Its integrated services also make each transformation inspectable from ingestion to the map."),
        ("1.5 Need for the Proposed System", "A second need is organizational. Mobility records can be distributed across geographic or administrative boundaries. The eight-client training design studies parameter aggregation while retaining regional partitions. This is a practical architecture for the experiment, but it is not presented as proof of differential privacy, secure aggregation, or a formal privacy guarantee."),
        ("1.6 Objectives", "The objectives are to construct the current Geo V2 dataset and exact feature contract, train an eight-client federated MLP, import a canonical OSM/PostGIS network, implement live ingestion and frozen inference, display traffic and prediction state through React-Leaflet, calculate legal directed routes, and validate the complete workflow through focused tests and controlled demonstrations."),
        ("1.7 Scope of the Project", "The scope includes GPS-based road-event classification, regional MLP training, adaptive model aggregation, causal feature engineering, OSM/PostGIS network representation, live and controlled telemetry, dynamic map visualization, and directed shortest-path inspection. It excludes production cloud orchestration, formal privacy protocols, CCTV analytics, learned traffic-aware route costs, and unattended safety-critical operation."),
        ("1.8 Contributions", "The first contribution is an end-to-end engineering pipeline connecting network import, PostGIS persistence, live ingestion, segment aggregation, causal feature construction, frozen inference, prediction persistence, API responses, map layers, and routing. The second is the versioned and ordered history_spatial_strong contract, which reduces the risk of loading a model against incompatible feature semantics."),
        ("1.8 Contributions", "A further contribution is the explicit separation of demonstration behavior from model evidence. A user can select a route and controlled traffic behavior while independent prediction coverage remains visible. The workflow demonstrates orchestration without claiming that selecting Accident, Congestion, or Normal proves that the model emitted the corresponding class."),
        ("1.9 Limitations", "The documented Geo V2 experiment uses geographically grounded synthetic traffic rather than a continuously measured city feed. Class imbalance makes overall accuracy less informative than event-balanced metrics and per-class recall. Routing is directed and distance-based by default, and federated parameter aggregation does not itself provide a formal privacy guarantee."),
        ("1.10 Organization of the Report", "Chapter 2 reviews the related literature, Chapter 3 defines requirements and feasibility, Chapter 4 presents the design, Chapter 5 explains implementation and operation, Chapter 6 records testing and results, Chapter 7 evaluates the evidence, and Chapter 8 concludes the work. Reproduction, artifact, network, testing, and review material is retained in the appendices, followed by the references."),
    ]
    grouped_sections(doc, sections)


def chapter2_expansion(doc: Document) -> None:
    sections = [
        ("2.2 Intelligent Transportation Systems", "Intelligent Transportation Systems combine sensing, communication, computation, and decision support to improve road operations. GPS-derived mobility observations provide broad coverage, while databases and road graphs give those observations a stable geographic meaning. FedRouteAI operates within this field as a segment-level event-classification and route-inspection prototype rather than as a complete traffic-control platform."),
        ("2.3 GPS-Based Traffic Analysis", "GPS-based traffic analysis transforms individual position and speed observations into road-level measurements. The transformation requires segment association, timestamp normalization, aggregation, and treatment of missing observations. FedRouteAI keeps raw observations, segment-level current state, and model-ready features distinct; latitude, longitude, and vehicle identity are not direct MLP inputs."),
        ("2.4 Traffic Anomaly Detection", "Traffic anomaly detection can be formulated as deviation from a baseline, classification into event types, or detection of an out-of-distribution state. Baseline methods are interpretable but depend on a reliable definition of normal, while classifiers are sensitive to imbalance and shift. FedRouteAI combines normal-history context with supervised classification."),
        ("2.5 Traffic Event Classification", "Temporary events have different behavioral signatures. Congestion may reduce speed while increasing vehicle count; an accident-like disturbance may create a sharper local disruption; construction or closure can create persistent effects. The classifier must learn such differences without receiving the event name, and the Geo V2 builder therefore rejects event and scenario tokens."),
        ("2.6 Federated Learning", "Federated learning is relevant when examples are naturally distributed. A regional client can train a local MLP while the server receives parameter updates instead of raw GPS rows. The global model can therefore learn from eight geographic partitions without treating all trajectories as one centrally assembled client dataset [12], [17]."),
        ("2.7 Federated Averaging", "Federated Averaging combines client parameter updates according to local participation. It is compatible with the continuous weight tensors of the MLP, unlike tree structures that require a different federation procedure. FedRouteAI retains a stable parameter interface for round initialization, local updates, aggregation, checkpoint comparison, and artifact promotion [17]."),
        ("2.8 Adaptive Federated Aggregation", "Traffic regions can differ in data quality, event prevalence, recency, and relevance. Adaptive aggregation extends sample-count weighting with bounded quality and relevance factors. The current workflow records these factors but does not claim that they solve non-IID learning in general [16], [26]."),
        ("2.9 Neural Networks for Traffic Classification", "The current runtime model is a PyTorch multilayer perceptron with a 23 -> 64 -> 32 -> 8 structure. Linear layers, batch normalization, ReLU, dropout during training, and LogSoftmax transform the fixed ordered feature vector into eight class scores. This tabular architecture is compatible with federated parameter averaging [9], [18]."),
        ("2.10 Historical Traffic Modeling", "Historical traffic memory provides a reference rather than a single stored average. Baseline speed, speed variation, and vehicle count support current-to-normal ratios, while shifted prior means, trends, and persistence describe recent behavior. Strictly earlier slots prevent the current observation from leaking into its own explanatory history."),
        ("2.11 Spatial Traffic Modeling", "Road conditions are spatially related because disruption on one segment can differ from or propagate toward connected roads. FedRouteAI uses persisted directed topology rather than arbitrary geometric proximity. The promoted feature contract retains a directed-neighbor speed contrast, giving the model a compact representation of local spatial disagreement."),
        ("2.12 OpenStreetMap and Road Networks", "OpenStreetMap contributes road geometry and descriptive tags. The cached source is normalized into canonical segments, road types, lane information, maximum speed, and direction metadata. This network is the spatial frame for map rendering and routing, not the labeled ML dataset [30]."),
        ("2.13 PostGIS and Spatial Data", "PostGIS stores geometry in PostgreSQL and supports spatial indexing and queries. The API serves the same canonical identity used by ingestion, prediction, and routing, avoiding a separate unversioned road drawing in the browser [31]."),
        ("2.14 Map Matching", "Map matching associates a noisy GPS position with a road segment. The preserved V1 path uses geometric projection and trajectory continuity, while trusted Geo V2 simulator observations supply a canonical ID that is still validated. Association is therefore an upstream preprocessing responsibility, not a classification shortcut."),
        ("2.15 Shortest Path Algorithms", "The route service models legal movement as directed transitions between canonical segments. It snaps endpoints, returns an ordered segment sequence and geometry, and reports distance and estimated duration. The dependable default is directed distance-weighted Dijkstra; prediction inspection and explicit exclusions remain separate [5]."),
        ("2.16 Research Gap", "Many studies address traffic prediction, anomaly detection, federated learning, spatial databases, or routing separately. The engineering gap addressed here is their integration under explicit data boundaries, allowing one road state to be traced from telemetry through causal features and independent prediction to the map."),
        ("2.17 FedRouteAI Positioning", "FedRouteAI is positioned as a reproducible college-scale integration of an eight-client federated MLP, a versioned 23-feature contract, an OSM/PostGIS directed network, live ingestion, a dynamic map, and controlled route-bound behavior. Its contribution is the inspectable complete path, not a claim of universal traffic accuracy."),
        ("2.18 Summary", "The reviewed work supports the selection of segment-level GPS aggregation, causal history, directed spatial context, federated MLP training, spatial persistence, and shortest-path routing. The following chapter converts these concepts into explicit functional, data, model, network, and operational requirements."),
    ]
    grouped_sections(doc, sections)
    equation(doc, "2.1", r"w_global = sum_i (n_i / sum_j n_j) w_i", "In the basic FedAvg formulation, n_i is the number of local training examples and w_i is the parameter vector returned by client i [1]. The adaptive workflow used by this project adds bounded quality and relevance factors around this sample-weighted starting point.")
    table(doc, "Table 2.1: Related Approaches and FedRouteAI Position", ["Area", "Typical focus", "FedRouteAI implementation"], [["Traffic analysis", "Speed, flow, and occupancy patterns", "Current segment aggregates with historical comparison"], ["Anomaly detection", "Deviation or event classification", "Frozen MLP with normal-history context"], ["Federated learning", "Distributed local training", "Eight regional MLP clients and parameter aggregation"], ["Spatial modeling", "Road geometry and neighboring roads", "OSM/PostGIS canonical directed topology"], ["Routing", "Shortest or alternative path", "Directed distance-based route inspection"], ["Visualization", "Map and operational dashboard", "React and Leaflet live traffic map"]])


def chapter3_expansion(doc: Document) -> None:
    sections = [
        ("3.5 User Roles", "The traffic operator inspects current segment state, model predictions, route information, and freshness. Regional clients prepare local examples and model updates. The model administrator manages artifact compatibility, while the evaluator needs reproducible commands, evidence, and a clear distinction between measured and synthetic values."),
        ("3.6 Data Requirements", "Training data must contain segment and region identity, timestamp, traffic aggregates, road metadata, historical baselines, and targets used only for supervised training or evaluation. Runtime construction must operate without a target column. The manifest counts describe generated research data and not the live database."),
        ("3.7 Model Requirements", "The model must accept exactly the ordered feature schema, output eight class probabilities, and fail closed when feature, network, scaler, or tensor metadata is incompatible. A null output caused by insufficient evidence remains distinct from a confident Normal result."),
        ("3.8 Database Requirements", "The database supports PostGIS geometry, historical memory, ingestion receipts, append-only observations, current segment projections, predictions, and network transitions. Network source and version prevent unrelated geometry and artifacts from being combined silently."),
        ("3.9 Road-Network Requirements", "The network contains canonical segment IDs, geometry, direction metadata, legal transitions, road type, lane count, and maximum speed. Route-bound demonstrations require a valid ordered route that follows transitions and meets the minimum distance."),
        ("3.10 Software Requirements", "The software stack requires Python 3.12+, FastAPI, SQLAlchemy, Alembic, PyTorch, and Flower-compatible components for the backend and ML workflow. The frontend requires Node.js, React, Vite, React Query, and Leaflet. PostgreSQL with PostGIS provides spatial persistence."),
        ("3.11 Hardware Requirements", "CPU inference is supported for the frozen artifact, while model training benefits from a GPU. Local operation requires sufficient memory for PostgreSQL/PostGIS, the backend, frontend development server, model artifacts, and generated traffic data."),
        ("3.12 Operational Feasibility", "A local operator can start PostgreSQL/PostGIS, apply migrations, import the Geo V2 network, start the backend and frontend, and use the map without manually constructing model input. This supports bounded academic operation, not unattended production deployment."),
        ("3.13 Technical Feasibility", "FastAPI, SQLAlchemy, PostGIS, PyTorch, Flower-compatible components, graph services, React, and Leaflet support the major requirements. Pure feature and routing functions remain testable without a live database where possible."),
        ("3.14 Privacy and Security Considerations", "Mobility records can reveal movement patterns, so vehicle identity is excluded from model features and regional learning remains conceptually separated. Scenario controls are not prediction labels. Differential privacy and secure aggregation are not implemented and are not claimed."),
        ("3.15 System Constraints", "Synthetic-data realism, class imbalance, the fixed artifact, exact 120-second history cadence, local-process execution, finite browser rendering, and distance-based default routing define the conditions under which results are meaningful."),
    ]
    grouped_sections(doc, sections)
    table(doc, "Table 3.4: Requirement Traceability", ["Requirement group", "Primary implementation evidence"], [["Data", "Geo V2 manifest, feature builder, and dataset partitions"], ["Model", "Feature schema, model store, frozen artifact metadata"], ["Network", "Cached OSM JSON, network normalizer, PostGIS import"], ["Runtime", "Live ingestion, snapshot, prediction persistence"], ["User interface", "Traffic Map tests, route planner, scenario controls"], ["Validation", "Backend suite, frontend suite, build, compile, and smoke evidence"]])


def chapter4_expansion(doc: Document) -> None:
    sections = [
        ("4.2 Overall System Architecture", "The overall design is organized around explicit transformations and immutable identities. The architecture connects offline regional training, the promoted frozen artifact, live telemetry ingestion, PostGIS persistence, causal feature construction, model inference, APIs, map visualization, and a separate routing branch. Network, run, feature, and model identities allow incompatible combinations to fail clearly."),
        ("4.3 Federated Learning Architecture", "Eight regional clients train local copies of the 23 -> 64 -> 32 -> 8 MLP and return parameters plus training metadata. The server aggregates participating updates and distributes the next global state. Raw regional examples remain with the logical clients during this experiment; the current implementation does not add secure aggregation or differential privacy."),
        ("4.4 Regional Client Architecture", "A regional client loads its partition, aligns the exact feature order, initializes from global parameters, performs local gradient updates, evaluates local behavior, and returns tensors and metrics. Replay and class-imbalance handling belong to local training, while checkpoint promotion remains a server-side experimental decision."),
        ("4.5 End-to-End Data Flow", "The data flow begins with either labeled Geo V2 examples for training or label-free observations for runtime. Runtime observations become segment aggregates, join normal memory and shifted history, acquire directed-neighbor context, pass through the frozen scaler and MLP, and become persisted predictions. Routing consumes the canonical directed graph through a separate distance-based path."),
        ("4.6 Geo V2 Feature Construction", "Geo V2 combines six current traffic values, cyclical time, three road attributes, three normal baselines, three deviation ratios, shifted prior means, trends, low-speed persistence, and one directed-neighbor speed delta. The promoted history_spatial_strong variant contains exactly 23 ordered values, and forbidden label or identity tokens are rejected."),
        ("4.7 Historical Traffic Memory", "Historical memory stores normal baseline speed, speed variation, and vehicle count. The feature builder requires an exact 120-second cadence, shifts earlier windows before rolling operations, and computes trends and persistence from prior state only. Normal prehistory handles initial missing slots without copying a future or current target value."),
        ("4.8 OSM/PostGIS Road-Network Architecture", "The cached OSM source is normalized into versioned canonical segments and legal directed transitions. PostGIS stores LineString geometry and road metadata so ingestion, feature construction, map rendering, and routing use the same segment identity. The active network contains 2,968 canonical segments and 11,259 transitions."),
        ("4.9 Directed Road Network and Transitions", "The road graph represents each canonical segment and the legal movement relationships between segments. Direction is preserved when constructing neighbors and routes, preventing visually adjacent but illegal movements from being treated as valid. The same topology supports spatial feature context and route-bound simulation."),
        ("4.10 Backend Service Architecture", "FastAPI endpoints parse requests and call services; services implement ingestion, feature, inference, simulation, and routing workflows; repositories own database access; and SQLAlchemy models represent persisted records. Pydantic API schemas remain separate from database models, preserving the one-directional project layering."),
        ("4.11 Frontend Architecture", "The React application uses typed API clients and React Query for network and live state. Leaflet renders separate geometry, telemetry, prediction, event, vehicle, and route layers. The browser does not reproduce backend inference or shortest-path logic, and scoped query identities prevent stale demonstration data from appearing as the active run."),
        ("4.12 Directed Shortest-Path Routing", "Routing snaps origin and destination coordinates to the canonical network and searches legal directed transitions using distance as the default cost. The response contains ordered segment IDs, actual geometry, distance, estimated duration, and prediction coverage where available. Predictions do not silently modify the default route cost."),
        ("4.13 Database Design", "The database separates canonical network rows, directed transitions, append-only GPS observations, ingestion receipts, current segment projections, historical memory, and prediction persistence. Source, run, network, segment, and timestamp fields preserve provenance across these records and support scoped live-map retrieval."),
        ("4.14 API Design", "The API exposes health, network, live ingestion, snapshot, prediction, routing, and demonstration operations through validated schemas. Endpoints remain thin, while services own route validity, run lifecycle, feature availability, artifact compatibility, and other business rules."),
        ("4.15 Label-Free Inference Design", "Runtime inference receives the exact 23 traffic and context values but not event labels, scenario names, event IDs, vehicle IDs, or ground-truth severity. The frozen scaler standardizes the ordered vector, the MLP produces probabilities, and invalid metadata or missing evidence results in an unavailable state rather than a fabricated class."),
        ("4.16 Training and Runtime Data Separation", "Training examples contain targets for supervised optimization and evaluation. Runtime telemetry, controlled demonstration metadata, the OSM network, and persisted predictions remain distinct stores joined by explicit identities. A selected scenario can change traffic behavior, but it is neither a runtime feature nor an automatic model result."),
        ("4.17 Summary", "The design connects federated training and label-free runtime inference through a frozen, versioned artifact. Historical and spatial context is grounded in one canonical directed network, backend and frontend responsibilities remain separated, and routing is an independent distance-based service. Chapter 5 explains how these designs are implemented."),
    ]
    grouped_sections(
        doc,
        sections,
        figures_after={
            "4.2 Overall System Architecture": [("4.1", "Overall System Architecture of FedRouteAI")],
            "4.3 Federated Learning Architecture": [("4.2", "Federated Learning Architecture")],
            "4.4 Regional Client Architecture": [("4.3", "Regional Client Architecture")],
            "4.5 End-to-End Data Flow": [("4.4", "End-to-End Data Pipeline")],
            "4.6 Geo V2 Feature Construction": [("4.5", "Geo V2 Feature Pipeline")],
            "4.7 Historical Traffic Memory": [("4.6", "Historical Traffic Memory")],
            "4.8 OSM/PostGIS Road-Network Architecture": [("4.7", "OSM/PostGIS Road-Network Architecture")],
            "4.9 Directed Road Network and Transitions": [("4.8", "Directed Road Network and Transitions")],
            "4.10 Backend Service Architecture": [("4.9", "Backend Service Architecture")],
            "4.11 Frontend Architecture": [("4.10", "Frontend Architecture")],
            "4.12 Directed Shortest-Path Routing": [("4.11", "Directed Shortest-Path Routing")],
        },
    )
    equation(doc, "4.1", r"r_speed = avg_speed_kmph / max(baseline_speed_kmph, epsilon)", "The speed-to-baseline ratio expresses current movement relative to normal history. Protected denominators prevent an absent or near-zero baseline from creating an undefined model input [4].")
    table(doc, "Table 4.3: Dataset and Runtime Data Separation", ["Data source", "Purpose", "Labels available?"], [["ML training/evaluation data", "Train, validate, and test the classifier", "Yes for target construction/evaluation"], ["OSM/PostGIS network", "Geometry, road metadata, topology, and routing", "No"], ["Live GPS telemetry", "Current runtime observations", "No scenario labels in inference"], ["Controlled demonstration telemetry", "Repeatable route-bound behavior", "Scenario truth kept outside features"], ["Prediction persistence", "Serve independent model outputs", "Predicted class and confidence"]])


def chapter5_expansion(doc: Document) -> None:
    sections = [
        ("5.2 Development Environment", "The project uses Python 3.12 or the configured Python environment for the FastAPI, data, and ML services, PostgreSQL with PostGIS for persistence, and Node.js with React, Vite, React Query, and Leaflet for the frontend. PyTorch provides the MLP runtime and training components. Local development keeps database, backend, frontend, and optional replay processes independently observable."),
        ("5.3 Project Structure", "The repository separates API endpoints, services, repositories, schemas, models, ML features, training, frontend pages, and Geo V2 scripts. This structure follows the project's one-directional layering rule. The important implementation boundary is which layer owns each transformation."),
        ("5.4 Dataset Preparation", "The Geo V2 dataset generator creates traffic states over the canonical network and writes a manifest describing the run. The recorded manifest identifies a five-hour period beginning at 2026-07-07 06:00:00, a 600-second tick interval, 1,000 vehicles, 30,000 telemetry rows, three scenario rows, 16,338 feature windows, and network version beeramguda-osm-20260506. The scenario table is separate from telemetry features and is not used as an inference input."),
        ("5.5 Regional Data Partitioning", "The regional partition is based on REGION_01 through REGION_08. Different regions can have different traffic distributions, event frequencies, and history quality, so the aggregation process must handle non-identical local data rather than assuming identical samples."),
        ("5.6 Road-Segment Association", "For map-matched V1 ingestion, candidate segments are selected spatially and a geometric matcher uses projection and trajectory continuity. For trusted Geo V2 observations, the canonical segment ID is supplied by the controlled network path and validated against the persisted network. Segment identity bridges telemetry, features, predictions, maps, and routes."),
        ("5.7 Traffic Aggregation", "The service aggregates observations by segment and tick into average speed, speed standard deviation, vehicle count, occupancy, flow rate, and stopped fraction. These are current-state fields rather than labels, and identity-level information is excluded from the model vector."),
        ("5.8 Historical Traffic Memory Implementation", "Historical memory is computed from normal prehistory and stores baseline speed, variation, and vehicle count. Current-to-baseline ratios and trends are computed later, keeping a database baseline row distinct from a prediction or scenario truth."),
        ("5.9 Geo V2 Feature Construction", "The feature builder verifies required columns, exact cadence, baseline coverage, and forbidden target-related tokens. It derives temporal encodings, baseline ratios, shifted prior means, trends, persistence, and directed-neighbor context in deterministic order."),
        ("5.10 Exact 23-Feature Contract", "The promoted history_spatial_strong variant contains 23 ordered values: current traffic, cyclical time, road metadata, normal baselines, ratios, prior means, trends, low-speed persistence, and neighbor_speed_delta. The model store validates this contract before inference."),
        ("5.11 Model Implementation", "The GeoV2MLP uses linear layers, normalization, ReLU, dropout, and a final eight-class classifier. Its runtime definition is separate from training orchestration so the application can load the frozen artifact without retraining."),
        ("5.12 Local Client Training", "A client aligns its regional examples, starts from global parameters, performs local optimization, evaluates its update, and returns tensors with sample metadata. It does not send raw GPS rows as the model update."),
        ("5.13 Federated Model Aggregation", "FedAvg combines MLP weights and biases from participating clients, while the current robust workflow records adaptive quality and relevance factors and bounded projection. The aggregation configuration is retained in artifact metadata."),
        ("5.14 Global Model Selection", "Validation evidence selected round 45 from a maximum of 50 rounds before one-time test access. Training history, client metrics, validation selection, and test receipt files support review of this decision."),
        ("5.15 Frozen Model Deployment", "The model store validates feature version, ordered features, network version, model identity, scaler metadata, and tensor compatibility. The application loads the selected artifact in evaluation mode and does not change it when a scenario starts."),
        ("5.16 Label-Free Runtime Inference", "At runtime the model receives the 23 feature values and no event label, scenario name, event ID, vehicle ID, or ground-truth severity. Missing evidence remains unavailable rather than being converted into an arbitrary class."),
        ("5.17 Live GPS Ingestion", "The service accepts trusted observations with source, run, batch, and observation identity, records receipts, persists append-only history, updates current state, and triggers the prediction path. Retried batches are checked for identity and payload consistency."),
        ("5.18 Prediction Persistence", "Prediction rows retain segment, timestamp, model identity, feature version, class, confidence, and related deviations. The live snapshot serves these values alongside current traffic state so the browser does not recompute inference."),
        ("5.19 Dynamic Traffic Map", "The React map requests network geometry and live snapshots through typed clients and presents freshness, network identity, vehicles, predictions, routes, and selected-road details. Independent layers prevent telemetry and prediction styling from being confused."),
        ("5.20 Moving Vehicle Visualization", "The backend remains authoritative for positions and counts. The frontend interpolates received positions for continuity without writing interpolated frames to telemetry, and a rendering cap limits browser marker work."),
        ("5.21 Route Calculation", "The route planner sends origin, destination, network identity, and optional scoped run identity. The backend snaps endpoints, searches directed transitions, and returns geometry, ordered segments, duration, distance, and prediction coverage."),
        ("5.22 Alternate Route Inspection", "The default route uses distance. When the user explicitly requests an alternative, selected segment IDs are passed as exclusions and a new directed route is calculated. The model does not autonomously change the default route cost."),
        ("5.23 Route-Bound Demonstration", "The service validates the ordered route, unknown IDs, transitions, minimum distance, and scenario enum. Controlled vehicles remain within the corridor, and scenario metadata is scrubbed before model input."),
        ("5.24 Normal Traffic Demonstration", "Normal is a controlled baseline behavior along the selected route. It is a demonstration control and not a claim that the model has established a ground-truth Normal label."),
        ("5.25 Congestion Demonstration", "Congestion is a controlled congestion-like route behavior. Its telemetry enters the ordinary aggregation and inference path, but the selected scenario is not itself a model input or proof of classification."),
        ("5.26 Accident Demonstration", "Accident is a controlled accident-like route disturbance. The correct interpretation is traffic behavior only, not ground truth; returned predictions remain independent and may be normal, abnormal, or unavailable."),
        ("5.27 API Integration", "FastAPI provides health, network, ingestion, live-map, prediction, route, and demonstration interfaces. Pydantic schemas enforce field types, enum values, bounds, and route prerequisites while services own business rules."),
        ("5.28 Frontend-Backend Integration", "React Query, typed API clients, scoped snapshots, and Leaflet connect the browser to backend-owned state. The UI preserves route and run identity, shows freshness, and distinguishes scenario controls from model outputs."),
        ("5.29 Implementation Summary", "The implementation joins dataset preparation, regional learning, artifact management, label-free inference, ingestion, persistence, visualization, routing, and controlled operation without collapsing their data responsibilities."),
    ]
    grouped_sections(
        doc,
        sections,
        figures_after={
            "5.17 Live GPS Ingestion": [("5.1", "Live GPS Ingestion Pipeline")],
        },
    )
    heading(doc, "5.30 Output Screens")
    p(doc, "Verified application screenshots are not available in the current workspace, so this section reserves only the canonical application-output positions. When captured from the running project, each screenshot must be explained as an application output and must preserve the distinction between controlled scenario behavior and model prediction.")
    for number, caption in [("5.2", "Dynamic Traffic Map"), ("5.3", "Moving Vehicle Visualization"), ("5.4", "Route-Bound Demonstration Flow"), ("5.5", "Normal Traffic Demonstration"), ("5.6", "Congestion Demonstration"), ("5.7", "Accident Demonstration")]:
        figure(doc, number, caption)
    table(doc, "Table 5.3: Model Configuration", ["Property", "Verified value"], [["Runtime model", "GeoV2MLP"], ["Output classes", "8"], ["Input feature count", "23"], ["Feature version", "geo-v2-history_spatial_strong-23-v2"], ["Training rounds", "50 maximum; checkpoint round 45"], ["Local epochs", "2"], ["Dropout", "0.2 in runtime architecture"], ["Inference mode", "Label-free feature input"]])
    table(doc, "Table 5.4: Demonstration Controls", ["Control", "Behavior"], [["Normal", "Baseline route-bound traffic behavior"], ["Congestion", "Controlled congestion-like route behavior"], ["Accident", "Controlled accident-like route disturbance"], ["Minimum route", "Approximately 1.5 km"], ["Route binding", "Ordered directed segment IDs supplied by route calculation"], ["Truth handling", "Scenario metadata excluded from model features"]])


def chapter6_expansion(doc: Document) -> None:
    sections = [
        ("6.4 Functional Testing", "Pure tests cover map matching decisions, event signature behavior, historical aggregation, adaptive weighting, graph reasoning, feature construction, route logic, API behavior, ingestion, prediction, and controlled demonstrations. These tests protect transformations without requiring every test to start a live database."),
        ("6.5 Data Validation Testing", "The backend suite exercises accepted observations, health behavior, ingestion receipts, live snapshots, network metadata, and controlled demonstration state. The current verified suite contains 117 passing tests; this is repository evidence, not proof that every possible condition has been exhausted."),
        ("6.6 Feature Contract Testing", "Feature tests verify exact input columns, ordered feature version, cadence, shifted history, normal prehistory fallback, directed-neighbor construction, and forbidden target-token rejection. A numerically valid output is not sufficient when feature semantics are wrong."),
        ("6.7 Model Artifact Validation", "Artifact checks load the selected MLP, verify the 23-feature schema, confirm network and model metadata, inspect scaler ordering, and reject incompatible files. The report states recorded metrics rather than retraining during documentation generation."),
        ("6.8 Federated Learning Validation", "Federated validation compares regional participation, round history, client metrics, aggregation weights, and validation selection. The chosen run records eight clients, a maximum of 50 rounds, two local epochs, and a selected checkpoint at round 45. The test set is accessed only after selection in the recorded experiment, as stated by the artifact report."),
        ("6.9 Inference Testing", "Inference tests verify artifact compatibility, feature ordering, label-free input, persisted class and confidence, unavailable states, and scoped prediction retrieval. They do not treat a controlled scenario name as a prediction label."),
        ("6.10 API Testing", "Schema tests verify required fields, enum restrictions, route minimum distance, prediction metadata, telemetry scrubbing, and response shape. Route-bound creation must receive ordered segment IDs and distance from the frontend result."),
        ("6.11 Database Testing", "Database-facing tests verify current segment state, prediction rows, network metadata, receipts, historical relationships, and demonstration lifecycle using the configured test approach and isolated fixtures where appropriate."),
        ("6.12 Routing Testing", "Routing tests verify legal directed topology, ordered segment IDs, distance, geometry, and explicit exclusions separately from default distance-based routing."),
        ("6.13 Frontend Testing", "The frontend suite checks loading, live state, polling, stale/offline status, layers, region and road selection, vehicles, route calculation, route clearing, prediction metadata, and demonstration controls. The focused Traffic Map suite contains 17 passing tests and the production build passes."),
        ("6.13 Frontend Testing", "Map and vehicle tests verify that hiding predictions does not hide telemetry, route geometry remains independent from scenario markers, interpolated markers do not create backend observations, and the browser marker cap does not change the authoritative count."),
        ("6.14 Performance Testing", "The recorded artifact report measures warmed single-row CPU inference at approximately 0.414 ms across 1,000 calls. This is a model-call measurement, not end-to-end ingestion, database, browser, memory, or production throughput evidence."),
    ]
    grouped_sections(
        doc,
        sections,
        figures_after={},
    )
    table(doc, "Table 6.3: Test Categories", ["Category", "Scope", "Result / status"], [["Unit and service", "Pure functions and service rules", "Covered by backend suite"], ["API contracts", "Pydantic request/response behavior", "Covered by focused tests"], ["Geo V2", "Feature ordering, cadence, history, neighbors", "Covered by model and feature tests"], ["Artifact", "Model, scaler, metadata, compatibility", "Passed for frozen artifact"], ["Routing", "Directed path, exclusions, route metadata", "Covered by routing tests"], ["Live ingestion", "Batch, persistence, prediction snapshot", "Covered by integration tests"], ["Frontend", "Map, route, demo, live controls", "17 focused tests passed"], ["Build", "Compile, import, production bundle", "Passed"]])
    equation(doc, "6.1", r"F1 = 2 * precision * recall / (precision + recall)", "Macro F1 averages class-wise F1 values and is therefore more informative than accuracy when Normal dominates the test distribution [17].")


def chapter7_expansion(doc: Document) -> None:
    sections = [
        ("7.11 Deployment Evaluation", "The local deployment consists of PostgreSQL/PostGIS, FastAPI, Vite, and optional simulator or replay processes. Migration and Geo V2 network import happen before database-backed map and routing operation. Production orchestration and queue-backed ingestion remain outside the measured scope."),
        ("7.11 Deployment Evaluation", "Backend and frontend configuration select database connection, artifact path, network identity, cadence, API base URL, and optional ingestion behavior through configuration. Secrets are kept in local environment settings and are not reproduced in the report."),
        ("7.13 Security and Privacy Discussion", "The live ingestion workflow can require a configured API key and validates batch identity. Demonstration endpoints apply bounded lifecycle and scoped source/run rules. The project does not claim complete authentication for every endpoint, differential privacy, secure aggregation, or a formal privacy budget."),
        ("7.14 Limitations", "The model store validates feature, network, scaler, artifact, and tensor metadata and fails closed when they do not agree. Training/evaluation records, OSM/PostGIS data, live telemetry, controlled telemetry, and prediction persistence remain distinct stores joined by explicit identities."),
        ("7.12 Performance Discussion", "Warmed CPU single-row inference averages approximately 0.414 ms across 1,000 calls in the artifact report. The complete path includes database access, feature construction, batch processing, and network communication, which are not represented by that isolated measurement."),
        ("7.12 Performance Discussion", "A complete memory profile for backend, database, model, and browser at the 1,000-vehicle scale was not measured. Bounded run registries, expiry cleanup, batched inference, and a frontend rendering cap reduce avoidable growth but are not measured memory guarantees."),
        ("7.8 Live Map Evaluation", "The map can contain thousands of road segments and large vehicle populations. Static geometry is loaded separately, marker rendering is capped, and the backend active count remains authoritative even when fewer markers are displayed."),
        ("7.11 Deployment Evaluation", "The federated topology can add regional clients and the repository/service layering can move database work behind a queue. Horizontal scaling, broker-backed ingestion, distributed caching, and cloud deployment were not implemented or measured."),
        ("7.14 Limitations", "The project remains a research and academic prototype with minority-class limitations, synthetic data, distance-based default routing, absent formal privacy mechanisms, and unmeasured production capacity. These facts define the correct operating envelope."),
    ]
    grouped_sections(doc, sections)


def appendices_expansion(doc: Document) -> None:
    appendix_heading(doc, "APPENDIX 4: Model Configuration")
    p(doc, "The promoted artifact is identified as fedrouteai-geo-v2-robust-robust-v2-hs1-prior2-unweighted-bw3-22-50r2e-seed42-r45. Its feature version is geo-v2-history_spatial_strong-23-v2, its network version is beeramguda-osm-20260506, and its selected checkpoint is round 45. The model has eight output classes and uses the ordered 23-feature schema listed in Chapter 4. These values are reproduced from the frozen artifact metadata and are not regenerated by this documentation task.")
    appendix_heading(doc, "APPENDIX 5: Database and Network Statistics")
    table(doc, "Table A5.1: Database and Network Evidence", ["Evidence item", "Value / interpretation"], [["Geo V2 network", "2,968 canonical segments"], ["Directed topology", "11,259 persisted transitions"], ["Regions", "8 regional IDs"], ["Network version", "beeramguda-osm-20260506"], ["Network source", "osm_geo_v2"], ["Geometry", "PostGIS LineString representation"], ["Route identity", "Ordered directed segment IDs"]])
    appendix_heading(doc, "APPENDIX 6: Testing Evidence")
    p(doc, "The current evidence register includes 117 passing backend tests, 17 passing Traffic Map frontend tests, a successful frontend production build, successful Python compilation, successful FastAPI import, model artifact validation, and normalized network counts. A future submitted version may insert screenshots or terminal excerpts into the reserved figure spaces after they are reviewed for sensitive configuration values.")
    appendix_heading(doc, "APPENDIX 7: Sample Telemetry Semantics")
    p(doc, "A runtime observation represents traffic state associated with a canonical segment and timestamp. It may contain speed, vehicle count, occupancy, flow, stopped fraction, and road metadata after aggregation. The model feature vector does not include latitude, longitude, vehicle identity, device identity, scenario name, event ID, or ground-truth label. Controlled telemetry may be generated to change the traffic pattern, but it remains an observation source rather than a label source.")
    appendix_heading(doc, "APPENDIX 8: Prediction Response Semantics")
    p(doc, "A prediction response is associated with a segment, timestamp, model version, feature version, predicted class, confidence, and current deviation information where available. A null or unavailable output means that the runtime did not have a valid prediction for that state; it is not equivalent to a confident normal classification. The Traffic Map displays this distinction through coverage and prediction status.")
    appendix_heading(doc, "APPENDIX 9: Routing Response Semantics")
    p(doc, "A shortest-route response contains network identity, snapped endpoints, distance, estimated duration, segment count, ordered segment IDs, and route geometry. Prediction fields, when available, summarize only the route segments covered by current persisted predictions. A route can therefore be valid even when prediction coverage is incomplete.")
    appendix_heading(doc, "APPENDIX 10: Project Screenshot Register")
    p(doc, "The screenshot register is intentionally left as an insertion plan. Future black-and-white figures may show the title and map, the dynamic Traffic Map, route selection, live status, moving vehicles, prediction inspection, model evidence, and controlled Normal, Congestion, and Accident behavior. Scenario labels must remain visibly distinct from model prediction labels in every inserted screenshot.")
    evidence_pages = [
        ("APPENDIX K: Geo V2 Feature Data Dictionary", "The Geo V2 contract begins with current traffic state: avg_speed_kmph, speed_std_kmph, vehicle_count, occupancy, flow_rate_vph, and stopped_fraction. These values describe the focal segment at the current two-minute tick. hour_sin and hour_cos encode the time of day without a midnight discontinuity. road_type_code, lane_count, and max_speed_kmph provide structural context from the canonical network rather than from the event label.", "The remaining values describe normal reference and temporal context. baseline_speed_kmph, baseline_speed_std_kmph, and baseline_vehicle_count are normal-history values. speed_to_baseline, count_to_baseline, and std_to_baseline express current deviation. prior_speed_mean_3, prior_count_mean_3, speed_trend, count_trend, and low_speed_persistence_3 are shifted historical features. neighbor_speed_delta is derived from directed same-time neighbor evidence. No label, scenario, vehicle identity, or device identity appears in this dictionary."),
        ("APPENDIX L: Feature Construction Review", "A feature review starts by confirming that every segment has a canonical identity and a timestamp at the expected cadence. The builder then joins current state to normal memory and checks the required columns. History is shifted before rolling operations, which means the current value cannot be used to manufacture its own prior mean or persistence signal. This review is particularly important when a batch is incomplete or a segment has just entered the live stream.", "The final review compares the emitted names and ordering with feature_schema.json. It also checks that network version and feature version agree with the selected artifact. If a required baseline or prior state is unavailable, the service reports insufficient evidence or uses the documented normal prehistory behavior. It does not silently substitute an event label or scenario control."),
        ("APPENDIX M: API Contract Review", "The health endpoint confirms service availability. Network endpoints return canonical geometry and network metadata. Live ingestion accepts trusted observations with source, run, batch, and observation identity. The live snapshot returns current segment state, prediction state, vehicle information, freshness, and scope metadata. These responses are designed for inspection and not as a replacement for the database schema.", "Route requests contain origin and destination coordinates and may include scoped live-run identity. Route responses return snapped endpoints, distance, estimated duration, ordered segment IDs, geometry, and prediction coverage. Demonstration creation requires a valid route, accepts only Normal, Congestion, or Accident, and returns a bounded run identity. Invalid input is rejected before simulation or inference begins."),
        ("APPENDIX N: Database Lifecycle Review", "The database lifecycle begins with migrations and network import. The OSM source is normalized into a versioned canonical network. Live batches are received with identity and checked for retries. Accepted observations are stored as history and aggregated into a current segment projection. Prediction rows are stored separately, allowing the map to distinguish current traffic from model output.", "A controlled run has its own source and run scope. Reset or expiry removes its temporary state without changing the persisted route definition or the imported canonical network. This lifecycle is the reason a demonstration can be repeated without making the database appear to contain measured city traffic. It also creates a clear location for a future queue-backed ingestion worker."),
        ("APPENDIX O: Federated Training Review", "A regional client owns the local examples for one of eight regions and trains from the current global parameters. The server receives parameter arrays and local metadata, then applies the configured FedAvg-family aggregation. The artifact record preserves the selected round, aggregation settings, seed, feature version, and network version. This information makes a model checkpoint reviewable without exporting the local raw trajectories.", "The federated design does not automatically provide formal privacy. Gradients or parameter updates can have their own disclosure risks, and the current prototype does not implement differential privacy or secure aggregation. The report therefore describes the architecture as federated parameter aggregation and records privacy mechanisms as future work rather than as a completed guarantee."),
        ("APPENDIX P: Model Metric Interpretation", "The frozen artifact records validation macro F1 of 0.3042, test accuracy of 0.9952, test macro F1 of 0.3200, event-balanced macro F1 of 0.4459, anomaly recall of 0.3444, anomaly precision of 0.2093, and normal false-positive rate of 0.0031. These metrics must be read together. Accuracy is strongly affected by the dominant normal class, while event-balanced macro F1 exposes minority-class behavior more clearly.", "Diversion recall is zero and construction recall is low in the recorded results. Anomaly precision is also limited, so a displayed abnormal prediction should be treated as decision support requiring inspection. The project does not approve the frozen model for unattended safety-critical operation. Future evaluation should add measured data, calibration, confidence intervals, and event-specific error analysis."),
        ("APPENDIX Q: Routing Validation Review", "A route is valid only when its ordered segment IDs exist in the active network and each consecutive pair is an allowed directed transition. The route planner snaps coordinates to the network and returns geometry derived from those segments. The route-bound demonstration receives this ordered sequence rather than inventing a corridor from two endpoints. A minimum distance requirement prevents trivial demonstrations that do not exercise a meaningful road path.", "The default route cost is distance-based. Prediction coverage is a report about how many route segments have current model state; it is not a hidden cost adjustment. An explicit alternative route may exclude selected segment IDs, but this is a separate user-requested behavior. The system therefore distinguishes route calculation, route inspection, and controlled traffic demonstration in both service logic and map presentation."),
        ("APPENDIX R: Demonstration Review", "The Normal, Congestion, and Accident controls define controlled traffic behavior along the selected route. The simulator uses the route topology and persistent vehicle identities to produce repeatable observations. The resulting telemetry goes through the same aggregation and inference path as other trusted observations. The scenario name is retained as demonstration metadata and is excluded from the model feature vector.", "The correct interpretation of a scenario run is: Traffic behavior only. Not ground truth. The model may produce a prediction, a normal state, or no prediction when evidence is insufficient. The frontend reports prediction coverage and abnormal counts from returned prediction state. It does not convert the selected control into an event badge or claim that a real accident was detected."),
        ("APPENDIX S: Frontend Review Checklist", "The Traffic Map review starts with loading network geometry and confirming the displayed network source and version. Live status indicates whether the snapshot is fresh, stale, paused, or offline. Telemetry, predictions, events, vehicles, and route overlays are separate layers. A selected road shows its current state and prediction metadata without requiring the browser to reproduce the backend model computation.", "The route workflow requires an origin and destination, calculates a route, displays ordered route information, and retains the route after demonstration reset. Demo controls are unavailable until route prerequisites are satisfied. Vehicle markers are rendered within a browser cap while the backend active count remains authoritative. These checks keep visual performance behavior separate from traffic-data semantics."),
        ("APPENDIX T: Test Matrix", "Pure service tests cover historical memory, event matching, graph reasoning, adaptive aggregation, feature construction, and routing. Backend integration tests cover ingestion, map matching, prediction persistence, live snapshots, route endpoints, Geo V2 network behavior, and controlled demonstrations. Artifact tests cover schema ordering, metadata compatibility, scaler alignment, and model loading.", "Frontend tests cover route selection, live status, polling, vehicle updates, layer toggles, prediction metadata, demo creation, reset behavior, and route prerequisites. Build checks cover Python compilation, clean FastAPI import, TypeScript compilation, and the production bundle. The verified current suite contains 117 passing backend tests and 17 passing Traffic Map tests."),
        ("APPENDIX U: Reproducibility Checklist", "A reproducible run records the source repository revision, Python and Node versions, database connection configuration, network source and version, model artifact identity, feature version, dataset manifest, and test command. The Geo V2 workflow imports the cached OSM network before route or map inspection. Model evaluation uses the frozen artifact rather than retraining during application startup.", "A reviewer should verify the manifest counts, network segment and transition counts, selected checkpoint, feature order, and recorded metrics. Screenshots should be captured only after the active network and artifact metadata are visible. Secrets, local passwords, and API keys must be omitted from screenshots and from the submitted report."),
        ("APPENDIX V: Limitations Register", "Data realism is limited because the documented Geo V2 experiment uses geographically grounded synthetic traffic. Class imbalance affects overall accuracy and minority-event recall. The model is not approved for unattended safety-critical use. Formal differential privacy, secure aggregation, production authentication, cloud orchestration, and queue-backed ingestion are not part of the current verified implementation.", "Routing is directed and distance-based by default, not a learned traffic-aware optimization. Event close-out and end-time lifecycle handling remain limited. End-to-end production throughput and memory capacity were not measured. These limitations are retained as explicit design boundaries so a future extension can be evaluated against a known baseline."),
        ("APPENDIX W: Submission Review Checklist", "Before submission, confirm that the cover and title pages use the approved identity, the certificate and declaration contain the correct student and guide details, the acknowledgement remains within one page, and the abstract is followed by keywords. Confirm that the contents, list of tables, list of figures, and abbreviations appear in the required order and that their captions match the report.", "Confirm that every chapter starts with a centered separator page, that content begins on the next page, that section headings are left aligned, that captions are single spaced, and that references are single spaced and left justified. Refresh Word fields after the final visual edit, inspect page numbers, replace reviewed figure placeholders, and ensure all final printing remains black and white where required."),
        ("APPENDIX X: Model Artifact Governance", "A deployable model artifact is more than a tensor checkpoint. Its review package must identify the model class, output labels, input feature version, exact feature order, scaler metadata, network source and version, selected round, training seed, aggregation configuration, and evaluation receipt. These fields allow the runtime to determine whether a checkpoint can interpret the current feature rows. A filename alone is not sufficient evidence of compatibility.", "Promotion should occur only after validation selection and one-time test evaluation are recorded. The application loads the promoted artifact in evaluation mode and does not retrain or mutate it when the demonstration starts. A future artifact should receive a new immutable identity and should retain its own metric report. This governance prevents scenario behavior, local experimentation, or an accidental schema change from silently altering the model presented in the final project demonstration."),
        ("APPENDIX Y: Live Operations Review", "A live-operations review checks database health, network identity, artifact readiness, ingestion freshness, current segment count, prediction coverage, active vehicle count, and route scope. A stale snapshot must remain visibly different from a fresh one. Missing predictions must remain unavailable rather than being converted to normal. The source and run fields should be inspected whenever a controlled demonstration is active so its state is not confused with another live feed.", "Stopping or resetting a run should clean bounded demonstration state while preserving the canonical network and any route the user still needs to inspect. Logs should identify validation failures without exposing secrets. Operational incidents such as database unavailability, malformed batches, incompatible artifacts, or expired runs should produce explicit user-facing states. Production alerting, service-level objectives, and distributed failover were not measured in the current implementation and remain future deployment work."),
        ("APPENDIX Z: Model Input Traceability", "A model-input trace begins with a scoped live observation and its canonical segment identity. The current-state projection aggregates speed and traffic quantities for the relevant timestamp, normal memory supplies baseline values, and shifted earlier windows supply causal history. Directed topology contributes observed-neighbor context. The resulting values are ordered according to the frozen 23-feature schema before scaling and inference. Each stage can therefore be inspected without exposing a scenario label to the classifier.", "Traceability also requires negative evidence. A reviewer should confirm that latitude, longitude, vehicle identity, device identity, event ID, scenario name, severity, and ground-truth fields are absent from the emitted feature names. Model identity, feature version, network version, source, run, segment, and timestamp remain metadata around the prediction rather than learned input values. This distinction allows a prediction to be reproduced while preserving the label-free runtime contract."),
        ("APPENDIX AA: Failure-State Handling", "The runtime distinguishes an invalid request, unavailable evidence, normal prediction, abnormal prediction, and stale snapshot. Invalid routes or unknown segments are rejected before simulation. Missing history or incompatible artifact metadata prevents a valid inference rather than producing a guessed class. A stale snapshot remains visible as stale, and an expired demonstration run cannot silently continue to populate the active view. These states make operational uncertainty observable to the user.", "Failure handling is tested across service and interface boundaries. Repository or database errors remain backend failures; schema violations remain request errors; insufficient prediction coverage remains an availability condition; and a controlled scenario remains demonstration metadata. The frontend should preserve useful independent state, such as a calculated route, when a demonstration is reset. Production retry policies, distributed failover, and service-level objectives are not verified in the current repository and must not be inferred from these local safeguards."),
        ("APPENDIX AB: Evaluation Evidence Checklist", "The frozen-model evaluation review should begin with the immutable artifact identity, selected round, feature schema, network version, split manifest, and one-time test receipt. Aggregate accuracy must be read with macro F1, event-balanced macro F1, anomaly precision, anomaly recall, normal false-positive rate, and the per-class confusion matrix. The dominant Normal class explains why high accuracy does not establish reliable detection of every temporary event.", "System evidence is reviewed separately from classifier quality. Backend and frontend tests demonstrate implemented contracts, the production build demonstrates compile-time compatibility, network statistics demonstrate imported topology, and the warmed CPU measurement describes only an isolated model call. None of these establishes measured city-wide accuracy, database load capacity, browser memory limits, or safety-critical suitability. A final evaluation statement should therefore identify both the evidence source and the scope it supports."),
    ]
    for appendix_number, (title, first, second) in enumerate(evidence_pages, start=11):
        doc.add_page_break()
        heading(doc, f"APPENDIX {appendix_number}: {title.split(': ', 1)[1]}", level=2)
        p(doc, first)
        p(doc, second)


def consolidated_appendices(doc: Document) -> None:
    """Render a compact evidence appendix set without page-inflating breaks."""
    appendix_heading(doc, "APPENDIX A: Project Setup and Reproduction")
    p(doc, "Prepare the Python and Node.js environments, start PostgreSQL with PostGIS, apply migrations, import the cached Geo V2 network, start FastAPI and Vite, open the Traffic Map, calculate a directed route, and run a bounded demonstration. The exact local commands remain in HOW_TO_RUN_PROJECT.md and README.md.")
    appendix_heading(doc, "APPENDIX B: Geo V2 Feature and Model Specification")
    p(doc, "The promoted artifact uses feature version geo-v2-history_spatial_strong-23-v2 and the exact 23-feature order documented in Chapter 4. The groups are current traffic state, cyclical time, road metadata, normal baselines, baseline deviations, prior-window means, trends, low-speed persistence, and directed-neighbor speed context. Runtime input excludes labels, scenario names, event IDs, vehicle IDs, and severity. GeoV2MLP maps 23 values through 64 and 32 hidden units to eight output classes, with the frozen scaler and compatibility metadata loaded before inference.")
    table(doc, "Table A.1: Promoted Artifact and Network Identity", ["Item", "Verified value"], [["Artifact", "Geo V2 federated checkpoint, selected round 45"], ["Feature version", "geo-v2-history_spatial_strong-23-v2"], ["Model", "GeoV2MLP, 23 -> 64 -> 32 -> 8"], ["Clients", "Eight regional clients"], ["Network", "osm_geo_v2 / beeramguda-osm-20260506"], ["Topology", "2,968 segments; 11,259 directed transitions"]])
    appendix_heading(doc, "APPENDIX C: Database, Network and API Specification")
    p(doc, "The database lifecycle imports and versions the OSM-derived network, persists canonical segments and directed transitions, accepts identity-checked live batches, stores append-only observations, builds current segment projections, and persists predictions separately. Route responses contain snapped endpoints, distance, duration, ordered segment IDs, geometry, and prediction coverage. A valid route does not require complete prediction coverage.")
    appendix_heading(doc, "APPENDIX D: Testing and Validation Evidence")
    p(doc, "The verified evidence register contains 117 passing backend tests, 17 focused Traffic Map tests, a successful frontend production build, Python compilation, FastAPI import, artifact compatibility checks, and normalized network counts. The frozen artifact reports validation macro F1 0.3042, test accuracy 0.9952, test macro F1 0.3200, event-balanced macro F1 0.4459, anomaly recall 0.3444, anomaly precision 0.2093, and normal false-positive rate 0.0031. Accuracy is dominated by Normal traffic; minority-event metrics define the limitation.")
    appendix_heading(doc, "APPENDIX E: Demonstration and Application Screenshot Register")
    p(doc, "Normal, Congestion, and Accident are route-bound controlled traffic behaviors. Their scenario metadata remains outside model features and does not become ground truth. The six compact positions in Chapter 5 are reserved for reviewed application screenshots only. No unavailable screenshot is represented as an actual application result.")
    for number, caption in [("5.2", "Dynamic Traffic Map"), ("5.3", "Moving Vehicle Visualization"), ("5.4", "Route-Bound Demonstration Flow"), ("5.5", "Normal Traffic Demonstration"), ("5.6", "Congestion Demonstration"), ("5.7", "Accident Demonstration")]:
        application_screenshot_entry(doc, number, caption)
    appendix_heading(doc, "APPENDIX F: Reproducibility and Artifact Register")
    p(doc, "A reproducible run records repository revision, Python and Node versions, database configuration, network source and version, dataset manifest, feature schema, artifact identity, selected round, model metrics, and test commands. Credentials, API keys, passwords, and local environment secrets must be omitted from evidence captures and the submitted report.")
    appendix_heading(doc, "APPENDIX G: Limitations and Final Review Checklist")
    p(doc, "The experiment uses geographically grounded synthetic traffic, has imbalanced event classes, uses distance-based default routing, and does not implement differential privacy, secure aggregation, production authentication, queue-backed ingestion, cloud orchestration, or measured city-scale capacity. Before submission, confirm refreshed Word fields, populated lists, unnumbered chapter separators, continuous Arabic numbering, matching captions, in-margin tables, print-safe diagrams, and absence of secrets.")


def legacy_main_content(doc: Document) -> None:
    chapter(doc, 1, "Introduction")
    heading(doc, "1.1 Introduction")
    p(doc, "Urban traffic changes continuously because of congestion, accidents, construction, flooding, diversions, road damage, and temporary closures. A traffic intelligence system must therefore observe behavior over time and distinguish normal variation from a short-lived road event. FedRouteAI addresses this requirement by using GPS-derived traffic observations, road-segment baselines, spatial topology, and machine learning in a federated architecture.")
    p(doc, "The system is designed as a detection and decision-support layer rather than a replacement for a commercial navigation application. It receives telemetry, associates observations with a canonical road network, builds causal traffic features, classifies the current road state, exposes the result through APIs, and visualizes it on a dynamic map. Directed shortest-path routing is provided for route inspection and explicit alternatives.")
    heading(doc, "1.2 Motivation")
    p(doc, "Centralized traffic analytics can require collection of sensitive mobility traces. Federated learning is relevant because regional traffic clients can train on local data and send model updates instead of raw trajectories. Traffic also has strong spatial and temporal structure: a segment's current speed is meaningful only in relation to its normal baseline, recent history, road metadata, and neighboring segments. These observations motivate the Geo V2 feature design.")
    heading(doc, "1.3 Problem Statement")
    p(doc, "The project problem is to build and validate an end-to-end system that detects temporary road conditions from GPS traffic behavior while preserving a clear separation between training data, road-network data, live telemetry, and controlled demonstration telemetry. The system must support regional learning, label-free inference, map visualization, and directed route inspection without overstating synthetic demonstrations as real-world ground truth.")
    heading(doc, "1.4 Objectives")
    for text in ["Build a complete GPS ingestion, segment association, aggregation, inference, and visualization pipeline.", "Train a federated MLP through eight regional clients and aggregate client updates with FedAvg-family strategies.", "Construct a causal Geo V2 feature contract using current, historical, temporal, and spatial information.", "Import and persist a geographically grounded OSM road network in PostGIS with directed transitions.", "Provide a dynamic React-Leaflet traffic map and a controlled route-bound demonstration.", "Validate the system with unit, integration, frontend, build, artifact, and runtime checks."]:
        p(doc, "- " + text, indent=False, after=3)
    heading(doc, "1.5 Scope and Organization")
    p(doc, "The implementation covers GPS-based traffic intelligence, federated model training, OSM/PostGIS road topology, live ingestion, map visualization, and distance-based directed routing. CCTV analytics, formal differential privacy, secure aggregation, cloud-scale queueing, and learned traffic-aware route costs are future work. Chapters 2 through 10 present the survey, requirements, architecture, implementation, validation, deployment considerations, conclusion, appendices, and references.")
    chapter(doc, 2, "Literature Survey")
    heading(doc, "2.1 Intelligent Transportation Systems")
    p(doc, "Intelligent Transportation Systems use sensing, communication, computation, and decision support to improve transportation operations. GPS trajectories provide a scalable source of movement information, but raw coordinates must be transformed into road-level observations before traffic conditions can be interpreted.")
    heading(doc, "2.2 Traffic Anomaly and Event Detection")
    p(doc, "Traffic anomaly detection methods commonly compare current speed, density, occupancy, flow, or travel time against historical patterns. Rule-based signatures are interpretable and useful for cold-start operation, while supervised models can learn boundaries among several event classes. FedRouteAI combines a learned MLP with explicit baseline and history features, while retaining rule-based fallback behavior where required by the runtime design.")
    heading(doc, "2.3 Federated Learning")
    p(doc, "Federated learning coordinates model training across clients without requiring every raw record to be transferred to a central server. FedAvg aggregates client model parameters weighted by local contributions. Adaptive aggregation can incorporate data quality, event confidence, historical similarity, temporal freshness, and regional relevance. In this project, the architecture uses eight regional clients and does not claim differential privacy or secure aggregation unless separately implemented.")
    heading(doc, "2.4 Neural Networks for Traffic Classification")
    p(doc, "A multilayer perceptron is suitable for the project's tabular feature contract because it accepts a fixed ordered vector and produces class probabilities. XGBoost is retained as a centralized baseline for comparison, while the federated model uses continuous neural-network parameters compatible with FedAvg aggregation.")
    heading(doc, "2.5 Map Matching, OSM, and Spatial Routing")
    p(doc, "Map matching associates GPS observations with road segments. OpenStreetMap supplies road geometry and tags, while PostGIS provides spatial persistence and indexing. A directed segment graph supports legal movement transitions and shortest-path algorithms such as Dijkstra. These components connect traffic intelligence to actual road structure.")
    heading(doc, "2.6 Research Gap and Project Contribution")
    p(doc, "The project contribution is an integrated prototype that joins federated tabular learning, causal traffic features, historical memory, spatial neighbors, OSM/PostGIS topology, live ingestion, map visualization, and route-bound demonstrations. The result is evaluated as a complete engineering pipeline rather than as an isolated classifier alone.")

    chapter(doc, 3, "Requirement Analysis and Feasibility Study")
    heading(doc, "3.1 Stakeholders")
    p(doc, "The main stakeholders are traffic operators who inspect road conditions, researchers who evaluate federated models, regional data clients that contribute local updates, and end users who inspect a route and current road state. College project evaluators are also stakeholders because reproducibility, traceability, and honest limitations are required.")
    table(doc, "Table 3.1: Functional Requirements", ["ID", "Requirement", "Verification"], [["FR-01", "Ingest GPS or trusted live observations", "API and integration tests"], ["FR-02", "Associate observations with road segments", "Map-matching tests"], ["FR-03", "Construct historical and Geo V2 features", "Feature-contract checks"], ["FR-04", "Run frozen MLP inference", "Artifact and prediction tests"], ["FR-05", "Persist and serve prediction state", "Live map API tests"], ["FR-06", "Display roads, vehicles, events, and predictions", "Frontend tests and build"], ["FR-07", "Calculate directed shortest routes", "Routing tests"], ["FR-08", "Run Normal, Congestion, and Accident demonstrations", "Route-bound demo tests"]])
    table(doc, "Table 3.2: Non-Functional Requirements", ["Property", "Requirement"], [["Correctness", "Inference must follow the ordered feature contract and directed topology."], ["Traceability", "Model, network, feature, and run metadata must be observable."], ["Honesty", "Scenario truth must not be presented as model prediction."], ["Reliability", "Invalid routes, missing fields, and expired demo runs must fail clearly."], ["Usability", "The map must expose live status, route information, and layer controls."], ["Maintainability", "API, service, repository, model, and schema layers remain separated."]])
    table(doc, "Table 3.3: Software and Hardware Requirements", ["Category", "Requirement"], [["Backend", "Python 3.12+, FastAPI, SQLAlchemy, Alembic, PyTorch, Flower"], ["Database", "PostgreSQL with PostGIS"], ["Frontend", "Node.js 18+, React, Vite, Leaflet"], ["ML", "CPU inference supported; training benefits from GPU"], ["Storage", "Model artifacts, telemetry, feature tables, and PostgreSQL storage"], ["Network", "OpenStreetMap cached source and local API connectivity"]])
    heading(doc, "3.2 Feasibility Study")
    p(doc, "Technical feasibility is supported by the existing Python and React stack, the cached OSM source, a local PostGIS database, and a frozen model artifact. Operational feasibility is supported by a local launcher, documented API endpoints, bounded demo runs, and a map interface. Economic feasibility is appropriate for a college prototype because the software stack is open source and the demonstrations can run locally. Ethical feasibility depends on presenting synthetic and controlled data honestly and avoiding claims of formal privacy guarantees that are not implemented.")

    chapter(doc, 4, "System Design and Architecture")
    heading(doc, "4.1 High-Level Architecture")
    p(doc, "FedRouteAI follows a layered architecture. API endpoints parse requests and call services. Services implement business logic and coordinate repositories. Repositories perform database access. Models represent database entities, while Pydantic schemas define API contracts. The ML subsystem is connected through explicit feature and artifact contracts.")
    figure(doc, "4.1", "Overall System Architecture of FedRouteAI")
    heading(doc, "4.2 Federated Learning Architecture")
    p(doc, "Eight regional clients are identified as REGION_01 through REGION_08. Each client trains locally on its regional partition. The Flower server coordinates rounds and aggregates model updates. The central application serves the selected global artifact and does not need raw regional trajectories for runtime classification.")
    figure(doc, "4.2", "Federated Learning Architecture")
    figure(doc, "4.3", "Regional Client Architecture")
    heading(doc, "4.3 Data Pipeline")
    p(doc, "The training and evaluation dataset is separate from the OSM/PostGIS network and from live telemetry. The Geo V2 generated dataset contains five hours, a 1,000-vehicle configuration, 30,000 telemetry rows, three scenario rows, and 16,338 feature windows according to its manifest. The OSM network supplies geometry and topology. Live or controlled telemetry is generated or ingested at runtime. These sources meet at segment IDs and timestamps but have different roles.")
    figure(doc, "4.4", "End-to-End Data Pipeline")
    heading(doc, "4.4 Geo V2 Feature Contract")
    p(doc, "The final promoted Geo V2 artifact uses feature version geo-v2-history_spatial_strong-23-v2. It uses 22 current/history features plus the directed same-timestamp neighbor_speed_delta feature. Feature construction has no target argument and rejects label, event, scenario, ground_truth, vehicle_id, device_id, severity, and related forbidden tokens.")
    feature_rows = [[str(i + 1), name, "Current" if i < 11 else "Historical/derived" if i < 22 else "Spatial"] for i, name in enumerate(["avg_speed_kmph", "speed_std_kmph", "vehicle_count", "occupancy", "flow_rate_vph", "stopped_fraction", "hour_sin", "hour_cos", "road_type_code", "lane_count", "max_speed_kmph", "baseline_speed_kmph", "baseline_speed_std_kmph", "baseline_vehicle_count", "speed_to_baseline", "count_to_baseline", "std_to_baseline", "prior_speed_mean_3", "prior_count_mean_3", "speed_trend", "count_trend", "low_speed_persistence_3", "neighbor_speed_delta"])]
    table(doc, "Table 4.1: Exact 23-Feature Geo V2 Contract", ["No.", "Feature", "Category"], feature_rows)
    figure(doc, "4.5", "Geo V2 Feature Pipeline")
    heading(doc, "4.5 Historical Traffic Memory")
    p(doc, "Historical memory stores normal traffic references for road segments. Geo V2 uses baseline speed, baseline speed standard deviation, and baseline vehicle count, then derives ratios and trends. Prior windows are shifted so current observations cannot leak into their own historical features. The feature cadence is exactly 120 seconds and the model uses causal t-1, t-2, and t-3 slots. Missing history uses fixed normal prehistory values from the training reference.")
    figure(doc, "4.6", "Historical Traffic Memory")
    heading(doc, "4.6 OSM/PostGIS Network")
    p(doc, "The cached Beeramguda/Ashok Nagar road source is normalized from OpenStreetMap JSON into canonical segments and directed transitions. The verified normalized network contains 2,968 segments, 11,259 transitions, and eight regions. PostGIS stores LineString geometry and supports spatial queries; directed transitions preserve legal movement between segments.")
    table(doc, "Table 4.2: Verified OSM/PostGIS Network Statistics", ["Property", "Value"], [["Network source", "osm_geo_v2"], ["Network version", "beeramguda-osm-20260506"], ["Canonical segments", "2,968"], ["Directed transitions", "11,259"], ["Regions", "8"], ["Bounding box", "78.2746597 to 78.3162335 longitude; 17.5020132 to 17.5323815 latitude"]])
    figure(doc, "4.7", "OSM/PostGIS Road-Network Architecture")
    figure(doc, "4.8", "Directed Road Network and Transitions")
    heading(doc, "4.7 Backend and Frontend Architecture")
    p(doc, "The FastAPI backend exposes health, segments, live ingestion, prediction, events, routing, and demonstration endpoints. The React-Leaflet frontend fetches network geometry and live snapshots, renders roads and vehicles, displays prediction states, and overlays calculated routes. React Query manages server interaction while the map maintains independent telemetry, prediction, event, and vehicle layers.")
    figure(doc, "4.9", "Backend Service Architecture")
    figure(doc, "4.10", "Frontend Architecture")
    heading(doc, "4.8 Routing Design")
    p(doc, "The routing service snaps origin and destination coordinates to the network, calculates a directed path, returns the ordered segment sequence and actual geometry, and reports distance, estimated duration, and segment count. The default shortest route is distance-based. Prediction inspection and explicit segment exclusion are separate behaviors; the current system should not be described as a learned traffic-aware routing optimizer.")
    figure(doc, "4.11", "Directed Shortest-Path Routing")

    chapter(doc, 5, "Implementation")
    heading(doc, "5.1 Project Module Mapping")
    table(doc, "Table 5.1: Major Software Modules", ["Module", "Role"], [["app/api", "Thin HTTP endpoints and request validation"], ["app/services/live_ingestion", "Batch ingestion, aggregation, and persistence orchestration"], ["app/services/geo_v2", "Network, simulation, feature alignment, and Geo V2 runtime"], ["app/ml/geo_v2", "Causal features, model store, training metadata, and inference contract"], ["app/repositories", "Database queries and PostGIS persistence"], ["frontend/src/pages/TrafficMap", "Dynamic map, route planner, demo controls, and inspection"], ["scripts/geo_v2", "Network import, dataset generation, replay, and validation"]])
    heading(doc, "5.2 Live GPS Ingestion")
    p(doc, "Live telemetry enters through the ingestion API as observations associated with source and run identity. Observations are validated, persisted, and projected into current segment state. Segment-level aggregates are then combined with historical memory and prior ticks to construct the 23-feature vector. Inference receives features rather than scenario labels. Prediction results are stored separately from the raw telemetry and exposed in the live snapshot.")
    figure(doc, "5.1", "Live GPS Ingestion Pipeline")
    heading(doc, "5.3 Frozen Geo V2 MLP")
    p(doc, "The promoted model is an MLP trained through eight geographic clients. Its metadata specifies 50 maximum federated rounds, two local epochs, seed 42, unweighted NLL, bounded aggregation projection, and checkpoint selection at round 45. The model store validates feature ordering and artifact metadata before loading. A malformed or mismatched artifact fails closed rather than silently producing predictions.")
    table(doc, "Table 5.2: Federated Client Configuration", ["Property", "Current implementation"], [["Clients", "8 regional clients: REGION_01 through REGION_08"], ["Model", "Geo V2 PyTorch MLP"], ["Aggregation", "FedAvg-family with adaptive weighting in the training workflow"], ["Feature version", "geo-v2-history_spatial_strong-23-v2"], ["Maximum rounds", "50"], ["Selected checkpoint", "Round 45"], ["Local epochs", "2"], ["Random seed", "42"]])
    heading(doc, "5.4 Dynamic Traffic Map")
    p(doc, "The Traffic Map presents OSM road geometry, current telemetry, moving vehicles, prediction states, live freshness, network identity, route overlays, origin and destination markers, and scenario controls. Vehicle positions are animated between authoritative backend snapshots for visual continuity; intermediate movement is not presented as additional GPS evidence. A rendering cap keeps the browser responsive while backend counts remain authoritative.")
    figure(doc, "5.2", "Dynamic Traffic Map")
    figure(doc, "5.3", "Moving Vehicle Visualization")
    heading(doc, "5.5 Controlled Route-Bound Demonstration")
    p(doc, "The user selects an origin and destination, calculates a directed route, and must use a route of at least approximately 1.5 km. The selected ordered segment IDs are passed to the demonstration service. Vehicles follow that route and telemetry flows through the existing ingestion and frozen-model pipeline. The available scenarios are Normal, Congestion, and Accident. The UI separately reports route behavior and model prediction coverage. The correct interpretation is: Traffic behavior only. Not ground truth.")
    figure(doc, "5.4", "Route-Bound Demonstration Flow")
    figure(doc, "5.5", "Normal Traffic Demonstration")
    figure(doc, "5.6", "Congestion Demonstration")
    figure(doc, "5.7", "Accident Demonstration")
    heading(doc, "5.6 API Summary")
    table(doc, "Table 5.3: API and Data Flow Summary", ["Interface", "Purpose"], [["GET /health", "Service liveness"], ["GET /segments", "Canonical road geometry"], ["POST /ingest/live/batch", "Trusted pre-matched live observations"], ["GET /live-map/snapshot", "Current map state and metadata"], ["POST /routes/shortest", "Directed shortest route"], ["POST /demo/geo-v2/runs", "Create route-bound demonstration"], ["POST /demo/geo-v2/runs/{id}/step", "Advance demonstration"], ["DELETE /demo/geo-v2/runs/{id}", "Stop and clean up demonstration"]])

    chapter(doc, 6, "Testing and Validation")
    heading(doc, "6.1 Testing Strategy")
    p(doc, "Testing covers pure service logic, API contracts, database-backed behavior where required, frontend interaction, artifact loading, Python compilation, and production build behavior. Fixture-free tests are used where possible because feature and routing logic should be testable without a live database. Integration tests cover ingestion-to-detection behavior and scoped live snapshots.")
    heading(doc, "6.2 Backend Validation")
    p(doc, "The current verified backend suite contains 117 passing tests. It includes map matching, event detection, historical memory, adaptive aggregation, routing, live ingestion, Geo V2 features, model contracts, controlled demonstrations, and API behavior. A deprecation warning from the local Starlette/httpx combination is non-fatal and does not represent a project test failure.")
    heading(doc, "6.3 Frontend Validation")
    p(doc, "The Traffic Map frontend suite includes 17 passing tests for route selection, live status, polling, vehicle updates, map layers, prediction metadata, route-bound demo creation, reset behavior, and route prerequisites. The frontend production build also completes successfully through TypeScript compilation and Vite bundling.")
    heading(doc, "6.4 Model Validation")
    p(doc, "The frozen model report records a validation macro F1 of 0.3042 and a one-time full-test macro F1 of 0.3200. Test accuracy is 0.9952, event-balanced macro F1 is 0.4459, anomaly recall is 0.3444, anomaly precision is 0.2093, and normal false-positive rate is 0.0031. These results must be read with the class imbalance and event-class limitations: diversion recall is zero and construction recall is low. The model is not approved for unattended safety-critical operation.")
    table(doc, "Table 6.1: Verification Summary", ["Verification", "Result"], [["Backend tests", "117 passed"], ["Traffic Map frontend tests", "17 passed"], ["Frontend production build", "Passed"], ["Python compilation", "Passed"], ["Artifact import and metadata validation", "Passed"], ["Network normalization", "2,968 segments and 11,259 transitions"]])
    table(doc, "Table 6.2: Frozen Model Results", ["Metric", "Value"], [["Validation macro F1", "0.3042"], ["Test accuracy", "0.9952"], ["Test macro F1", "0.3200"], ["Event-balanced macro F1", "0.4459"], ["Anomaly recall", "0.3444"], ["Anomaly precision", "0.2093"], ["Normal FPR", "0.0031"]])
    figure(doc, "6.1", "Model Validation Results")
    figure(doc, "6.2", "Confusion Matrix")
    figure(doc, "6.3", "Testing Evidence")
    heading(doc, "6.5 Limitations Revealed by Validation")
    p(doc, "The high overall accuracy is influenced by the dominant normal class and therefore is not sufficient by itself. Event precision and minority-class recall require careful interpretation. The system uses geographically grounded synthetic data for the documented demonstration, not measured city-scale traffic. A controlled scenario can exercise the pipeline but cannot establish real-world predictive validity.")

    chapter(doc, 7, "Results and Discussion")
    heading(doc, "7.1 Results Interpretation")
    p(doc, "The application can be run as separate local processes: PostgreSQL/PostGIS, FastAPI, Vite, and optional simulator or Geo V2 replay processes. Alembic applies the schema, the network importer creates the additive Geo V2 network, and the frontend connects to the backend through its configured API base URL. Docker is useful for a disposable PostGIS container but is not the application deployment architecture itself.")
    figure(doc, "7.1", "Local Deployment Architecture")
    heading(doc, "7.2 Security and Privacy Position")
    p(doc, "The architecture is motivated by data minimization through federated training and label-free runtime features. However, the implementation does not claim differential privacy, secure aggregation, encryption guarantees, or formal privacy bounds. API keys are used for trusted live-ingestion workflows where configured. Secrets and database passwords must remain in local environment configuration and must not be committed to the report or source control.")
    heading(doc, "7.3 Performance and Scalability")
    p(doc, "The verified artifact report records average CPU single-row inference of approximately 0.414 ms across 1,000 warmed calls, or approximately 2,416 calls per second under that measurement setup. The five-hour demonstration configuration contains 1,000 persistent vehicles and 150 ten-minute ticks. The manifest records 30,000 telemetry rows because 1,000 vehicles are represented at each of 30 ten-minute steps in that generated run; this is distinct from model prediction count, which is segment/batch based.")
    table(doc, "Table 7.1: Runtime Performance Evidence", ["Measure", "Verified value / interpretation"], [["Single-row CPU inference", "0.414 ms average after warm-up"], ["Approximate inference throughput", "2,416 calls/second in the recorded setup"], ["Demonstration vehicles", "1,000 persistent vehicles"], ["Demonstration duration", "5 simulated hours"], ["Demonstration ticks", "150 ten-minute ticks in the intended replay configuration"], ["Prediction granularity", "Observed road segment/batch, not one prediction per vehicle"]])
    table(doc, "Table 7.2: Current Limitations", ["Area", "Limitation"], [["Data", "Geographically grounded synthetic telemetry is not measured traffic."], ["Model", "Minority event recall and anomaly precision remain limited."], ["Privacy", "Formal differential privacy and secure aggregation are not implemented."], ["Routing", "Default cost is distance-based, not learned traffic-aware routing."], ["Operations", "Background/in-process demonstration execution is a bounded prototype scope."], ["Events", "Event close-out and end-time lifecycle handling remain limited."], ["Deployment", "Production cloud orchestration and queue infrastructure are future work."]])

    chapter(doc, 8, "Summary and Conclusions")
    heading(doc, "8.1 Conclusion")
    p(doc, "FedRouteAI demonstrates a complete traffic intelligence prototype that combines federated learning, a Geo V2 causal feature contract, historical traffic memory, OSM/PostGIS road topology, live GPS ingestion, frozen MLP inference, dynamic map visualization, and directed shortest-path routing. The system is organized around traceable contracts: the road network is distinct from the ML dataset, live telemetry is distinct from controlled demonstration behavior, and model features exclude scenario truth.")
    p(doc, "The implementation has been validated through backend and frontend tests, artifact checks, build checks, and network normalization evidence. It is suitable as a B.Tech major project demonstration and a foundation for further research. Its results are reported honestly: the model improves the preserved baseline according to its recorded metrics, but minority event performance, synthetic-data realism, formal privacy mechanisms, and production-scale operations remain open limitations.")
    heading(doc, "8.2 Learning Outcomes")
    p(doc, "The project provided experience in federated model design, tabular feature engineering, causal time-window construction, PyTorch training, PostGIS spatial data, directed graph routing, FastAPI service architecture, React-Leaflet visualization, testing, artifact governance, and technical documentation. It also required distinguishing model evidence from demonstration behavior and separating system subsystems by their data responsibilities.")
    heading(doc, "8.3 Future Enhancements")
    for text in ["Collect and validate larger real-world GPS traffic datasets across seasons and cities.", "Improve event-specific sampling and class-balanced training for diversion, construction, and other minority classes.", "Evaluate stronger adaptive federated aggregation and larger client populations.", "Add formal differential privacy, secure aggregation, and auditable privacy accounting.", "Develop traffic-aware route costs after validating prediction reliability and operational safety.", "Move ingestion and replay work to queue-backed services for scale.", "Explore online learning, edge deployment, and energy-aware regional clients.", "Evaluate CCTV or video integration only as a separate future extension, not as part of the current system."]:
        p(doc, "- " + text, indent=False, after=3)

    appendix_heading(doc, "APPENDIX 1: Project Run and Reproduction Guide")
    p(doc, "The current project can be started by preparing Python and Node.js environments, starting PostgreSQL with PostGIS, applying Alembic migrations, importing the cached Geo V2 network, starting the FastAPI backend and Vite frontend, opening the Traffic Map, starting live mode, calculating a route, and selecting a route-bound demonstration. The exact operational commands are maintained in HOW_TO_RUN_PROJECT.md and README.md.")
    heading(doc, "APPENDIX B: Evidence and Artifact Register", level=2)
    table(doc, "", ["Evidence", "Role"], [["Geo V2 model report", "Frozen selection, metrics, limitations, and runtime contract"], ["Feature schema JSON", "Ordered 23-feature contract and version"], ["Network source JSON", "Cached OSM input for normalized segments and transitions"], ["Dataset manifest", "Five-hour data configuration and telemetry counts"], ["Backend test suite", "Service, API, model, ingestion, and routing validation"], ["Frontend test suite", "Traffic Map and interaction validation"]])
    heading(doc, "APPENDIX C: Figure Insertion Register", level=2)
    p(doc, "All figure spaces in this report are intentional placeholders. Final SVG, PNG, or PDF figures must be prepared from the current implementation and inserted only after this report draft is reviewed and figure numbering is accepted. No final figures are included in this first documentation pass.")
    for text in ["Figure 4.1-4.10: Architecture and design figures", "Figure 5.1-5.7: Implementation and demonstration figures", "Figure 6.1-6.3: Validation and testing figures", "Figure 7.1: Deployment figure"]:
        p(doc, "- " + text, indent=False, after=3)

    chapter(doc, 10, "References")
    refs = [
        "[1] H. B. McMahan et al., \"Communication-Efficient Learning of Deep Networks from Decentralized Data,\" in Proceedings of AISTATS, 2017.",
        "[2] B. McMahan and D. Ramage, \"Federated Learning: Collaborative Machine Learning without Centralized Training Data,\" Google Research, 2017.",
        "[3] P. Kairouz et al., \"Advances and Open Problems in Federated Learning,\" Foundations and Trends in Machine Learning, vol. 14, nos. 1-2, 2021.",
        "[4] I. Goodfellow, Y. Bengio, and A. Courville, Deep Learning. MIT Press, 2016.",
        "[5] C. M. Bishop, Pattern Recognition and Machine Learning. Springer, 2006.",
        "[6] Y. LeCun, Y. Bengio, and G. Hinton, \"Deep Learning,\" Nature, vol. 521, pp. 436-444, 2015.",
        "[7] OpenStreetMap contributors, \"OpenStreetMap,\" https://www.openstreetmap.org/ (accessed 2026).",
        "[8] PostGIS Project Steering Committee, \"PostGIS Documentation,\" https://postgis.net/documentation/ (accessed 2026).",
        "[9] E. W. Dijkstra, \"A Note on Two Problems in Connexion with Graphs,\" Numerische Mathematik, vol. 1, pp. 269-271, 1959.",
        "[10] M. Abadi et al., \"TensorFlow: Large-Scale Machine Learning on Heterogeneous Systems,\" 2015.",
        "[11] A. Paszke et al., \"PyTorch: An Imperative Style, High-Performance Deep Learning Library,\" in NeurIPS, 2019.",
        "[12] FastAPI Documentation, \"FastAPI Web Framework,\" https://fastapi.tiangolo.com/ (accessed 2026).",
        "[13] React Documentation, \"React,\" https://react.dev/ (accessed 2026).",
        "[14] Leaflet Documentation, \"Leaflet JavaScript Library,\" https://leafletjs.com/ (accessed 2026).",
        "[15] NetworkX Developers, \"NetworkX Documentation,\" https://networkx.org/ (accessed 2026).",
        "[16] W. McKinney, Python for Data Analysis, 3rd ed. O'Reilly Media, 2022.",
        "[17] F. Pedregosa et al., \"Scikit-learn: Machine Learning in Python,\" Journal of Machine Learning Research, vol. 12, pp. 2825-2830, 2011.",
        "[18] Project technical source: FedRouteAI repository, current backend, frontend, Geo V2 scripts, tests, dataset manifests, and frozen artifact metadata, accessed 2026.",
    ]
    for ref in refs: p(doc, ref, indent=False, after=6)


def legacy_expanded_main_content(doc: Document) -> None:
    """Build the expanded report from the verified project evidence."""
    chapter(doc, 1, "Introduction")
    heading(doc, "1.1 Introduction")
    p(doc, "FedRouteAI is an end-to-end traffic intelligence prototype that detects temporary road conditions from GPS-derived traffic behavior and supports route inspection. It combines an OSM/PostGIS directed network, live telemetry aggregation, historical traffic memory, a causal 23-feature Geo V2 contract, an eight-client federated MLP, and a React-Leaflet map. The system is designed for traceable academic evaluation: every important transformation has an explicit data boundary and the controlled demonstration is kept separate from model ground truth.")
    chapter1_expansion(doc)
    chapter(doc, 2, "Literature Survey")
    heading(doc, "2.1 Introduction")
    p(doc, "This chapter places the project at the intersection of intelligent transportation systems, GPS traffic analysis, anomaly detection, federated learning, spatial databases, and routing. The review focuses on the design decisions that are implemented in the repository and on the gap addressed by integrating them into one inspectable pipeline.")
    chapter2_expansion(doc)
    chapter(doc, 3, "Requirement Analysis and Feasibility Study")
    heading(doc, "3.1 Introduction")
    p(doc, "This chapter translates the current implementation into requirements that can be verified through APIs, services, artifacts, tests, and controlled operation.")
    heading(doc, "3.2 Problem Requirements")
    p(doc, "The system must transform GPS-derived observations into segment traffic state, classify current road behavior through the frozen Geo V2 model, serve independent prediction state, and support legal directed route inspection without treating scenario controls as labels.")
    heading(doc, "3.3 Functional Requirements")
    table(doc, "Table 3.1: Functional Requirements", ["ID", "Requirement", "Verification"], [["FR-01", "Ingest GPS or trusted live observations", "API and integration tests"], ["FR-02", "Associate observations with road segments", "Map-matching and network tests"], ["FR-03", "Construct historical and Geo V2 features", "Feature-contract checks"], ["FR-04", "Run frozen MLP inference", "Artifact and prediction tests"], ["FR-05", "Persist and serve prediction state", "Live map API tests"], ["FR-06", "Display roads, vehicles, events, and predictions", "Frontend tests and build"], ["FR-07", "Calculate directed shortest routes", "Routing tests"], ["FR-08", "Run route-bound demonstrations", "Demo validation tests"]])
    heading(doc, "3.4 Non-Functional Requirements")
    table(doc, "Table 3.2: Non-Functional Requirements", ["Property", "Requirement"], [["Correctness", "Inference follows the ordered feature contract and directed topology."], ["Traceability", "Model, network, feature, and run metadata are observable."], ["Honesty", "Scenario truth is not presented as model prediction."], ["Reliability", "Invalid routes, missing fields, and expired runs fail clearly."], ["Usability", "The map exposes live status, route information, and layer controls."], ["Maintainability", "API, service, repository, model, and schema layers remain separated."]])
    chapter3_expansion(doc)
    heading(doc, "3.16 Requirement Traceability")
    p(doc, "The requirement-to-evidence mapping connects data requirements to the Geo V2 manifest and feature builder, model requirements to the feature schema and artifact metadata, network requirements to the OSM importer and PostGIS records, runtime requirements to ingestion and prediction persistence, interface requirements to Traffic Map tests, and validation requirements to the backend, frontend, build, and smoke evidence.")
    heading(doc, "3.17 Summary")
    p(doc, "The requirements define a bounded academic prototype with explicit data, model, network, interface, and evidence contracts. Feasibility is supported by the current software stack and local deployment workflow.")
    chapter(doc, 4, "System Design and Architecture")
    heading(doc, "4.1 Introduction")
    p(doc, "FedRouteAI follows the one-directional project layering: API endpoints call services, services call repositories, and repositories access models. The ML subsystem is connected through explicit feature and artifact contracts. The frontend consumes API responses and does not reproduce backend inference or routing logic.")
    chapter4_expansion(doc)
    chapter(doc, 5, "Implementation")
    heading(doc, "5.1 Introduction")
    p(doc, "This chapter explains how the current design is implemented and operated, from the development environment and generated data through federated model deployment, live inference, map behavior, routing, and controlled demonstrations.")
    chapter5_expansion(doc)
    chapter(doc, 6, "Testing and Validation")
    heading(doc, "6.1 Introduction")
    heading(doc, "6.2 Testing Objectives")
    p(doc, "Testing covers pure service logic, API contracts, model compatibility, database-backed workflows, frontend interaction, build behavior, and runtime smoke paths. Fixture-free tests are used where possible so feature and routing rules remain diagnosable without a live database.")
    heading(doc, "6.3 Test Environment")
    p(doc, "The test environment uses the repository's Python test suite, focused frontend tests, artifact files, configured network metadata, and the production frontend build. Database-backed checks use the project's configured test approach; not every pure service test requires a live PostgreSQL instance.")
    chapter6_expansion(doc)
    heading(doc, "6.15 Model Validation Results")
    p(doc, "The frozen artifact report records validation macro F1 of 0.3042, test accuracy of 0.9952, test macro F1 of 0.3200, event-balanced macro F1 of 0.4459, anomaly recall of 0.3444, anomaly precision of 0.2093, and normal false-positive rate of 0.0031. The dominant Normal class affects accuracy, while diversion and construction remain difficult minority classes.")
    figure(doc, "6.1", "Model Validation Results")
    heading(doc, "6.16 Confusion Matrix Analysis")
    p(doc, "The confusion matrix must be read as class-specific evidence rather than as a decorative result. It shows the dominant Normal behavior alongside weak or absent recall for some minority events. This supports reporting macro and event-balanced metrics together with accuracy.")
    figure(doc, "6.2", "Confusion Matrix")
    heading(doc, "6.17 Prediction Testing")
    p(doc, "Prediction tests verify artifact compatibility, feature ordering, label-free input, persisted class and confidence, unavailable states, and scoped prediction retrieval. They do not treat a controlled scenario name as a prediction label.")
    heading(doc, "6.18 System Integration Testing")
    p(doc, "Integration coverage follows the path from accepted observations through aggregation, feature construction, inference, persistence, live snapshot retrieval, map display, route inspection, and demonstration reset.")
    heading(doc, "6.19 Test Case Design")
    p(doc, "Test cases cover valid and invalid inputs, missing history, incompatible metadata, directed route errors, idempotent ingestion, stale snapshots, frontend layer independence, and controlled scenario lifecycle.")
    heading(doc, "6.20 Testing Results")
    table(doc, "Table 6.1: Verification Summary", ["Verification", "Result"], [["Backend tests", "117 collected/passing in the verified suite"], ["Frontend tests", "46 listed by constrained discovery; 17 focused Traffic Map tests in the prior report evidence"], ["Frontend production build", "Passed"], ["Python compilation and application import", "Passed"], ["Artifact metadata validation", "Passed"], ["Network normalization", "2,968 segments and 11,259 transitions"]])
    figure(doc, "6.3", "Testing Evidence")
    heading(doc, "6.21 Summary")
    p(doc, "Testing demonstrates that the current contracts and workflows are implemented and inspectable. It does not convert synthetic data into measured city traffic or isolated model latency into a production capacity claim.")
    chapter(doc, 7, "System Evaluation and Discussion")
    heading(doc, "7.1 Introduction")
    p(doc, "The recorded results show a technically complete pipeline with strong normal-class accuracy but limited minority-event performance. This chapter interprets those results alongside the controlled demonstrations, test evidence, routing behavior, and deployment constraints. The discussion separates measured model evidence from behavior observed in a simulation.")
    heading(doc, "7.2 Model Performance")
    p(doc, "The model's high accuracy is dominated by Normal traffic. Macro F1, anomaly recall and precision, event-balanced F1, and normal false-positive rate provide a more useful view of minority behavior. The result is a useful academic baseline with clear limitations rather than an unattended detector.")
    heading(doc, "7.3 Federated Learning Evaluation")
    p(doc, "The federated workflow successfully represents eight regional clients, local training, parameter aggregation, validation-based selection, and frozen artifact promotion. It demonstrates regional learning behavior but does not claim formal privacy mechanisms.")
    heading(doc, "7.4 Geo V2 Evaluation")
    p(doc, "The exact ordered 23-feature history_spatial_strong contract is validated at runtime and retains current, historical, temporal, road, and directed-neighbor context without labels or scenario metadata.")
    heading(doc, "7.5 Historical Feature Evaluation")
    p(doc, "Shifted prior windows, normal prehistory, ratios, trends, and persistence give the model causal context while avoiding current-value leakage.")
    heading(doc, "7.6 Spatial Context Evaluation")
    p(doc, "The directed neighbor contrast connects model context to the persisted legal network rather than to arbitrary coordinate proximity.")
    heading(doc, "7.7 Runtime Inference Evaluation")
    p(doc, "The frozen artifact loads only after feature, scaler, model, and network metadata checks. Invalid or insufficient evidence remains unavailable.")
    heading(doc, "7.8 Live Map Evaluation")
    p(doc, "The map exposes roads, vehicles, prediction state, freshness, route scope, and selected-road inspection through independent layers.")
    heading(doc, "7.9 Routing Evaluation")
    p(doc, "Directed distance-based routes are returned with ordered segment IDs and geometry; predictions are inspected separately unless explicit exclusions are requested.")
    heading(doc, "7.10 Controlled Demonstration Evaluation")
    p(doc, "Normal, Congestion, and Accident controls exercise repeatable traffic behavior and orchestration. They are not ground-truth model labels.")
    heading(doc, "7.11 Deployment Evaluation")
    p(doc, "The local deployment is appropriate for a bounded academic demonstration. Queue-backed ingestion, horizontal scaling, cloud orchestration, and production authentication remain outside the verified scope.")
    figure(doc, "7.1", "Local Deployment Architecture")
    heading(doc, "7.12 Performance Discussion")
    p(doc, "Warmed single-row CPU inference averages approximately 0.414 ms over 1,000 calls in the recorded setup. This excludes HTTP, database, feature construction, browser, and end-to-end load behavior.")
    heading(doc, "7.13 Security and Privacy Discussion")
    p(doc, "Federated training reduces the intended need to centralize regional records, but differential privacy, secure aggregation, and a formal privacy budget are not implemented.")
    heading(doc, "7.14 Limitations")
    p(doc, "Synthetic data, imbalance, bounded local execution, distance-based routing, absent formal privacy controls, and unmeasured production capacity define the operating limits.")
    heading(doc, "7.15 Objective-to-Result Mapping")
    p(doc, "The project achieves the stated ingestion, feature, federated model, artifact, map, routing, demonstration, and validation objectives, while the evaluation records which objectives are demonstrated and which production extensions remain future work.")
    heading(doc, "7.16 Summary")
    p(doc, "The evaluation supports the project as a complete and traceable B.Tech prototype with meaningful current evidence and explicit boundaries on generalization and deployment.")
    chapter(doc, 8, "Conclusion and Future Enhancements")
    heading(doc, "8.1 Introduction")
    p(doc, "This chapter summarizes the completed implementation, findings, practical significance, limitations, and future research direction.")
    heading(doc, "8.2 Summary of the Work")
    p(doc, "FedRouteAI demonstrates a complete and traceable traffic intelligence pipeline. Its contribution is the integration of federated tabular learning, causal traffic features, historical memory, a canonical directed road network, live ingestion, model persistence, dynamic mapping, and route-bound demonstrations. The documented metrics and limitations show that the prototype is suitable for academic evaluation but not unattended safety-critical operation.")
    heading(doc, "8.3 Objectives Achieved")
    p(doc, "The completed system ingests traffic observations, associates them with a canonical road network, constructs label-free Geo V2 features, runs a frozen federated MLP, persists predictions, presents live state on a React-Leaflet map, and calculates directed shortest routes. It also provides a route-bound demonstration that keeps controlled traffic behavior separate from model output.")
    heading(doc, "8.4 Major Contributions")
    p(doc, "The major contributions are the ordered 23-feature causal contract, eight-region federated training workflow, versioned OSM/PostGIS network with 2,968 segments and 11,259 directed transitions, integrated ingestion-to-map pipeline, and explicit evidence boundaries for demonstrations, predictions, and routing.")
    heading(doc, "8.5 Experimental Findings")
    p(doc, "The frozen artifact records validation macro F1 of 0.3042, test macro F1 of 0.3200, event-balanced macro F1 of 0.4459, anomaly recall of 0.3444, anomaly precision of 0.2093, and normal false-positive rate of 0.0031. Overall accuracy is high because normal traffic dominates the dataset, while diversion and construction remain difficult minority classes.")
    heading(doc, "8.6 Practical Significance")
    p(doc, "The project demonstrates how a current model artifact, spatial database, federated workflow, service architecture, live map, and route inspector can be brought together for academic evaluation without overstating the evidence. Its practical value is the traceable prototype and the foundation it provides for measured traffic data and stronger operational controls.")
    heading(doc, "8.7 Current Limitations")
    p(doc, "The documented dataset is geographically grounded but synthetic, minority-event performance remains limited, and the system is not approved for unattended safety-critical operation. Formal differential privacy, secure aggregation, production queueing, cloud orchestration, and learned traffic-aware route costs are not implemented.")
    heading(doc, "8.8 Future Enhancements")
    add_paragraphs(doc, [
        "Collect measured GPS traffic across seasons and cities and evaluate transfer beyond the current synthetic network.",
        "Improve minority-event sampling and event-specific calibration, especially for diversion and construction.",
        "Add formal differential privacy, secure aggregation, and auditable privacy accounting.",
        "Develop traffic-aware route costs only after prediction reliability is sufficient for operational use.",
        "Move ingestion and replay to queue-backed services and evaluate distributed deployment.",
        "Study graph neural networks as a future extension for learned spatial reasoning.",
    ])
    heading(doc, "8.9 Scope for Future Research")
    p(doc, "Future research should evaluate measured traffic across seasons and cities, improve minority-event sampling and calibration, add formal privacy mechanisms, study traffic-aware route costs, move ingestion to queue-backed services, and investigate graph-based spatial models after the current baseline is preserved.")
    heading(doc, "8.10 Final Conclusion")
    p(doc, "FedRouteAI is therefore best understood as a complete and academically honest local prototype: it demonstrates how federated learning, causal traffic features, spatial infrastructure, live services, and user-facing route inspection can be integrated while keeping unverified production and safety claims outside the project scope.")
    consolidated_appendices(doc)
    doc.add_page_break()
    heading(doc, "REFERENCES", level=1)
    refs = [
        "[1] M. Abadi et al., \"Deep Learning with Differential Privacy,\" Proceedings of ACM CCS, pp. 308-318, 2016.",
        "[2] D. J. Beutel et al., \"Flower: A Friendly Federated Learning Research Framework,\" arXiv:2007.14390, 2020.",
        "[3] C. M. Bishop, Pattern Recognition and Machine Learning. Springer, 2006.",
        "[4] C. Chen et al., \"A Survey on Spatial-Temporal Data Mining for ITS,\" IEEE International Conference on Big Data, 2016.",
        "[5] E. W. Dijkstra, \"A Note on Two Problems in Connexion with Graphs,\" Numerische Mathematik, vol. 1, pp. 269-271, 1959.",
        "[6] C. Dwork and A. Roth, \"The Algorithmic Foundations of Differential Privacy,\" Foundations and Trends in Theoretical Computer Science, vol. 9, pp. 211-407, 2014.",
        "[7] I. El Manaa et al., \"Road Traffic Anomaly Detection: A Survey,\" Digital Technologies and Applications, Springer, pp. 772-781, 2022.",
        "[8] M. Gao et al., \"Anomaly Traffic Detection in IoT Security Using Graph Neural Networks,\" Journal of Information Security and Applications, vol. 76, 2023.",
        "[9] I. Goodfellow, Y. Bengio, and A. Courville, Deep Learning. MIT Press, 2016.",
        "[10] X. Han, \"Traffic Incident Detection: A Deep Learning Framework,\" IEEE Mobile Data Management, pp. 379-380, 2019.",
        "[11] D. Hendrycks and K. Gimpel, \"A Baseline for Detecting Misclassified and Out-of-Distribution Examples in Neural Networks,\" ICLR, 2017.",
        "[12] P. Kairouz et al., \"Advances and Open Problems in Federated Learning,\" Foundations and Trends in Machine Learning, vol. 14, pp. 1-210, 2021.",
        "[13] L. U. Khan et al., \"Federated Learning for Edge Networks: Resource Optimization and Incentive Mechanism,\" IEEE Communications Magazine, vol. 58, pp. 88-93, 2020.",
        "[14] X. Li et al., \"Deep Representation Learning for Trajectory Similarity Computation,\" IEEE ICDE, pp. 617-628, 2018.",
        "[15] Y. Liu et al., \"Privacy-Preserving Traffic Flow Prediction: A Federated Learning Approach,\" IEEE Internet of Things Journal, vol. 7, pp. 7751-7763, 2020.",
        "[16] Z. Lu et al., \"Federated Learning With Non-IID Data: A Survey,\" IEEE Internet of Things Journal, vol. 11, pp. 19188-19209, 2024.",
        "[17] H. B. McMahan et al., \"Communication-Efficient Learning of Deep Networks from Decentralized Data,\" Proceedings of AISTATS, pp. 1273-1282, 2017.",
        "[18] A. Paszke et al., \"PyTorch: An Imperative Style, High-Performance Deep Learning Library,\" NeurIPS, 2019.",
        "[19] J. Raiyn and T. Toledo, \"Real-Time Road Traffic Anomaly Detection,\" Journal of Transportation Technologies, vol. 4, pp. 256-266, 2014.",
        "[20] R. Shokri and V. Shmatikov, \"Privacy-Preserving Deep Learning,\" Annual Allerton Conference, pp. 909-910, 2015.",
        "[21] H. Su et al., \"A Survey of Trajectory Distance Measures and Performance Evaluation,\" VLDB Journal, vol. 29, pp. 3-32, 2019.",
        "[22] X. Wang et al., \"Convergence of Edge Computing and Deep Learning: A Comprehensive Survey,\" IEEE Communications Surveys and Tutorials, vol. 22, pp. 869-904, 2020.",
        "[23] K. Wei et al., \"Federated Learning With Differential Privacy: Algorithms and Performance Analysis,\" IEEE Transactions on Information Forensics and Security, vol. 15, pp. 3454-3469, 2020.",
        "[24] J. Wu et al., \"Topology-Aware Federated Learning in Edge Computing: A Comprehensive Survey,\" ACM Computing Surveys, vol. 56, pp. 1-41, 2024.",
        "[25] G. Yang et al., \"Anomaly Detection for Spatiotemporal Data in Action,\" ACM SIGKDD, pp. 4844-4845, 2022.",
        "[26] L. Yuan and D. Chen, \"Adaptive Federated Learning with Non-IID Data,\" AHPCAI, SPIE, 2024.",
        "[27] R. Zhang et al., \"A Survey on Federated Learning in Intelligent Transportation Systems,\" IEEE Transactions on Intelligent Vehicles, vol. 10, pp. 3043-3059, 2025.",
        "[28] Y. Zheng, \"Trajectory Data Mining: An Overview,\" ACM Transactions on Intelligent Systems and Technology, vol. 6, pp. 1-41, 2015.",
        "[29] Z. Zhou et al., \"Edge Intelligence: Paving the Last Mile of Artificial Intelligence With Edge Computing,\" Proceedings of the IEEE, vol. 107, pp. 1738-1762, 2019.",
        "[30] OpenStreetMap Contributors, \"OpenStreetMap,\" https://www.openstreetmap.org/, accessed 2026.",
        "[31] PostGIS Project Steering Committee, \"PostGIS Documentation,\" https://postgis.net/documentation/, accessed 2026.",
        "[32] FastAPI Documentation, https://fastapi.tiangolo.com/, accessed 2026.",
        "[33] React and Leaflet Documentation, https://react.dev/ and https://leafletjs.com/, accessed 2026.",
        "[34] FedRouteAI project technical sources: backend, frontend, tests, manifests, network loader, and frozen artifact metadata, accessed 2026.",
    ]
    for ref in refs:
        reference_para = p(doc, ref, indent=False, after=6)
        reference_para.paragraph_format.line_spacing = 1.0


def main_content(doc: Document) -> None:
    """Build the final report with substantive, reader-oriented sections."""
    chapter(doc, 1, "Introduction")
    heading(doc, "1.1 Introduction"); p(doc, "FedRouteAI is an end-to-end traffic intelligence prototype for detecting temporary road conditions from GPS-derived traffic behavior and supporting route inspection. It combines an OSM/PostGIS directed network, live telemetry aggregation, historical traffic memory, a causal 23-feature Geo V2 contract, an eight-client federated MLP, and a React-Leaflet map.")
    chapter1_expansion(doc)

    chapter(doc, 2, "Literature Survey")
    heading(doc, "2.1 Introduction"); p(doc, "This chapter reviews the technical fields that support FedRouteAI and identifies the integration gap addressed by the project.")
    sections = [
        ("2.2 Intelligent Transportation Systems", "Intelligent Transportation Systems combine sensing, communication, computation, and decision support for transportation operations. A traffic-intelligence system must convert observations into road-level state before analysis can be useful."),
        ("2.3 GPS-Based Traffic Analysis", "GPS trajectories provide broad movement coverage, but raw positions require timestamp normalization, segment association, and aggregation. The project keeps raw observations, current segment state, and model-ready features distinct."),
        ("2.4 Traffic Anomaly and Event Detection", "Anomaly detection compares current speed, flow, occupancy, or travel behavior against normal patterns. FedRouteAI combines interpretable baseline deviations with supervised event classification and retains a rule-based fallback for cold-start conditions."),
        ("2.5 Federated Learning for Distributed Traffic Intelligence", "Federated learning is relevant when regional records should remain with their logical owners. Eight regional clients train local models and send parameter updates rather than raw trajectories [12], [17]."),
        ("2.6 Federated Averaging and Adaptive Aggregation", "FedAvg combines continuous model parameters using client contributions. The project's adaptive workflow also records bounded quality, rarity, reliability, and relevance factors while preserving a reviewable aggregation process [16], [17]."),
        ("2.7 Neural Networks for Traffic Classification", "A multilayer perceptron is appropriate for a fixed tabular vector. The current GeoV2MLP maps 23 ordered values through 64 and 32 hidden units to eight output classes, while XGBoost remains a centralized comparison baseline."),
        ("2.8 Historical and Spatial Traffic Modeling", "Current traffic becomes meaningful when compared with normal baselines, strictly prior windows, trends, persistence, and directed-neighbor state. These temporal and spatial signals address limitations of single-snapshot classification."),
        ("2.9 OpenStreetMap, PostGIS and Road-Network Representation", "OpenStreetMap supplies geometry and road attributes; PostGIS stores the versioned canonical network and supports spatial access. The network is shared by matching, features, map rendering, and routing [30], [31]."),
        ("2.10 Map Matching and Directed Routing", "Map matching associates observations with canonical segments. Directed transitions then constrain legal movement, allowing distance-weighted Dijkstra routing to return an ordered segment path and geometry."),
        ("2.11 Research Gap", "Existing work commonly treats traffic detection, federated learning, spatial storage, or routing separately. FedRouteAI addresses the engineering gap of integrating them under explicit data and artifact boundaries."),
        ("2.12 FedRouteAI Positioning", "The project is positioned as a reproducible college-scale integration of federated tabular learning, causal features, OSM/PostGIS topology, live services, map visualization, and route-bound demonstrations rather than as a claim of universal traffic accuracy."),
    ]
    grouped_sections(doc, sections)
    equation(doc, "2.1", r"w_global = sum_i (n_i / sum_j n_j) w_i", "This is the basic sample-weighted FedAvg relationship, where n_i is local sample count and w_i is the client parameter vector [17]. The implementation records additional bounded aggregation factors.")
    heading(doc, "2.13 Summary"); p(doc, "The literature supports the project's use of segment-level GPS aggregation, causal history, directed spatial context, federated MLP training, spatial persistence, and shortest-path routing.")

    chapter(doc, 3, "Requirement Analysis and Feasibility Study")
    heading(doc, "3.1 Introduction"); p(doc, "This chapter converts the current implementation into requirements and evaluates whether the proposed system can be operated and verified within the project scope.")
    heading(doc, "3.2 Problem Requirements"); p(doc, "The system must transform observations into segment traffic state, construct label-free Geo V2 features, apply the frozen classifier, serve independent prediction state, and support legal directed route inspection without treating scenario controls as labels.")
    table(doc, "Table 3.1: Functional Requirements", ["ID", "Requirement", "Verification"], [["FR-01", "Ingest and validate live observations", "API/integration tests"], ["FR-02", "Associate observations with canonical segments", "Network tests"], ["FR-03", "Construct Geo V2 features", "Contract tests"], ["FR-04", "Run frozen MLP inference", "Artifact tests"], ["FR-05", "Serve map and prediction state", "Frontend/API tests"], ["FR-06", "Calculate directed routes", "Routing tests"]])
    heading(doc, "3.3 Functional Requirements"); p(doc, "Functional behavior covers ingestion, segment association, aggregation, historical and spatial feature construction, frozen inference, prediction persistence, map presentation, route calculation, and controlled demonstrations. Each function has an API or service-level verification path.")
    heading(doc, "3.4 Non-Functional Requirements"); p(doc, "Correctness requires exact feature ordering and legal directed transitions. Traceability requires model, network, feature, source, run, and timestamp identities. Reliability requires clear handling of invalid input, unavailable evidence, stale state, and expired demonstrations. Maintainability requires the API-to-service-to-repository layering.")
    table(doc, "Table 3.2: Non-Functional Requirements", ["Property", "Requirement"], [["Correctness", "Exact feature and directed-network contracts"], ["Traceability", "Observable artifact, network, and run identity"], ["Honesty", "Scenario truth remains separate from prediction"], ["Reliability", "Explicit invalid and unavailable states"], ["Usability", "Map, route, and freshness inspection"], ["Maintainability", "One-directional application layering"]])
    heading(doc, "3.5 User Roles and System Actors"); p(doc, "Traffic operators inspect current state and routes; regional clients train on local partitions; model administrators review artifacts; researchers evaluate metrics and evidence; and project evaluators require reproducible operation and honest limitations.")
    heading(doc, "3.6 Data and Dataset Requirements"); p(doc, "Training data requires region, segment, timestamp, traffic aggregates, road context, historical values, and supervised targets. Runtime input must not contain targets, event names, scenario labels, vehicle identity, device identity, or severity.")
    heading(doc, "3.7 Model and Feature Requirements"); p(doc, "The model must accept exactly the 23 ordered features, produce eight class probabilities, use compatible scaling and metadata, and fail closed for incompatible artifacts or insufficient evidence. The model contract is versioned as history_spatial_strong.")
    heading(doc, "3.8 Database and Road-Network Requirements"); p(doc, "PostGIS must support canonical geometry, directed transitions, historical memory, append-only observations, current projections, prediction rows, and network identity. The active network contains 2,968 segments and 11,259 directed transitions.")
    heading(doc, "3.9 Software and Hardware Requirements"); p(doc, "The stack uses Python/FastAPI/SQLAlchemy/Alembic/PyTorch, PostgreSQL/PostGIS, Node.js/React/Vite/React Query/Leaflet, and Flower-compatible training components. CPU inference is supported; training benefits from GPU resources.")
    heading(doc, "3.10 Feasibility Study"); p(doc, "Technical feasibility is supported by the existing stack, cached OSM input, local PostGIS, and a frozen artifact. Operational feasibility is supported by local startup instructions, bounded demonstrations, and observable APIs. Economic feasibility follows from open-source components. Ethical feasibility depends on distinguishing synthetic data, controlled behavior, and model output.")
    heading(doc, "3.11 Privacy, Security and Ethical Considerations"); p(doc, "Regional training reduces the intended need to centralize raw records, but federated aggregation does not itself provide differential privacy, secure aggregation, or a formal privacy guarantee. Configured API keys and database secrets remain outside the report and source control.")
    heading(doc, "3.12 System Constraints"); p(doc, "Synthetic-data realism, class imbalance, exact 120-second cadence, fixed artifact compatibility, bounded local execution, browser rendering limits, and distance-based default routing define the operating envelope.")
    heading(doc, "3.13 Requirement Traceability"); p(doc, "Data requirements trace to the manifest and feature builder; model requirements trace to the schema and artifact store; network requirements trace to OSM normalization and PostGIS; runtime requirements trace to ingestion and persistence; and interface requirements trace to frontend tests and build evidence.")
    heading(doc, "3.14 Summary"); p(doc, "The requirements define a bounded and testable academic prototype whose feasibility follows from the current software, network, artifact, and evidence base.")

    chapter(doc, 4, "System Design and Architecture")
    heading(doc, "4.1 Introduction"); p(doc, "FedRouteAI uses explicit boundaries between regional training, runtime inference, canonical network services, persistence, routing, and presentation. API endpoints call services, services call repositories, and the frontend consumes backend-owned state.")
    heading(doc, "4.2 Overall System Architecture"); p(doc, "The system has a telemetry and spatial-state path, a Geo V2 inference path, a federated training and delivery path, and presentation and routing consumers. Training produces a versioned artifact; runtime observations become segment state, features, predictions, and map responses."); figure(doc, "4.1", "Overall System Architecture of FedRouteAI"); p(doc, "The architecture prevents the map or routing client from silently recreating model or database logic.")
    heading(doc, "4.3 Federated Learning Architecture"); p(doc, "Eight geographic clients train local copies of the MLP and return parameter arrays and scalar metadata. The server aggregates participating updates and distributes the next global state without requiring raw regional trajectories."); figure(doc, "4.2", "Federated Learning Architecture")
    heading(doc, "4.4 Regional Client Architecture"); p(doc, "A regional client loads its partition, aligns the ordered feature contract, trains locally, evaluates its update, and returns model tensors with sample metadata. The server owns round coordination and artifact promotion."); figure(doc, "4.3", "Regional Client Architecture")
    heading(doc, "4.5 End-to-End Data Flow"); p(doc, "Runtime processing validates telemetry, associates it with the canonical network, aggregates segment state, joins normal memory and causal history, constructs features, validates the artifact, performs inference, and persists the response. Routing is a separate directed-network branch."); figure(doc, "4.4", "End-to-End Data Pipeline")
    heading(doc, "4.6 Geo V2 Feature Construction"); p(doc, "The promoted history_spatial_strong contract combines current traffic, time encoding, road metadata, normal baselines, deviations, prior windows, trends, persistence, and directed-neighbor context. Forbidden label and identity fields are excluded."); figure(doc, "4.5", "Geo V2 Feature Pipeline")
    heading(doc, "4.7 Historical Traffic Memory"); p(doc, "Normal prehistory establishes baseline speed, variation, and vehicle count. The runtime reads strictly prior t-1, t-2, and t-3 windows at the documented cadence, preventing current-value leakage."); figure(doc, "4.6", "Historical Traffic Memory"); equation(doc, "4.1", r"r_speed = avg_speed_kmph / max(baseline_speed_kmph, epsilon)", "The protected ratio expresses current movement relative to normal history.")
    heading(doc, "4.8 OSM/PostGIS Road-Network Architecture"); p(doc, "Cached OSM data is normalized into versioned canonical segments and directed transitions. PostGIS stores geometry and metadata for matching, spatial context, map display, and route computation."); figure(doc, "4.7", "OSM/PostGIS Road-Network Architecture")
    heading(doc, "4.9 Directed Road Network and Transitions"); p(doc, "The graph preserves legal movement relationships. A visually adjacent segment is not necessarily traversable unless the directed transition exists."); figure(doc, "4.8", "Directed Road Network and Transitions")
    heading(doc, "4.10 Backend Service Architecture"); p(doc, "FastAPI endpoints remain thin. Services own business rules and orchestration, repositories own database access, SQLAlchemy models represent persistence, and Pydantic schemas define API contracts."); figure(doc, "4.9", "Backend Service Architecture")
    heading(doc, "4.11 Frontend Architecture"); p(doc, "React, React Query, and Leaflet compose network, traffic, vehicle, prediction, event, and route layers from backend responses. The browser does not reproduce inference or route search."); figure(doc, "4.10", "Frontend Architecture")
    heading(doc, "4.12 Directed Shortest-Path Routing"); p(doc, "The route service snaps endpoints, searches legal transitions with distance as the default cost, and returns ordered IDs, geometry, distance, and duration. Prediction coverage and explicit exclusions are separate inspection behaviors."); figure(doc, "4.11", "Directed Shortest-Path Routing")
    heading(doc, "4.13 Database Design"); p(doc, "The database separates network rows, transitions, observations, receipts, current projections, historical memory, predictions, and controlled-run state. Explicit identities preserve provenance across these stores.")
    heading(doc, "4.14 API Design"); p(doc, "Health, network, ingestion, snapshot, prediction, routing, and demonstration endpoints expose validated contracts while services retain domain rules.")
    heading(doc, "4.15 Label-Free Inference and Training/Runtime Separation"); p(doc, "Training targets exist only in supervised training and evaluation. Runtime receives the 23 permitted values, while scenario names, event IDs, vehicle IDs, severity, and ground truth remain outside the feature vector. A controlled route can alter traffic behavior without becoming a model label.")
    heading(doc, "4.16 Summary"); p(doc, "The design connects federated training, causal feature construction, frozen inference, spatial persistence, map presentation, and directed routing through explicit contracts.")

    chapter(doc, 5, "Implementation")
    heading(doc, "5.1 Introduction"); p(doc, "This chapter describes the implemented data, model, runtime, interface, and demonstration workflows.")
    heading(doc, "5.2 Development Environment and Project Structure"); p(doc, "The implementation separates API endpoints, services, repositories, schemas, models, ML features, training, frontend pages, and Geo V2 scripts. Python, PostgreSQL/PostGIS, PyTorch, React, Vite, React Query, and Leaflet form the primary development stack.")
    table(doc, "Table 5.1: Major Software Modules", ["Module", "Role"], [["app/api", "HTTP endpoints and validation"], ["app/services", "Business logic and workflow orchestration"], ["app/repositories", "Database and PostGIS access"], ["app/ml/geo_v2", "Features, artifact validation, and inference"], ["frontend", "Map, routes, live state, and demonstrations"], ["scripts/geo_v2", "Network, data, replay, and validation workflows"]])
    heading(doc, "5.3 Dataset Preparation and Regional Partitioning"); p(doc, "The Geo V2 data workflow records network identity, time configuration, telemetry, feature windows, scenarios, and regional partitions. Eight regions provide non-identical local datasets for federated training; scenario metadata remains separate from model input.")
    heading(doc, "5.4 Road-Segment Association and Traffic Aggregation"); p(doc, "Map-matched observations use geometric projection and trajectory continuity, while trusted Geo V2 records validate canonical segment IDs. Aggregation produces speed, variation, count, occupancy, flow, and stopped fraction for each segment and tick.")
    heading(doc, "5.5 Historical Traffic Memory"); p(doc, "Normal prehistory supplies baseline rows. Shifted prior windows, ratios, trends, and persistence are constructed causally so the current state cannot explain itself through future or target information.")
    figure(doc, "5.1", "Live GPS Ingestion Pipeline")
    heading(doc, "5.6 Geo V2 Feature Construction"); p(doc, "The builder checks required columns, cadence, baseline availability, finite values, and forbidden target-related tokens before producing deterministic features.")
    heading(doc, "5.7 Exact 23-Feature Contract"); p(doc, "The ordered contract contains 23 values under history_spatial_strong: current traffic, cyclical time, road metadata, normal baselines, deviations, prior means, trends, low-speed persistence, and neighbor_speed_delta.")
    heading(doc, "5.8 GeoV2MLP Model Implementation"); p(doc, "The frozen GeoV2MLP uses the current 23 -> 64 -> 32 -> 8 architecture, normalization, ReLU, dropout during training, and LogSoftmax for eight output classes. The model store validates the scaler, feature order, network identity, and tensor metadata.")
    heading(doc, "5.9 Local Client Training"); p(doc, "Each client aligns its regional data, initializes from global parameters, performs local optimization, evaluates the update, and returns parameters and scalar metadata rather than raw GPS rows.")
    heading(doc, "5.10 Federated Model Aggregation"); p(doc, "The training workflow aggregates client tensors through its FedAvg-family strategy and records bounded adaptive weighting, participation, round history, and provenance.")
    heading(doc, "5.11 Global Model Selection and Frozen Artifact Deployment"); p(doc, "Validation selected round 45 from the recorded run. The promoted artifact retains the feature version, network version, scaler, model identity, selected round, and evaluation receipt, and is loaded in evaluation mode without retraining during demonstrations.")
    table(doc, "Table 5.2: Federated Client and Artifact Configuration", ["Property", "Current implementation"], [["Clients", "8 regional clients"], ["Feature version", "geo-v2-history_spatial_strong-23-v2"], ["Model", "GeoV2MLP, 23 -> 64 -> 32 -> 8"], ["Maximum rounds", "50"], ["Selected checkpoint", "Round 45"], ["Local epochs", "2"], ["Seed", "42"]])
    heading(doc, "5.12 Label-Free Runtime Inference"); p(doc, "Runtime input is the validated 23-feature vector. Labels, scenario names, event IDs, vehicle IDs, and severity are absent. Missing evidence and incompatible metadata produce an unavailable or rejected state instead of a guessed class.")
    heading(doc, "5.13 Live GPS Ingestion and Prediction Persistence"); p(doc, "Trusted batches carry source, run, batch, and observation identity. The service validates receipts, persists append-only history, updates current state, constructs features, runs inference, and stores predictions separately for snapshot retrieval.")
    heading(doc, "5.14 Dynamic Traffic Map and Moving Vehicle Visualization"); p(doc, "The React-Leaflet map presents geometry, traffic, predictions, events, vehicles, freshness, routes, and selected-road inspection as independent layers. Interpolated browser movement improves continuity but is not written back as telemetry.")
    heading(doc, "5.15 Route Calculation and Alternate Route Inspection"); p(doc, "The backend snaps endpoints and returns legal directed paths with ordered segment IDs, geometry, distance, and duration. The default cost remains distance-based; exclusions and prediction coverage are explicit inspection options.")
    heading(doc, "5.16 Route-Bound Controlled Demonstrations"); p(doc, "The demonstration validates a route of approximately 1.5 km or more and binds vehicles to its ordered segments. Normal Traffic Demonstration provides controlled baseline behavior. Congestion Demonstration applies controlled congestion-like behavior. Accident Demonstration applies a controlled accident-like disturbance. In every case, the scenario is traffic behavior only, not ground truth, and scenario metadata stays outside model features.")
    heading(doc, "5.17 API and Frontend-Backend Integration"); p(doc, "Typed API clients, React Query, scoped run identities, polling, freshness states, and Leaflet layers connect the browser to backend-owned data. Pydantic contracts and service rules validate routes, runs, snapshots, and demonstrations.")
    heading(doc, "5.18 Implementation Summary"); p(doc, "The implementation connects data preparation, regional learning, artifact governance, label-free inference, ingestion, persistence, visualization, routing, and controlled operation without collapsing their responsibilities.")
    p(doc, "Application screenshot register: verified application screenshots are not available in the current workspace. Future captures may be inserted at the relevant locations without changing technical figure numbering; no empty boxes are used in this report.", indent=False, size=10)

    chapter(doc, 6, "Testing and Validation")
    heading(doc, "6.1 Introduction"); p(doc, "Testing evaluates pure services, API contracts, artifacts, databases, routing, frontend interaction, builds, and integrated runtime paths.")
    heading(doc, "6.2 Testing Objectives and Strategy"); p(doc, "The objectives are to verify transformation rules, reject invalid contracts, preserve data boundaries, validate model compatibility, and exercise the complete ingestion-to-map workflow. Fixture-free tests are used where a live database is unnecessary.")
    heading(doc, "6.3 Test Environment"); p(doc, "The evidence combines the Python backend suite, focused Traffic Map tests, artifact files, network metadata, and the frontend production build. Database-backed checks use the configured project test approach.")
    heading(doc, "6.4 Functional and Service Testing"); p(doc, "Functional tests cover map matching, event logic, historical aggregation, adaptive weighting, graph reasoning, feature construction, route rules, ingestion, demonstrations, and API behavior. The verified backend suite contains 117 passing tests.")
    heading(doc, "6.5 Data and Feature Contract Validation"); p(doc, "Contract checks verify exact column names and order, 120-second cadence, shifted history, normal prehistory, directed-neighbor construction, finite values, and rejection of target or identity tokens.")
    heading(doc, "6.6 Model Artifact and Federated Learning Validation"); p(doc, "Artifact checks validate the 23-feature schema, scaler ordering, model tensor shape, network identity, and provenance. Federated checks record eight clients, two local epochs, 50 maximum rounds, adaptive aggregation metadata, and selected round 45.")
    heading(doc, "6.7 Runtime Inference and API Testing"); p(doc, "Inference and API tests verify label-free input, persisted class and confidence, unavailable states, metadata compatibility, request bounds, route prerequisites, enum restrictions, and response shape.")
    heading(doc, "6.8 Database and Routing Testing"); p(doc, "Database tests verify receipts, append-only observations, current segment state, historical relationships, prediction rows, network metadata, and scoped run state. Routing tests verify transitions, ordered segment IDs, distance, geometry, snapping, and explicit exclusions.")
    heading(doc, "6.9 Frontend and Integration Testing"); p(doc, "Frontend tests cover live polling, stale and offline state, layers, vehicles, route selection, prediction metadata, demonstration creation, reset behavior, and route prerequisites. The focused Traffic Map suite contains 17 passing tests and the production build passes.")
    heading(doc, "6.10 Performance Testing"); p(doc, "The recorded warmed single-row CPU inference measurement averages approximately 0.414 ms over 1,000 calls. This is an isolated model-call result, not an end-to-end capacity claim.")
    heading(doc, "6.11 Model Validation Results"); p(doc, "The frozen artifact reports validation macro F1 0.3042, test accuracy 0.9952, test macro F1 0.3200, event-balanced macro F1 0.4459, anomaly recall 0.3444, anomaly precision 0.2093, and normal false-positive rate 0.0031."); figure(doc, "6.1", "Model Validation Results")
    heading(doc, "6.12 Confusion Matrix Analysis"); p(doc, "The confusion matrix shows that accuracy is dominated by Normal traffic while several minority classes remain difficult. Macro and event-balanced metrics therefore provide necessary context."); figure(doc, "6.2", "Confusion Matrix")
    heading(doc, "6.13 Prediction and System Testing Results"); p(doc, "Prediction persistence, scoped snapshots, route responses, and controlled demonstrations remain separate from the classifier's independent output. The evidence supports implemented behavior but not city-wide predictive validity.")
    heading(doc, "6.14 Test Case Design and Verification Summary"); p(doc, "Test cases include valid and invalid requests, missing history, incompatible artifacts, directed route errors, idempotent ingestion, stale snapshots, independent frontend layers, and demonstration lifecycle.")
    table(doc, "Table 6.1: Verification Summary", ["Verification", "Result"], [["Backend suite", "117 passed"], ["Traffic Map tests", "17 passed"], ["Frontend build", "Passed"], ["Python compilation/import", "Passed"], ["Artifact validation", "Passed"], ["Network normalization", "2,968 segments; 11,259 transitions"]])
    table(doc, "Table 6.2: Frozen Model Results", ["Metric", "Value"], [["Validation macro F1", "0.3042"], ["Test accuracy", "0.9952"], ["Test macro F1", "0.3200"], ["Event-balanced macro F1", "0.4459"], ["Anomaly recall", "0.3444"], ["Anomaly precision", "0.2093"], ["Normal FPR", "0.0031"]])
    figure(doc, "6.3", "Testing Evidence")
    heading(doc, "6.15 Summary"); p(doc, "Testing demonstrates that the current contracts and workflows are implemented and inspectable while retaining clear limits on generalization, privacy, and production capacity.")

    chapter(doc, 7, "System Evaluation and Discussion")
    heading(doc, "7.1 Introduction"); p(doc, "This chapter interprets model results together with federated behavior, feature design, runtime operation, visualization, routing, deployment, and limitations.")
    heading(doc, "7.2 Model Performance Evaluation"); p(doc, "High accuracy is dominated by Normal traffic. Macro F1, event-balanced F1, anomaly recall and precision, and normal false-positive rate expose the weaker minority-class behavior. The model is an academic decision-support baseline, not an unattended detector.")
    heading(doc, "7.3 Federated Learning Evaluation"); p(doc, "The workflow demonstrates eight regional clients, local training, parameter aggregation, validation-based selection, and frozen artifact promotion. It does not claim differential privacy or secure aggregation.")
    heading(doc, "7.4 Geo V2, Historical and Spatial Feature Evaluation"); p(doc, "The 23-feature history_spatial_strong contract combines current values with baselines, strictly prior history, trends, persistence, and directed-neighbor context. This design is more informative than a single snapshot while maintaining label-free runtime inference.")
    heading(doc, "7.5 Runtime Inference Evaluation"); p(doc, "The model store fails closed for incompatible feature, scaler, model, or network metadata. Unavailable evidence remains distinct from a confident Normal result.")
    heading(doc, "7.6 Live Map and Routing Evaluation"); p(doc, "The map exposes independent traffic, prediction, vehicle, event, freshness, and route state. Directed distance-based routing returns legal ordered paths; predictions do not silently rewrite default route cost.")
    heading(doc, "7.7 Controlled Demonstration Evaluation"); p(doc, "Normal, Congestion, and Accident controls exercise repeatable route-bound behavior. They demonstrate orchestration and observation flow, not ground-truth classification.")
    heading(doc, "7.8 Deployment and Performance Discussion"); p(doc, "The local deployment combines PostgreSQL/PostGIS, FastAPI, Vite, and the model artifact. The measured 0.414 ms model-call result excludes database, feature, HTTP, browser, and end-to-end load behavior."); figure(doc, "7.1", "Local Deployment Architecture")
    heading(doc, "7.9 Security and Privacy Discussion"); p(doc, "Federated regional processing supports data minimization, but formal differential privacy, secure aggregation, and a privacy budget are not implemented. Secrets remain configuration concerns.")
    heading(doc, "7.10 Limitations"); p(doc, "Synthetic data, class imbalance, bounded local execution, distance-based routing, absent formal privacy mechanisms, and unmeasured production capacity limit the claims supported by the current evidence.")
    heading(doc, "7.11 Objective-to-Result Mapping"); p(doc, "The implementation achieves ingestion, causal feature construction, federated model training, artifact deployment, map presentation, routing, demonstrations, and validation objectives. Production-scale operations and measured real-world transfer remain future work.")
    heading(doc, "7.12 Summary"); p(doc, "The evaluation supports FedRouteAI as a complete and traceable B.Tech prototype with useful current evidence and explicit boundaries on safety and generalization.")

    chapter(doc, 8, "Conclusion and Future Enhancements")
    heading(doc, "8.1 Introduction"); p(doc, "This chapter summarizes the completed system, findings, significance, limitations, and future direction.")
    heading(doc, "8.2 Summary of the Work"); p(doc, "FedRouteAI integrates federated tabular learning, causal traffic features, historical memory, a versioned OSM/PostGIS network, live ingestion, frozen inference, dynamic mapping, and directed route inspection.")
    heading(doc, "8.3 Objectives Achieved"); p(doc, "The system ingests observations, associates segments, constructs label-free Geo V2 features, loads the frozen MLP, persists predictions, presents live state, calculates routes, and runs controlled demonstrations.")
    heading(doc, "8.4 Major Contributions"); p(doc, "The main contributions are the ordered 23-feature contract, eight-region training workflow, canonical directed network, integrated ingestion-to-map path, and explicit evidence boundaries.")
    heading(doc, "8.5 Experimental Findings"); p(doc, "The recorded artifact achieves test accuracy 0.9952, test macro F1 0.3200, event-balanced macro F1 0.4459, anomaly recall 0.3444, anomaly precision 0.2093, and normal FPR 0.0031. These values must be interpreted with class imbalance.")
    heading(doc, "8.6 Practical Significance"); p(doc, "The project demonstrates a traceable way to combine federated learning, spatial infrastructure, service boundaries, and map-based decision support without overstating controlled behavior as measured reality.")
    heading(doc, "8.7 Current Limitations"); p(doc, "The dataset is geographically grounded but synthetic; minority-event performance is limited; formal privacy controls, queue-backed production operation, and learned traffic-aware costs are not implemented.")
    heading(doc, "8.8 Future Enhancements"); p(doc, "Future work includes measured multi-season data, class calibration, formal privacy mechanisms, queue-backed ingestion, distributed deployment, and graph-based spatial models.")
    heading(doc, "8.9 Scope for Future Research"); p(doc, "Further research should evaluate cross-city transfer, event-specific calibration, stronger federated strategies, privacy accounting, traffic-aware routing, and graph neural networks while preserving the current baseline.")
    heading(doc, "8.10 Final Conclusion"); p(doc, "FedRouteAI is a complete and academically honest local prototype showing how federated learning, causal traffic features, spatial services, live APIs, and route inspection can be integrated within a verifiable scope.")
    consolidated_appendices(doc)
    doc.add_page_break(); heading(doc, "REFERENCES", level=1)
    refs = [
        "[1] M. Abadi et al., \"Deep Learning with Differential Privacy,\" Proceedings of ACM CCS, pp. 308-318, 2016.", "[2] D. J. Beutel et al., \"Flower: A Friendly Federated Learning Research Framework,\" arXiv:2007.14390, 2020.", "[3] C. M. Bishop, Pattern Recognition and Machine Learning. Springer, 2006.", "[4] C. Chen et al., \"A Survey on Spatial-Temporal Data Mining for ITS,\" IEEE International Conference on Big Data, 2016.", "[5] E. W. Dijkstra, \"A Note on Two Problems in Connexion with Graphs,\" Numerische Mathematik, vol. 1, pp. 269-271, 1959.", "[6] D. Dwork and A. Roth, \"The Algorithmic Foundations of Differential Privacy,\" Foundations and Trends, vol. 9, pp. 211-407, 2014.", "[7] I. El Manaa et al., \"Road Traffic Anomaly Detection: A Survey,\" Digital Technologies and Applications, 2022.", "[8] M. Gao et al., \"Anomaly Traffic Detection in IoT Security Using Graph Neural Networks,\" Journal of Information Security and Applications, 2023.", "[9] I. Goodfellow, Y. Bengio, and A. Courville, Deep Learning. MIT Press, 2016.", "[10] X. Han, \"Traffic Incident Detection: A Deep Learning Framework,\" IEEE Mobile Data Management, 2019.", "[11] D. Hendrycks and K. Gimpel, \"A Baseline for Detecting Misclassified and Out-of-Distribution Examples,\" ICLR, 2017.", "[12] P. Kairouz et al., \"Advances and Open Problems in Federated Learning,\" Foundations and Trends in Machine Learning, 2021.", "[13] L. U. Khan et al., \"Federated Learning for Edge Networks,\" IEEE Communications Magazine, 2020.", "[14] X. Li et al., \"Deep Representation Learning for Trajectory Similarity Computation,\" IEEE ICDE, 2018.", "[15] Y. Liu et al., \"Privacy-Preserving Traffic Flow Prediction: A Federated Learning Approach,\" IEEE Internet of Things Journal, 2020.", "[16] Z. Lu et al., \"Federated Learning With Non-IID Data: A Survey,\" IEEE Internet of Things Journal, 2024.", "[17] H. B. McMahan et al., \"Communication-Efficient Learning of Deep Networks from Decentralized Data,\" AISTATS, 2017.", "[18] A. Paszke et al., \"PyTorch: An Imperative Style, High-Performance Deep Learning Library,\" NeurIPS, 2019.", "[19] J. Raiyn and T. Toledo, \"Real-Time Road Traffic Anomaly Detection,\" Journal of Transportation Technologies, 2014.", "[20] R. Shokri and V. Shmatikov, \"Privacy-Preserving Deep Learning,\" Annual Allerton Conference, 2015.", "[21] H. Su et al., \"A Survey of Trajectory Distance Measures and Performance Evaluation,\" VLDB Journal, 2019.", "[22] X. Wang et al., \"Convergence of Edge Computing and Deep Learning,\" IEEE Communications Surveys and Tutorials, 2020.", "[23] K. Wei et al., \"Federated Learning With Differential Privacy,\" IEEE TIFS, 2020.", "[24] J. Wu et al., \"Topology-Aware Federated Learning in Edge Computing,\" ACM Computing Surveys, 2024.", "[25] G. Yang et al., \"Anomaly Detection for Spatiotemporal Data in Action,\" ACM SIGKDD, 2022.", "[26] L. Yuan and D. Chen, \"Adaptive Federated Learning with Non-IID Data,\" AHPCAI, 2024.", "[27] R. Zhang et al., \"A Survey on Federated Learning in Intelligent Transportation Systems,\" IEEE Transactions on Intelligent Vehicles, 2025.", "[28] Y. Zheng, \"Trajectory Data Mining: An Overview,\" ACM TIST, 2015.", "[29] Z. Zhou et al., \"Edge Intelligence,\" Proceedings of the IEEE, 2019.", "[30] OpenStreetMap Contributors, \"OpenStreetMap,\" https://www.openstreetmap.org/, accessed 2026.", "[31] PostGIS Project Steering Committee, \"PostGIS Documentation,\" https://postgis.net/documentation/, accessed 2026.", "[32] FastAPI Documentation, https://fastapi.tiangolo.com/, accessed 2026.", "[33] React and Leaflet Documentation, https://react.dev/ and https://leafletjs.com/, accessed 2026.", "[34] FedRouteAI project technical sources: current backend, frontend, tests, manifests, network loader, and frozen artifact metadata, accessed 2026."]
    for ref in refs:
        reference_para = p(doc, ref, indent=False, after=4); reference_para.paragraph_format.line_spacing = 1.0


def main() -> None:
    doc = Document()
    configure_document(doc)
    front_matter(doc)
    lists(doc)
    start_main_numbering(doc)
    main_content(doc)
    doc.core_properties.title = TITLE
    doc.core_properties.subject = "B.Tech Major Project Report"
    doc.core_properties.author = "Moguloju Abhiram and Rajulapudi Rohith"
    doc.core_properties.comments = "Current technical report with verified figures and grouped page-oriented prose."
    doc.save(OUT)
    validate_report_package(OUT)
    print(OUT)


def validate_report_package(path: Path) -> None:
    """Fail generation when prohibited range headings or required figures drift."""
    with zipfile.ZipFile(path) as package:
        xml = package.read("word/document.xml").decode("utf-8")
    text = re.sub(r"<[^>]+>", " ", xml)
    text = re.sub(r"\s+", " ", text)
    if re.search(r"\b\d+\.\d+-\d+\.\d+\b", text):
        raise ValueError("Report contains a prohibited combined section heading")
    required = [
        "Figure 4.1 Overall System Architecture of FedRouteAI",
        "Figure 4.2 Federated Learning Architecture",
        "Figure 4.3 Regional Client Architecture",
        "Figure 4.4 End-to-End Data Pipeline",
        "Figure 4.5 Geo V2 Feature Pipeline",
        "Figure 4.6 Historical Traffic Memory",
        "Figure 4.7 OSM/PostGIS Road-Network Architecture",
        "Figure 4.8 Directed Road Network and Transitions",
        "Figure 4.9 Backend Service Architecture",
        "Figure 4.10 Frontend Architecture",
        "Figure 4.11 Directed Shortest-Path Routing",
        "Figure 5.1 Live GPS Ingestion Pipeline",
        "Figure 6.1 Model Validation Results",
        "Figure 6.2 Confusion Matrix",
        "Figure 6.3 Testing Evidence",
        "Figure 7.1 Local Deployment Architecture",
    ]
    missing = [caption for caption in required if caption not in text]
    if missing:
        raise ValueError(f"Missing canonical figure captions: {missing}")
    expected_screenshots = [
        "Application Screenshot 5.2 Dynamic Traffic Map",
        "Application Screenshot 5.3 Moving Vehicle Visualization",
        "Application Screenshot 5.4 Route-Bound Demonstration Flow",
        "Application Screenshot 5.5 Normal Traffic Demonstration",
        "Application Screenshot 5.6 Congestion Demonstration",
        "Application Screenshot 5.7 Accident Demonstration",
    ]
    missing_screenshots = [label for label in expected_screenshots if label not in text]
    if missing_screenshots:
        raise ValueError(f"Missing application screenshot entries: {missing_screenshots}")


if __name__ == "__main__":
    main()
