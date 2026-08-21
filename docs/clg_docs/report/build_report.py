from __future__ import annotations

from pathlib import Path
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "FedRouteAI_Major_Project_Report_FINAL.docx"

TITLE = "FedRouteAI: Adaptive Federated Learning for Resilient Edge-Based Traffic Anomaly Detection"
STUDENTS = [("MOGULOJU ABHIRAM", "23211A6774"), ("RAJULAPUDI ROHITH", "23211A67A0")]
GUIDE = "Mrs. S. Jyothsna"
DEPARTMENT = "Computer Science and Engineering (Data Science)"
COLLEGE = "B V RAJU INSTITUTE OF TECHNOLOGY"
ADDRESS = "Vishnupur, Narsapur, Medak, Telangana, India 502313"
MAIN_PAGE_STARTS: dict[int, int] = {
    1: 1,
    2: 4,
    3: 8,
    4: 12,
    5: 18,
    6: 26,
    7: 31,
    8: 35,
    9: 37,
    10: 55,
}
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
    "4.11": "fig_4_11_routing.png",
    "5.1": "fig_5_1_live_ingestion.png",
    "5.2": "fig_5_2_frozen_mlp.png",
    "6.1": "fig_6_1_model_validation.png",
    "6.2": "fig_6_2_confusion_matrix.png",
    "6.3": "fig_6_3_test_evidence.png",
    "7.1": "fig_7_1_deployment.png",
}


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "FFFFFF")
    tc_pr.append(shd)


def set_cell_text(cell, text: str, bold: bool = False, size: float = 10) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.bold = bold
    r.font.name = "Times New Roman"
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor(0, 0, 0)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


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
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
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
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
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

    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 12)):
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
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def figure(doc: Document, number: str, caption: str, height: float = 1.45) -> None:
    box = doc.add_paragraph()
    box.alignment = WD_ALIGN_PARAGRAPH.CENTER
    box.paragraph_format.first_line_indent = Inches(0)
    box.paragraph_format.space_before = Pt(6)
    box.paragraph_format.space_after = Pt(4)
    box.paragraph_format.line_spacing = 1.0
    image = ROOT.parent / "figures" / "png" / FIGURE_IMAGES[number] if number in FIGURE_IMAGES else None
    if image is not None and image.exists():
        run = box.add_run()
        run.add_picture(str(image), width=Inches(6.2))
    else:
        run = box.add_run(f"[INSERT FIGURE {number} HERE]\n\n\n\n\n\n\n\n\nFIGURE SPACE RESERVED")
        run.font.name = "Times New Roman"
        run.font.size = Pt(11)
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
    box.paragraph_format.line_spacing = 1.5
    box.paragraph_format.keep_with_next = True
    caption_para = p(doc, f"Figure {number}: {caption}", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=8, size=11)
    caption_para.paragraph_format.line_spacing = 1.0


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
    contents = [
        ("ABSTRACT", "v"), ("LIST OF FIGURES", "viii"), ("LIST OF TABLES", "ix"), ("LIST OF ABBREVIATIONS / SYMBOLS", "x"),
        ("1. INTRODUCTION", "01"), ("2. LITERATURE SURVEY", "08"), ("3. REQUIREMENT ANALYSIS AND FEASIBILITY STUDY", "15"),
        ("4. SYSTEM DESIGN AND ARCHITECTURE", "23"), ("5. IMPLEMENTATION", "37"), ("6. TESTING AND VALIDATION", "55"),
        ("7. DEPLOYMENT, SECURITY AND PERFORMANCE", "67"), ("8. CONCLUSION AND FUTURE ENHANCEMENTS", "76"), ("9. APPENDICES", "82"), ("10. REFERENCES", "94"),
    ]
    for item, page in contents:
        p(doc, f"{item:<62}{page}", indent=False, after=4, size=11)
    doc.add_page_break()
    p(doc, "LIST OF TABLES", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14, bold=True, size=14)
    tables = ["2.1 Related Approaches and FedRouteAI Position", "3.1 Functional Requirements", "3.2 Requirement Traceability", "3.3 Software and Hardware Requirements", "3.4 Additional Requirement Evidence", "4.1 Exact 23-Feature Geo V2 Contract", "4.2 Dataset and Runtime Data Separation", "4.3 Database and Network Statistics", "5.1 Major Software Modules", "5.2 Model Configuration", "5.3 Demonstration Controls", "5.4 Additional Implementation Evidence", "6.1 Test Categories", "6.2 Additional Validation Evidence", "7.1 Deployment and Performance Evidence", "9.1 Database and Network Evidence", "9.2 Evidence Register"]
    for item in tables: p(doc, f"Table {item}", indent=False, after=4, size=11)
    doc.add_page_break()
    p(doc, "LIST OF FIGURES", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14, bold=True, size=14)
    figs = [
        "4.1 Overall System Architecture of FedRouteAI", "4.2 Federated Learning Architecture", "4.3 Regional Client Architecture", "4.4 End-to-End Data Pipeline", "4.5 Geo V2 Feature Pipeline", "4.6 Historical Traffic Memory", "4.7 OSM/PostGIS Road-Network Architecture", "4.8 Directed Road Network and Transitions", "4.9 Backend Service Architecture", "4.10 Frontend Architecture", "4.11 Directed Shortest-Path Routing", "5.1 Live GPS Ingestion Pipeline", "5.2 Dynamic Traffic Map", "5.3 Moving Vehicle Visualization", "5.4 Route-Bound Demonstration Flow", "5.5 Normal Traffic Demonstration", "5.6 Congestion Demonstration", "5.7 Accident Demonstration", "6.1 Model Validation Results", "6.2 Confusion Matrix", "6.3 Testing Evidence", "7.1 Local Deployment Architecture",
    ]
    for i, item in enumerate(figs, 1): p(doc, f"Figure {item:<55}{'—'}", indent=False, after=3, size=11)
    doc.add_page_break()
    p(doc, "LIST OF ABBREVIATIONS / SYMBOLS", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14, bold=True, size=14)
    table(doc, "", ["Abbreviation / Symbol", "Meaning"], [["AI", "Artificial Intelligence"], ["API", "Application Programming Interface"], ["FL", "Federated Learning"], ["FedAvg", "Federated Averaging"], ["GPS", "Global Positioning System"], ["MLP", "Multilayer Perceptron"], ["OSM", "OpenStreetMap"], ["PostGIS", "PostgreSQL spatial database extension"], ["REST", "Representational State Transfer"], ["GIS", "Geographic Information System"], ["FPR", "False Positive Rate"], ["F1", "Harmonic mean of precision and recall"], ["V1 / V2", "Version 1 / Geo V2 system contracts"], ["km/h", "Kilometres per hour"], ["m", "Metres"]])


def start_main_numbering(doc: Document) -> None:
    return None


def add_paragraphs(doc: Document, paragraphs: list[str]) -> None:
    for text in paragraphs:
        p(doc, text)


def chapter1_expansion(doc: Document) -> None:
    heading(doc, "1.2 Background")
    add_paragraphs(doc, [
        "Traffic intelligence begins with the observation that a road segment is not static. Its average speed, dispersion of speeds, vehicle count, occupancy, flow, and stopped fraction vary with time of day, road type, weather, nearby activity, and the behavior of adjacent segments. A useful system therefore needs a reference for normal operation and a method for comparing the current state with that reference. FedRouteAI models the road segment as the unit of analysis because segment-level state can be joined to road geometry, historical memory, spatial neighbors, and route topology.",
        "GPS telemetry is attractive for this purpose because it can be produced by mobile devices, fleet systems, or controlled vehicle simulators. Raw positions alone are not sufficient for event classification. They must be associated with a canonical segment, aggregated into a consistent time interval, and interpreted with road metadata. The project follows this sequence and keeps the original telemetry, derived segment state, model features, predictions, and demonstration metadata conceptually separate.",
        "The current project contains two related but distinct data paths. The training and evaluation path uses geographically grounded synthetic data with event labels available for dataset construction and evaluation. The runtime path uses label-free telemetry and constructs only the features permitted by the frozen model contract. A controlled demonstration can intentionally change vehicle behavior, but its selected scenario is not passed as a model input and is not automatically treated as a prediction.",
    ])
    heading(doc, "1.3 Need for the Proposed System")
    add_paragraphs(doc, [
        "A simple map of GPS points does not tell an operator whether a slow road is experiencing an accident, recurring peak-hour congestion, or a normal low-speed residential condition. The distinction requires historical context and spatial reasoning. FedRouteAI addresses this need by comparing current traffic aggregates with normal baselines, recent prior windows, and neighboring road behavior while also incorporating road type, lanes, and maximum speed.",
        "A second need is organizational rather than purely algorithmic. Mobility records can be distributed across regions, companies, or administrative boundaries. Sending all raw trajectories to one training database may be undesirable even when the final model is centrally served. The regional-client design lets the project study model aggregation while preserving the conceptual boundary between local observations and global parameters. This is a system design decision, not a claim that the current prototype provides formal privacy guarantees.",
    ])
    heading(doc, "1.4 Contributions")
    add_paragraphs(doc, [
        "The first contribution is an end-to-end engineering pipeline. The project does not stop at a trained classifier; it connects network import, PostGIS persistence, live ingestion, segment state, causal feature construction, frozen inference, prediction persistence, API responses, map layers, and routing. This makes the system inspectable at each stage and enables integration testing across boundaries.",
        "The second contribution is the Geo V2 feature contract. It makes current traffic, historical baselines, temporal position, prior-window behavior, and directed-neighbor evidence explicit. The contract is ordered and versioned, and the runtime model store validates it before inference. This reduces the risk that a model artifact is loaded with an incompatible feature order.",
        "The third contribution is an honest demonstration workflow. A user selects a route, chooses a controlled traffic behavior, and observes telemetry and model outputs independently. The interface reports route coverage and abnormal predictions only where predictions exist. This allows the system to demonstrate a realistic pipeline without claiming that a clicked Accident scenario is proof of accident classification.",
    ])
    heading(doc, "1.5 Scope")
    add_paragraphs(doc, [
        "The scope includes GPS-based road-event classification, regional MLP training, model aggregation, causal feature engineering, OSM/PostGIS network representation, live and controlled telemetry, dynamic map visualization, and directed shortest-path inspection. The scope does not include an external navigation service, a production cloud deployment, a CCTV pipeline, a learned graph neural network, or a formal privacy protocol.",
    ])
    heading(doc, "1.6 Limitations")
    add_paragraphs(doc, [
        "The principal limitation is data realism. The documented Geo V2 experiments use geographically grounded synthetic traffic rather than a continuously collected measured traffic feed. This is appropriate for controlled validation of the pipeline but does not establish city-wide operational accuracy. The class distribution also makes overall accuracy less informative than event-balanced metrics, per-class recall, and false-positive analysis.",
        "The routing subsystem calculates directed shortest paths and supports explicit inspection or exclusions; it should not be described as a learned traffic-aware optimizer. Likewise, federated training demonstrates regional parameter aggregation but does not by itself guarantee privacy. These boundaries are retained in the report so that the project claims remain aligned with the implementation.",
    ])
    heading(doc, "1.7 Organization of the Report")
    p(doc, "Chapter 1 establishes the problem and scope. Chapter 2 surveys related technical areas. Chapter 3 records requirements and feasibility. Chapter 4 explains the architecture and exact feature contract. Chapter 5 describes implementation behavior. Chapter 6 presents testing and model evidence. Chapter 7 discusses deployment, security, performance, and limitations. Chapter 8 summarizes achievements and future work. Chapter 9 provides reproducibility and evidence appendices, and Chapter 10 lists the references used in the report.")


def chapter2_expansion(doc: Document) -> None:
    for title, text in [
        ("2.2 GPS-Based Traffic Analysis", "GPS-based traffic analysis transforms individual position and speed observations into road-level measurements. The transformation usually requires map matching, timestamp normalization, aggregation, and a treatment for missing observations. FedRouteAI uses this general pattern but adds a distinction between raw GPS observations, segment-level current state, and model-ready features. The MLP does not consume latitude, longitude, or vehicle identity directly; those fields are used upstream for association and aggregation."),
        ("2.3 Traffic Anomaly Detection", "Traffic anomaly detection can be formulated as deviation from a baseline, classification into event types, or detection of an out-of-distribution state. Baseline methods are interpretable but depend on a reliable definition of normal. Classification methods can separate multiple event types but are sensitive to class imbalance and dataset shift. The project combines both ideas: normal-only historical references provide context, while the supervised federated MLP provides the learned classification path."),
        ("2.4 Traffic Event Classification", "Temporary events have different behavioral signatures. Congestion may reduce speed while increasing vehicle count; an accident-like disturbance may create a sharper local disruption; construction or a closure may produce persistent or highly asymmetric effects. A model must learn these patterns without receiving the event name as an input. The Geo V2 feature builder explicitly rejects event and scenario tokens, which keeps the inference contract causal and label-free."),
        ("2.5 Federated Learning", "Federated learning is relevant when observations are naturally distributed. In a traffic setting, a regional client may represent a geographic area, a fleet operator, or an edge installation. The client can build local examples and train a local MLP, while the server receives model updates. The resulting global model can benefit from multiple regions without requiring one raw table containing every trajectory. The project uses this as an architectural and experimental principle."),
        ("2.6 FedAvg", "FedAvg provides the basic aggregation mechanism by combining client parameter updates according to local sample participation. Its main advantage for this project is compatibility with a neural network represented by continuous tensors. Tree structures would require a different federated procedure, whereas the MLP can retain a stable get-parameters and set-parameters contract. The final report treats FedAvg as the aggregation family and distinguishes the adaptive weighting workflow from the basic algorithm."),
        ("2.7 Adaptive Federated Aggregation", "Traffic regions do not necessarily have equal data quality, event prevalence, recency, or relevance to the global deployment population. Adaptive aggregation is therefore useful as an extension to sample-count weighting. The repository's strategy records factors including data quality, event confidence, historical similarity, temporal recency, and regional relevance. The project does not claim that this weighting solves non-IID data in general; it documents the factors as an implemented aggregation design."),
        ("2.8 Neural Networks for Traffic Classification", "The Geo V2 runtime model is a PyTorch MLP with a variable input width and eight output classes. The network contains linear layers, batch normalization, ReLU activations, dropout during training, and a log-softmax output. Its input is a fixed ordered feature vector. This makes the model suitable for tabular state classification while keeping the runtime independent from the training script."),
        ("2.9 Historical Traffic Modeling", "Historical memory is more than a stored average. The current system uses normal baseline speed, speed variation, and vehicle count, then creates current-to-baseline ratios, prior-window means, trends, and low-speed persistence. The history slots are shifted and use earlier observations only. This causal arrangement prevents a current abnormal value from being copied into the feature that is supposed to explain it."),
        ("2.10 OpenStreetMap and Road Networks", "OpenStreetMap contributes road geometry and descriptive tags. The project normalizes the cached source into canonical segments, road types, lane information, maximum speed, and direction metadata. The normalized network is the spatial frame used by both map rendering and route calculation. It is not the ML training dataset; it supplies road structure and metadata used by the feature builder and services."),
        ("2.11 PostGIS and Spatial Data", "PostGIS stores geometry in PostgreSQL and supports spatial indexing and queries. In FedRouteAI, the database contains network rows and live derived state in addition to other system records. Keeping geometry in a spatial database allows the API to serve the same canonical road identity used by ingestion and routing. This reduces ambiguity that would arise if the frontend displayed a separate, unversioned road drawing."),
        ("2.12 Map Matching", "Map matching is the association between a noisy GPS position and a road segment. The earlier V1 pipeline uses geometric projection and trajectory continuity; the Geo V2 network also provides canonical IDs and geometry for trusted simulator observations. The report therefore treats association as a required preprocessing step and does not describe raw coordinate proximity as a complete traffic classifier."),
        ("2.13 Shortest Path Algorithms", "The route service models legal movement as directed transitions between canonical segments. It snaps endpoints, obtains an ordered segment sequence, constructs route geometry, and reports distance and estimated duration. Dijkstra is the dependable shortest-path method used by the routing layer; an alternative path can be inspected when explicit exclusions are requested. The route cost is not silently replaced by a model prediction."),
        ("2.14 Research Gap", "Many individual methods address one part of the problem: traffic prediction, anomaly detection, federated learning, map matching, spatial databases, or routing. The engineering gap addressed here is the integration of these responsibilities under explicit data boundaries. The system must make it possible to trace one observed road state from telemetry through feature construction and prediction to the map, while preserving a different path for route calculation."),
        ("2.15 Project Contribution", "FedRouteAI contributes a reproducible college-scale implementation of this integrated path. Its strongest result is not a claim of universal traffic accuracy; it is the demonstrable connection among an eight-client federated MLP, a versioned 23-feature contract, an OSM/PostGIS directed network, live ingestion, a dynamic map, and a controlled route demonstration. This positioning guides the evaluation and the limitations reported later."),
    ]:
        heading(doc, title)
        p(doc, text)
    table(doc, "Table 2.1: Related Approaches and FedRouteAI Position", ["Area", "Typical focus", "FedRouteAI implementation"], [["Traffic analysis", "Speed, flow, and occupancy patterns", "Current segment aggregates with historical comparison"], ["Anomaly detection", "Deviation or event classification", "Frozen MLP with normal-history context"], ["Federated learning", "Distributed local training", "Eight regional MLP clients and parameter aggregation"], ["Spatial modeling", "Road geometry and neighboring roads", "OSM/PostGIS canonical directed topology"], ["Routing", "Shortest or alternative path", "Directed distance-based route inspection"], ["Visualization", "Map and operational dashboard", "React and Leaflet live traffic map"]])


def chapter3_expansion(doc: Document) -> None:
    sections = [
        ("3.2 User Roles", "The traffic operator uses the map to inspect current segment state, model predictions, route information, and live freshness. The regional client represents a local training participant and is responsible for local data preparation and model update generation. The model administrator manages the selected artifact and checks metadata compatibility. The project evaluator needs reproducible commands, test evidence, and a clear explanation of which values are measured and which are synthetic."),
        ("3.3 Dataset Requirements", "The training dataset must contain segment identity, region identity, timestamp, traffic aggregates, road metadata, historical baselines, and labels only for supervised training or evaluation. The runtime feature builder must be able to operate without a target column. The current Geo V2 manifest records five hours, 1,000 vehicles, 30,000 telemetry rows, three scenario rows, and 16,338 feature windows. These numbers describe the generated research dataset and are not a claim about the live database."),
        ("3.4 Model Requirements", "The model must accept exactly the ordered feature schema expected by the selected artifact, output eight class probabilities, and fail closed when the feature version or network metadata is incompatible. The runtime must preserve the difference between a null prediction caused by insufficient evidence and a normal prediction produced by the classifier. Artifact validation is therefore a functional requirement rather than an optional administration task."),
        ("3.5 Database Requirements", "The database must support PostgreSQL tables, PostGIS geometry, historical memory, live ingestion receipts, current segment projections, predictions, and network transitions. Geometry and transition data must carry a network source and version so a model or route cannot silently operate against an unrelated network. Database initialization and import are separate from application startup."),
        ("3.6 Network Requirements", "The network must contain canonical segment IDs, geometry, direction metadata, legal transitions, road type, lane count, and maximum speed. A route-bound demo additionally requires an ordered route that follows persisted directed transitions and meets the minimum distance. These checks protect the demonstration from generating vehicle paths that look plausible on a map but violate the stored network topology."),
        ("3.7 Technical Feasibility", "The project is technically feasible because each major requirement is supported by an established library or a local service: FastAPI for HTTP endpoints, SQLAlchemy and PostGIS for persistence, PyTorch for the MLP, Flower-compatible training components for federation, NetworkX for graph operations, and React-Leaflet for map rendering. The implementation also includes testable pure functions for feature and routing behavior."),
        ("3.8 Operational Feasibility", "A local operator can start the database, apply migrations, import the Geo V2 network, start the backend and frontend, and use the map without manually constructing a model input. The route-bound demonstration supplies a repeatable way to exercise ingestion and inference. Operational feasibility is limited to a bounded local or project demonstration; it is not evidence of unattended production operation."),
        ("3.9 Economic Feasibility", "The software stack is primarily open source and can run on a local workstation for development and demonstration. A larger training run may benefit from a GPU, but the report does not treat an unmeasured hardware configuration as a performance result. Database storage, model artifacts, and generated telemetry are the principal local resource requirements."),
        ("3.10 Ethical and Data Considerations", "Mobility traces can reveal movement patterns, so the project separates regional learning concepts from central raw-data collection and excludes vehicle identity from model features. The controlled scenario labels are not presented as ground truth predictions. The project also explicitly avoids claiming differential privacy or secure aggregation because those mechanisms are not implemented in the current artifact."),
        ("3.11 System Constraints", "The system is constrained by synthetic-data realism, class imbalance, the fixed frozen artifact, exact 120-second history cadence, local-process deployment, finite browser rendering, and distance-based default routing. These constraints are not hidden implementation details; they define the conditions under which the reported results and demonstrations are meaningful."),
    ]
    for title, text in sections:
        heading(doc, title)
        p(doc, text)
    table(doc, "Table 3.4: Requirement Traceability", ["Requirement group", "Primary implementation evidence"], [["Data", "Geo V2 manifest, feature builder, and dataset partitions"], ["Model", "Feature schema, model store, frozen artifact metadata"], ["Network", "Cached OSM JSON, network normalizer, PostGIS import"], ["Runtime", "Live ingestion, snapshot, prediction persistence"], ["User interface", "Traffic Map tests, route planner, scenario controls"], ["Validation", "Backend suite, frontend suite, build, compile, and smoke evidence"]])


def chapter4_expansion(doc: Document) -> None:
    sections = [
        ("4.2 Design Overview", "The design is organized around immutable identities and explicit transformations. A network version identifies the road structure; a source and run identify a telemetry stream; a timestamp identifies a traffic state; a feature version identifies the model input contract; and an artifact name identifies the selected model. This metadata allows the service to reject incompatible combinations instead of allowing a visually plausible but technically invalid result."),
        ("4.3 Dataset Architecture", "The ML dataset has a label-aware construction path and a label-free inference path. During training, event labels are available to create targets and evaluate predictions. During inference, the feature builder receives current state, normal baselines, earlier state, and network-derived neighbors, but not labels, event identifiers, scenario names, or vehicle IDs. This distinction is the central safeguard against target leakage in the project design."),
        ("4.4 Geo V2 Architecture", "Geo V2 extends current traffic observations with history and spatial context. The current-only block contains speed, dispersion, vehicle count, occupancy, flow, stopped fraction, time-of-day encodings, and road metadata. The history block adds normal baselines, deviation ratios, prior-window means, trends, and low-speed persistence. The promoted history-spatial-strong variant adds directed same-timestamp neighbor_speed_delta. Together these form the exact 23 ordered values loaded by the runtime model."),
        ("4.5 Temporal Feature Construction", "The feature builder requires an exact 120-second cadence between observations for each segment. It computes hour_sin and hour_cos from the timestamp so the daily cycle is represented without a discontinuity at midnight. Prior means use shifted rolling windows, and persistence is calculated from earlier low-speed states. Missing history is filled from normal prehistory rather than from a future or current target state."),
        ("4.6 Spatial Feature Construction", "Spatial context is based on directed persisted topology. At a timestamp, the builder joins a segment to observed outgoing neighbors and calculates neighbor speed, vehicle count, occupancy, and observed-neighbor count. The selected promoted contract retains neighbor_speed_delta, which compares the focal segment's current average speed with its directed neighbor speed context. This is narrower and more auditable than treating every nearby coordinate as a neighbor."),
        ("4.7 PostGIS Architecture", "The OSM import process reads the cached road source, normalizes ways into canonical segments, derives legal directed transitions, and replaces the selected network version in the Geo V2 repository. PostGIS stores LineString geometry and uses spatial database capabilities for retrieval and association. The frontend consumes the same persisted identity that the backend uses for prediction and routing."),
        ("4.8 Backend Architecture", "The backend keeps endpoint code thin. Services coordinate feature construction, simulation, ingestion, prediction, and routing. Repositories contain database access. Pydantic schemas define request and response contracts separately from SQLAlchemy models. The arrangement prevents a map endpoint from quietly implementing model logic or a service from bypassing the repository layer."),
        ("4.9 Live Ingestion Architecture", "A live batch carries source and run identity, observations, timestamps, and traffic measurements. The ingestion service validates and persists the batch, updates the current segment projection, and triggers the prediction path. Idempotent receipt handling prevents a retried batch from creating duplicate history. The map then reads a scoped snapshot so a demonstration run does not accidentally replace the operator's intended live view."),
        ("4.10 Prediction Pipeline", "Prediction begins only after sufficient current and prior state is available. The service builds the ordered feature vector, applies the artifact scaler where required, validates network and feature metadata, and calls the frozen MLP. The resulting class and confidence are stored as prediction state. A missing or malformed feature vector is not silently converted into an arbitrary event class."),
        ("4.11 Traffic Map Architecture", "The map maintains separate layers for network geometry, telemetry styling, model predictions, events, vehicles, and route overlays. This separation matters during a controlled scenario: a moving vehicle or a scenario disturbance is observable behavior, while the predicted road state is an independent model output. The interface also displays freshness and coverage so users can identify missing predictions."),
        ("4.12 Routing Architecture", "Routing accepts origin and destination coordinates, snaps them to the canonical network, and searches the directed graph. It returns actual route geometry, ordered segment IDs, distance, estimated duration, and prediction coverage when scoped prediction state exists. The default route calculation is distance-based; event or prediction information is inspected separately unless explicit exclusions are requested."),
        ("4.13 Route-Bound Demonstration Architecture", "The demonstration service accepts only Normal, Congestion, and Accident scenarios. It requires the ordered route produced by the route planner, checks unknown IDs and directed transitions, and rejects routes shorter than 1.5 km. The simulator controls vehicle movement and disturbance scheduling, while the telemetry is scrubbed before it enters the label-free inference contract. The route impact panel counts only predictions actually returned for route segments."),
    ]
    for title, text in sections:
        heading(doc, title)
        p(doc, text)
    table(doc, "Table 4.3: Dataset and Runtime Data Separation", ["Data source", "Purpose", "Labels available?"], [["ML training/evaluation data", "Train, validate, and test the classifier", "Yes for target construction/evaluation"], ["OSM/PostGIS network", "Geometry, road metadata, topology, and routing", "No"], ["Live GPS telemetry", "Current runtime observations", "No scenario labels in inference"], ["Controlled demonstration telemetry", "Repeatable route-bound behavior", "Scenario truth kept outside features"], ["Prediction persistence", "Serve independent model outputs", "Predicted class and confidence"]])


def chapter5_expansion(doc: Document) -> None:
    sections = [
        ("5.2 Dataset Generation", "The Geo V2 dataset generator creates traffic states over the canonical network and writes a manifest describing the run. The recorded manifest identifies a five-hour period beginning at 2026-07-07 06:00:00, a 600-second tick interval, 1,000 vehicles, 30,000 telemetry rows, three scenario rows, 16,338 feature windows, and network version beeramguda-osm-20260506. The scenario table is separate from the telemetry features and is not used as an inference input."),
        ("5.3 Regional Data Partitioning", "The regional partition is based on REGION_01 through REGION_08. A regional split allows local training and validation behavior to be examined without flattening all records into one client. It also reflects the system's intended deployment concept: different geographic regions can have different traffic distributions, event frequencies, and history quality. The aggregation process must therefore handle non-identical local data rather than assuming identical samples."),
        ("5.4 MLP Model", "The GeoV2MLP accepts a variable input width but requires eight output classes. Its sequential network uses a first linear layer, batch normalization, ReLU, dropout, a narrower hidden layer, another normalization and ReLU stage, and a final linear classifier. The forward pass returns log-softmax values and the probability method exponentiates them. This runtime definition is kept separate from training orchestration so the application can load the artifact without importing the training loop."),
        ("5.5 Local Client Training", "A local client prepares its regional examples, uses the current global parameters as its starting point, performs local optimization, evaluates the result, and returns updated parameters with sample metadata. The client does not send raw GPS rows as the model update. Local training behavior can be affected by regional class imbalance and history quality, which is why regional metrics and aggregation metadata are retained."),
        ("5.6 FedAvg", "FedAvg combines participating model parameters after a local training step. In practical terms, the server receives arrays representing the MLP weights and biases, associates each update with its local example count and metrics, and computes a global parameter set. The stable parameter interface is important because the same mechanism can be used for initialization, rounds, checkpoint comparison, and deployment artifact creation."),
        ("5.7 AdaptiveFedAvg", "Adaptive aggregation extends the basic parameter average with quality and relevance information. The current workflow records client-level factors and applies bounded projection in the selected robust run. The report describes this as adaptive aggregation, not as a guarantee that every region is equally represented or that all rare events are solved. The final artifact metadata records the selected aggregation configuration so the runtime model can be traced to a documented experiment."),
        ("5.8 Global Model Selection", "The promoted checkpoint was selected using validation evidence before the one-time test access. The recorded selection is round 45 of a maximum 50-round run. This separation matters because using the test set repeatedly for checkpoint selection would make the reported test result optimistic. The artifact directory retains validation selection, training history, client metrics, and test receipt files to support review."),
        ("5.9 Model Artifact Management", "Model loading validates feature version, ordered features, network version, model identity, scaler metadata, and tensor compatibility. The selected artifact is frozen for the current application demonstration. The application does not retrain on startup, alter the artifact in response to a scenario button, or substitute scenario truth for a missing model output. These rules protect the meaning of a live prediction."),
        ("5.10 Live GPS Ingestion", "The live ingestion service accepts trusted multi-vehicle observations with source, run, batch, and observation identity. It records an ingestion receipt, persists append-only GPS history, and updates a current-state projection. The append-only history supports later inspection, whereas the projection makes the latest map state inexpensive to serve. Retried batches are checked for identity and payload consistency."),
        ("5.11 Segment Association", "For map-matched V1 ingestion, candidate segments are selected spatially and a geometric matcher uses projection and trajectory continuity. For Geo V2 trusted simulator observations, the canonical segment ID is supplied by the controlled network path and still validated against the persisted network. In both cases, segment identity is the bridge between telemetry and every downstream feature, prediction, map, and route operation."),
        ("5.12 Traffic Aggregation", "The service aggregates observations by segment and tick into average speed, speed standard deviation, vehicle count, occupancy, flow rate, and stopped fraction. These are current state fields rather than labels. The aggregation deliberately removes identity-level information from the feature vector while preserving the traffic quantities needed for classification."),
        ("5.13 Historical Memory", "Historical memory is computed from normal prehistory and is used as the comparison frame for runtime state. The service keeps baseline speed, baseline variation, and baseline vehicle count. Current-to-baseline ratios and trend values are computed later by the Geo V2 feature builder. This separation prevents the database baseline row from being confused with a prediction or with scenario truth."),
        ("5.14 Geo V2 Feature Construction", "The feature builder verifies required columns, exact cadence, baseline coverage, and forbidden target-related tokens. It derives temporal encodings, baseline ratios, shifted prior means, trends, persistence, and directed-neighbor context. It returns only metadata and the selected feature variant in a deterministic ordering. The promoted variant is history_spatial_strong with 23 values."),
        ("5.15 Label-Free Inference", "At runtime, the model receives the 23 feature values and no event label, scenario name, event ID, vehicle ID, or ground-truth severity. If a controlled scenario causes traffic to change, the model sees only the resulting aggregate behavior. The prediction can remain normal, become an abnormal class, or be unavailable. That outcome is independent of the scenario control selected by the user."),
        ("5.16 Prediction Persistence", "Prediction persistence records the segment, timestamp, model identity, feature version, predicted event, confidence, and related deviations. The live snapshot returns these values alongside current traffic state. This allows the frontend to color road segments and display inspection details without recomputing the model in the browser."),
        ("5.17 Dynamic Traffic Map", "The React map requests network geometry and live snapshots through typed API clients. It presents a live status indicator, network source and version, vehicle counts, prediction counts, route summary, and selected road details. Map layers can be toggled independently so a reviewer can inspect telemetry without confusing it with prediction styling."),
        ("5.18 Vehicle Animation", "The backend remains authoritative for vehicle positions and counts. The frontend animates between received positions to avoid visually discontinuous jumps, but the interpolated frame is not inserted into the telemetry history. A rendered marker cap limits browser work for large demonstrations while the displayed active count continues to refer to backend state."),
        ("5.19 Route Calculation", "The route planner sends origin, destination, network identity, and optional scoped live-run identity to the shortest-route endpoint. The backend snaps both endpoints, searches directed transitions, and returns a route geometry and ordered segment list. Prediction coverage is calculated from available route segment state rather than assuming every network segment has a current model output."),
        ("5.20 Alternative Route and Route Inspection", "The normal route is calculated using the configured distance-based cost. When the user explicitly requests an alternative around abnormal segments, those segment IDs are passed as exclusions and a new directed route is calculated. This is an explicit user action and should not be described as the model autonomously changing the default route cost."),
        ("5.21 Route-Bound Demonstrations", "The route-bound service validates the exact ordered route supplied by the frontend. It checks unknown segments, directed transitions, minimum route distance, and scenario enum values. Controlled vehicle routes remain within the selected corridor, and scenario metadata is scrubbed before model input. The map reports route prediction coverage and abnormal counts without fabricating missing predictions."),
        ("5.22 API Implementation", "FastAPI endpoints provide health, network, ingestion, live-map, prediction, route, and demo interfaces. Pydantic schemas enforce field types and bounds, including the minimum route distance and accepted scenario values. The service layer owns state transitions and business rules, while repository methods own database queries. This keeps API behavior predictable and testable."),
        ("5.23 Frontend Implementation", "The frontend uses React, React Query, typed API clients, and Leaflet. The Traffic Map page manages route selection, live sessions, scoped snapshots, scenario controls, map layers, vehicle selection, road inspection, and reset behavior. The UI distinguishes model prediction from scenario behavior in its wording and data presentation."),
        ("5.24 Error Handling", "Invalid route topology, short routes, unknown segment IDs, mismatched model/network versions, unavailable snapshots, expired demo runs, and failed inference requests produce explicit errors or unavailable states. The system does not silently turn missing data into abnormal events. The frontend preserves useful state where possible, such as retaining the calculated route after a demo reset."),
        ("5.25 Configuration Management", "Database settings, model paths, network identities, cadence, and service URLs are loaded through project configuration rather than scattered literals. The report does not reproduce secret values. A local operator must configure PostgreSQL/PostGIS and any ingestion key through environment settings before running database-backed demonstrations."),
    ]
    for title, text in sections:
        heading(doc, title)
        p(doc, text)
    table(doc, "Table 5.3: Model Configuration", ["Property", "Verified value"], [["Runtime model", "GeoV2MLP"], ["Output classes", "8"], ["Input feature count", "23"], ["Feature version", "geo-v2-history_spatial_strong-23-v2"], ["Training rounds", "50 maximum; checkpoint round 45"], ["Local epochs", "2"], ["Dropout", "0.2 in runtime architecture"], ["Inference mode", "Label-free feature input"]])
    table(doc, "Table 5.4: Demonstration Controls", ["Control", "Behavior"], [["Normal", "Baseline route-bound traffic behavior"], ["Congestion", "Controlled congestion-like route behavior"], ["Accident", "Controlled accident-like route disturbance"], ["Minimum route", "Approximately 1.5 km"], ["Route binding", "Ordered directed segment IDs supplied by route calculation"], ["Truth handling", "Scenario metadata excluded from model features"]])


def chapter6_expansion(doc: Document) -> None:
    sections = [
        ("6.2 Unit Testing", "Pure tests cover map matching decisions, event signature behavior, historical aggregation, adaptive weighting, graph reasoning, feature construction, and route logic. These tests are intentionally small because the mathematical and state-transition rules should be diagnosable without a running PostgreSQL server. They protect the transformations that later appear inside the API flow."),
        ("6.3 Backend Testing", "The backend test suite exercises FastAPI import, health behavior, ingestion, prediction, live snapshots, route calculation, Geo V2 network handling, and controlled demonstrations. The current verified suite contains 117 passing tests. The count is a repository verification result, not a claim that every possible network or model condition has been exhausted."),
        ("6.4 API Contract Testing", "Schema tests verify required fields, enum restrictions, route minimum distance, prediction metadata, telemetry scrubbing, and response shape. Route-bound demo creation must receive ordered segment IDs and distance from the frontend route result. This prevents the UI and backend from silently drifting into separate assumptions about the selected route."),
        ("6.5 Database Testing", "Database-facing tests use the project's configured test approach and small isolated fixtures where appropriate. They verify persistence and retrieval relationships such as current segment state, prediction rows, network metadata, and demonstration receipts. A full local production database is not required for every pure service test, which keeps the feedback cycle fast."),
        ("6.6 Geo V2 Feature Testing", "Feature tests verify the exact input columns, ordered feature version, cadence requirement, shifted history, normal prehistory fallback, directed neighbor construction, and forbidden target-token rejection. These checks are essential because a model can produce numerically valid output even when the semantic feature order is wrong."),
        ("6.7 Model Artifact Testing", "Artifact checks load the selected MLP, verify the 23-feature schema, confirm the network and model metadata, inspect scaler ordering, and reject incompatible files. The final report states the artifact's recorded metrics and limitations rather than recalculating or retraining it during documentation generation."),
        ("6.8 Federated Learning Validation", "Federated validation compares regional participation, round history, client metrics, aggregation weights, and validation selection. The chosen run records eight clients, a maximum of 50 rounds, two local epochs, and a selected checkpoint at round 45. The test set is accessed only after selection in the recorded experiment, as stated by the artifact report."),
        ("6.9 Routing Testing", "Routing tests use directed segment transitions and verify that a route follows legal topology, returns ordered segment IDs, and reports distance and geometry. Explicit exclusions are tested separately from default routing. This distinction protects the claim that the current default route is distance-based rather than model-optimized."),
        ("6.10 Live Ingestion Testing", "Live-ingestion tests verify accepted batches, idempotent receipts, current-state projection, scoped source and run identity, model inference, and persistence of prediction fields. Tests also check that telemetry does not carry scenario labels or event IDs into the inference input path."),
        ("6.11 Frontend Testing", "The frontend suite checks initial loading, live start and pause, polling, stale and offline status, map layers, region filtering, road selection, vehicle selection, route calculation, route clearing, and prediction metadata. The current Traffic Map focused suite contains 17 passing tests and the production TypeScript/Vite build passes."),
        ("6.12 Traffic Map Testing", "Map tests use deterministic road and snapshot fixtures to verify that the correct segment count, route line, prediction state, and vehicle information are rendered. Layer independence is important: hiding predictions must not hide telemetry, and a route overlay must remain tied to the calculated geometry rather than to a scenario marker."),
        ("6.13 Vehicle Motion Testing", "Vehicle motion tests verify cleanup, marker limits, selection behavior, and updates from subsequent authoritative snapshots. The visual interpolation layer is tested as a rendering concern. It does not change the persisted observation count or create a second stream of synthetic backend GPS points."),
        ("6.14 Controlled Demonstration Testing", "Demonstration tests validate Normal, Congestion, and Accident enum handling, route length rejection, unknown segment rejection, directed transition validation, deterministic route binding, scoped snapshots, expiry cleanup, label scrubbing, and reset behavior. They also verify that route-impact summaries count only available predictions."),
        ("6.15 Build Validation", "Python modules are compiled without errors, the FastAPI application imports cleanly, the frontend TypeScript compiler completes, and Vite produces a production bundle. These checks detect syntax, import, and contract errors that unit tests alone may miss."),
        ("6.16 Runtime Validation", "The verified smoke workflow uses a live backend and canonical network identity, creates or receives observations, checks scoped prediction persistence, and resets the demonstration. Runtime evidence is interpreted with the database and artifact configuration active at the time of the run; it is not generalized into a production capacity claim."),
        ("6.17 Performance Testing", "The recorded model artifact report measures warmed single-row CPU inference at approximately 0.414 ms across 1,000 calls, equivalent to approximately 2,416 calls per second under that setup. This is a model-call measurement, not an end-to-end ingestion or browser throughput measurement. End-to-end latency, PostgreSQL load capacity, and memory pressure under a production workload were not measured in the current implementation."),
        ("6.18 Limitations of Validation", "Synthetic data limits external validity, class imbalance affects aggregate metrics, and local demonstrations do not represent a city-wide deployment. The report also avoids treating the 1,000-vehicle configuration as 1,000 independent predictions because model outputs are generated at observed segment or batch granularity. These limitations are part of the validation conclusion."),
    ]
    for title, text in sections:
        heading(doc, title)
        p(doc, text)
    table(doc, "Table 6.3: Test Categories", ["Category", "Scope", "Result / status"], [["Unit and service", "Pure functions and service rules", "Covered by backend suite"], ["API contracts", "Pydantic request/response behavior", "Covered by focused tests"], ["Geo V2", "Feature ordering, cadence, history, neighbors", "Covered by model and feature tests"], ["Artifact", "Model, scaler, metadata, compatibility", "Passed for frozen artifact"], ["Routing", "Directed path, exclusions, route metadata", "Covered by routing tests"], ["Live ingestion", "Batch, persistence, prediction snapshot", "Covered by integration tests"], ["Frontend", "Map, route, demo, live controls", "17 focused tests passed"], ["Build", "Compile, import, production bundle", "Passed"]])


def chapter7_expansion(doc: Document) -> None:
    sections = [
        ("7.2 Local Deployment", "The local deployment consists of PostgreSQL/PostGIS, the FastAPI backend, the Vite development server, and optional simulator or replay processes. Database migration and Geo V2 network import happen before the application is used for database-backed map and routing features. The root launcher can coordinate backend and frontend processes, while manual startup is useful when logs need to remain separate."),
        ("7.3 Backend Configuration", "Backend configuration selects the database connection, artifact location, Geo V2 baseline source, network source and version, cadence, and ingestion behavior. These values are loaded through the application's configuration layer. The report intentionally does not expose local passwords or keys. A deployment operator must provide valid local values before running the full database-backed workflow."),
        ("7.4 Frontend Configuration", "The frontend uses a configurable API base URL and a development proxy for local operation. Its query keys include live session and scoped demonstration identity so an old snapshot does not become the current run by accident. The browser receives normalized snapshots rather than reaching directly into database tables."),
        ("7.5 Database Configuration", "PostgreSQL stores relational application state and PostGIS stores road geometry. The Geo V2 import is versioned and additive with respect to the preserved V1 network. The database schema includes network, live ingestion, prediction, historical, and supporting records as defined by the current models and migrations."),
        ("7.6 Environment Variables", "Environment variables are used for database credentials, API keys where configured, frontend API base URL, and model or baseline paths. Secrets belong in local environment files or deployment secret stores and should not be copied into a submitted report. The report records configuration categories, not secret values."),
        ("7.7 API Security", "The live ingestion workflow can require a configured API key and validates request identity and batch payload. The demonstration endpoints apply bounded run lifecycle rules and scoped source/run identity. The current project does not claim a complete authentication and authorization system for every endpoint; this is a prototype limitation."),
        ("7.8 Input Validation", "Pydantic schemas validate data types and enumerations. Geo V2 services validate network identity, segment existence, directed transitions, minimum route distance, and feature availability. Input validation is especially important for route-bound demonstrations because an invalid ordered path could otherwise create a visually plausible but topologically false result."),
        ("7.9 Model Artifact Integrity", "The model store checks the artifact's expected feature version, ordered feature names, network version, model identity, scaler, and tensor structure. The model is loaded in evaluation mode for inference. If metadata does not match the active data contract, the system fails closed rather than making a prediction whose semantics cannot be verified."),
        ("7.10 Data Separation", "The deployment keeps ML training/evaluation records, OSM/PostGIS network data, live GPS telemetry, controlled demonstration telemetry, and prediction persistence as distinct conceptual stores. They are joined through explicit IDs and timestamps, not treated as one interchangeable dataset. This separation is required for honest interpretation of model results."),
        ("7.11 Privacy Considerations", "Federated learning reduces the need to centralize raw regional training data in the intended architecture, and runtime features omit vehicle identity and scenario truth. Nevertheless, the current implementation does not provide differential privacy, secure aggregation, or a formal privacy budget. These are future security enhancements, not present capabilities."),
        ("7.12 Runtime Performance", "The available performance evidence is limited but concrete: warmed CPU single-row inference averages approximately 0.414 ms across 1,000 calls in the artifact report. The complete path also includes database access, feature construction, batch processing, and network communication, which were not represented by that isolated model-call number."),
        ("7.13 Memory Usage", "A complete memory profile for the backend, database, model, and browser at the 1,000-vehicle scale was not measured in the current implementation. The system does include bounded run registries, expiry cleanup, batched inference, and a frontend vehicle rendering cap. These controls reduce avoidable growth but should not be reported as a measured memory guarantee."),
        ("7.14 Browser Rendering Considerations", "The map can contain thousands of network segments and large vehicle populations. Static road geometry is loaded separately from live snapshots, vehicle markers are capped for rendering, and React Query controls refresh behavior. The map distinguishes visible markers from backend active count so a rendering optimization is not mistaken for data loss."),
        ("7.15 Scalability", "The federated topology can add regional clients, and the repository/service layering can move database work behind a queue or worker in future. Current ingestion uses local process behavior and is appropriate for Phase 1 demonstration scope. Horizontal scaling, broker-backed ingestion, distributed caching, and cloud deployment were not implemented or measured."),
        ("7.16 Current Limitations", "The deployment remains a research and academic prototype. Its model has minority-class limitations, its data is synthetic for the documented Geo V2 run, its routing is distance-based by default, and formal privacy mechanisms are absent. These facts define the correct operating envelope and should accompany any demonstration of the system."),
    ]
    for title, text in sections:
        heading(doc, title)
        p(doc, text)


def appendices_expansion(doc: Document) -> None:
    heading(doc, "APPENDIX D: Model Configuration", level=2)
    p(doc, "The promoted artifact is identified as fedrouteai-geo-v2-robust-robust-v2-hs1-prior2-unweighted-bw3-22-50r2e-seed42-r45. Its feature version is geo-v2-history_spatial_strong-23-v2, its network version is beeramguda-osm-20260506, and its selected checkpoint is round 45. The model has eight output classes and uses the ordered 23-feature schema listed in Chapter 4. These values are reproduced from the frozen artifact metadata and are not regenerated by this documentation task.")
    heading(doc, "APPENDIX E: Database and Network Statistics", level=2)
    table(doc, "Table 9.1: Database and Network Evidence", ["Evidence item", "Value / interpretation"], [["Geo V2 network", "2,968 canonical segments"], ["Directed topology", "11,259 persisted transitions"], ["Regions", "8 regional IDs"], ["Network version", "beeramguda-osm-20260506"], ["Network source", "osm_geo_v2"], ["Geometry", "PostGIS LineString representation"], ["Route identity", "Ordered directed segment IDs"]])
    heading(doc, "APPENDIX F: Testing Evidence", level=2)
    p(doc, "The current evidence register includes 117 passing backend tests, 17 passing Traffic Map frontend tests, a successful frontend production build, successful Python compilation, successful FastAPI import, model artifact validation, and normalized network counts. A future submitted version may insert screenshots or terminal excerpts into the reserved figure spaces after they are reviewed for sensitive configuration values.")
    heading(doc, "APPENDIX G: Sample Telemetry Semantics", level=2)
    p(doc, "A runtime observation represents traffic state associated with a canonical segment and timestamp. It may contain speed, vehicle count, occupancy, flow, stopped fraction, and road metadata after aggregation. The model feature vector does not include latitude, longitude, vehicle identity, device identity, scenario name, event ID, or ground-truth label. Controlled telemetry may be generated to change the traffic pattern, but it remains an observation source rather than a label source.")
    heading(doc, "APPENDIX H: Prediction Response Semantics", level=2)
    p(doc, "A prediction response is associated with a segment, timestamp, model version, feature version, predicted class, confidence, and current deviation information where available. A null or unavailable output means that the runtime did not have a valid prediction for that state; it is not equivalent to a confident normal classification. The Traffic Map displays this distinction through coverage and prediction status.")
    heading(doc, "APPENDIX I: Routing Response Semantics", level=2)
    p(doc, "A shortest-route response contains network identity, snapped endpoints, distance, estimated duration, segment count, ordered segment IDs, and route geometry. Prediction fields, when available, summarize only the route segments covered by current persisted predictions. A route can therefore be valid even when prediction coverage is incomplete.")
    heading(doc, "APPENDIX J: Project Screenshot Register", level=2)
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
    ]
    for title, first, second in evidence_pages:
        doc.add_page_break()
        heading(doc, title, level=2)
        p(doc, first)
        p(doc, second)


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

    chapter(doc, 7, "Deployment, Security and Performance")
    heading(doc, "7.1 Local Deployment Architecture")
    p(doc, "The application can be run as separate local processes: PostgreSQL/PostGIS, FastAPI, Vite, and optional simulator or Geo V2 replay processes. Alembic applies the schema, the network importer creates the additive Geo V2 network, and the frontend connects to the backend through its configured API base URL. Docker is useful for a disposable PostGIS container but is not the application deployment architecture itself.")
    figure(doc, "7.1", "Local Deployment Architecture")
    heading(doc, "7.2 Security and Privacy Position")
    p(doc, "The architecture is motivated by data minimization through federated training and label-free runtime features. However, the implementation does not claim differential privacy, secure aggregation, encryption guarantees, or formal privacy bounds. API keys are used for trusted live-ingestion workflows where configured. Secrets and database passwords must remain in local environment configuration and must not be committed to the report or source control.")
    heading(doc, "7.3 Performance and Scalability")
    p(doc, "The verified artifact report records average CPU single-row inference of approximately 0.414 ms across 1,000 warmed calls, or approximately 2,416 calls per second under that measurement setup. The five-hour demonstration configuration contains 1,000 persistent vehicles and 150 ten-minute ticks. The manifest records 30,000 telemetry rows because 1,000 vehicles are represented at each of 30 ten-minute steps in that generated run; this is distinct from model prediction count, which is segment/batch based.")
    table(doc, "Table 7.1: Runtime Performance Evidence", ["Measure", "Verified value / interpretation"], [["Single-row CPU inference", "0.414 ms average after warm-up"], ["Approximate inference throughput", "2,416 calls/second in the recorded setup"], ["Demonstration vehicles", "1,000 persistent vehicles"], ["Demonstration duration", "5 simulated hours"], ["Demonstration ticks", "150 ten-minute ticks in the intended replay configuration"], ["Prediction granularity", "Observed road segment/batch, not one prediction per vehicle"]])
    table(doc, "Table 7.2: Current Limitations", ["Area", "Limitation"], [["Data", "Geographically grounded synthetic telemetry is not measured traffic."], ["Model", "Minority event recall and anomaly precision remain limited."], ["Privacy", "Formal differential privacy and secure aggregation are not implemented."], ["Routing", "Default cost is distance-based, not learned traffic-aware routing."], ["Operations", "Background/in-process demonstration execution is a bounded prototype scope."], ["Events", "Event close-out and end-time lifecycle handling remain limited."], ["Deployment", "Production cloud orchestration and queue infrastructure are future work."]])

    chapter(doc, 8, "Conclusion and Future Enhancements")
    heading(doc, "8.1 Conclusion")
    p(doc, "FedRouteAI demonstrates a complete traffic intelligence prototype that combines federated learning, a Geo V2 causal feature contract, historical traffic memory, OSM/PostGIS road topology, live GPS ingestion, frozen MLP inference, dynamic map visualization, and directed shortest-path routing. The system is organized around traceable contracts: the road network is distinct from the ML dataset, live telemetry is distinct from controlled demonstration behavior, and model features exclude scenario truth.")
    p(doc, "The implementation has been validated through backend and frontend tests, artifact checks, build checks, and network normalization evidence. It is suitable as a B.Tech major project demonstration and a foundation for further research. Its results are reported honestly: the model improves the preserved baseline according to its recorded metrics, but minority event performance, synthetic-data realism, formal privacy mechanisms, and production-scale operations remain open limitations.")
    heading(doc, "8.2 Learning Outcomes")
    p(doc, "The project provided experience in federated model design, tabular feature engineering, causal time-window construction, PyTorch training, PostGIS spatial data, directed graph routing, FastAPI service architecture, React-Leaflet visualization, testing, artifact governance, and technical documentation. It also required distinguishing model evidence from demonstration behavior and separating system subsystems by their data responsibilities.")
    heading(doc, "8.3 Future Enhancements")
    for text in ["Collect and validate larger real-world GPS traffic datasets across seasons and cities.", "Improve event-specific sampling and class-balanced training for diversion, construction, and other minority classes.", "Evaluate stronger adaptive federated aggregation and larger client populations.", "Add formal differential privacy, secure aggregation, and auditable privacy accounting.", "Develop traffic-aware route costs after validating prediction reliability and operational safety.", "Move ingestion and replay work to queue-backed services for scale.", "Explore online learning, edge deployment, and energy-aware regional clients.", "Evaluate CCTV or video integration only as a separate future extension, not as part of the current system."]:
        p(doc, "- " + text, indent=False, after=3)

    chapter(doc, 9, "Appendices")
    heading(doc, "APPENDIX A: Project Run and Reproduction Guide", level=2)
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


def main_content(doc: Document) -> None:
    """Build the expanded report from the verified project evidence."""
    chapter(doc, 1, "Introduction")
    heading(doc, "1.1 Introduction")
    p(doc, "FedRouteAI is an end-to-end traffic intelligence prototype that detects temporary road conditions from GPS-derived traffic behavior and supports route inspection. It combines an OSM/PostGIS directed network, live telemetry aggregation, historical traffic memory, a causal 23-feature Geo V2 contract, an eight-client federated MLP, and a React-Leaflet map. The system is designed for traceable academic evaluation: every important transformation has an explicit data boundary and the controlled demonstration is kept separate from model ground truth.")
    chapter1_expansion(doc)
    chapter(doc, 2, "Literature Survey")
    heading(doc, "2.1 Survey Introduction")
    p(doc, "This chapter places the project at the intersection of intelligent transportation systems, GPS traffic analysis, anomaly detection, federated learning, spatial databases, and routing. The review focuses on the design decisions that are implemented in the repository and on the gap addressed by integrating them into one inspectable pipeline.")
    chapter2_expansion(doc)
    chapter(doc, 3, "Requirement Analysis and Feasibility Study")
    heading(doc, "3.1 Stakeholders and Core Requirements")
    p(doc, "The principal stakeholders are traffic operators, regional learning clients, model administrators, researchers, end users, and project evaluators. Their needs span trustworthy traffic state, reproducible training, compatible artifacts, route inspection, and clear evidence boundaries.")
    table(doc, "Table 3.1: Functional Requirements", ["ID", "Requirement", "Verification"], [["FR-01", "Ingest GPS or trusted live observations", "API and integration tests"], ["FR-02", "Associate observations with road segments", "Map-matching and network tests"], ["FR-03", "Construct historical and Geo V2 features", "Feature-contract checks"], ["FR-04", "Run frozen MLP inference", "Artifact and prediction tests"], ["FR-05", "Persist and serve prediction state", "Live map API tests"], ["FR-06", "Display roads, vehicles, events, and predictions", "Frontend tests and build"], ["FR-07", "Calculate directed shortest routes", "Routing tests"], ["FR-08", "Run route-bound demonstrations", "Demo validation tests"]])
    chapter3_expansion(doc)
    chapter(doc, 4, "System Design and Architecture")
    heading(doc, "4.1 High-Level Architecture")
    p(doc, "FedRouteAI follows the one-directional project layering: API endpoints call services, services call repositories, and repositories access models. The ML subsystem is connected through explicit feature and artifact contracts. The frontend consumes API responses and does not reproduce backend inference or routing logic.")
    figure(doc, "4.1", "Overall System Architecture of FedRouteAI")
    chapter4_expansion(doc)
    for number, caption in [
        ("4.2", "Federated Learning Architecture"),
        ("4.3", "Regional Client and Server Interaction"),
        ("4.4", "End-to-End Data Pipeline"),
        ("4.5", "Geo V2 Feature Construction Pipeline"),
        ("4.6", "Historical Traffic Memory and Causal Windows"),
        ("4.7", "OSM/PostGIS Network Import"),
        ("4.8", "Directed Road Network and Transitions"),
        ("4.9", "Backend Service and Repository Layers"),
        ("4.10", "Frontend Map and API Interaction"),
        ("4.11", "Directed Shortest-Path Routing"),
    ]:
        figure(doc, number, caption)
    chapter(doc, 5, "Implementation")
    heading(doc, "5.1 Project Module Mapping")
    table(doc, "Table 5.1: Major Software Modules", ["Module", "Role"], [["app/api", "Thin HTTP endpoints and request validation"], ["app/services", "Business logic and workflow orchestration"], ["app/ml/geo_v2", "Features, model store, and inference contract"], ["app/repositories", "Database and PostGIS access"], ["frontend/src/pages/TrafficMap", "Map, route, live controls, and inspection"], ["scripts/geo_v2", "Network import, dataset generation, replay, and validation"]])
    figure(doc, "5.1", "Live GPS Ingestion Pipeline")
    chapter5_expansion(doc)
    for number, caption in [
        ("5.2", "Frozen Geo V2 MLP Inference"),
        ("5.3", "Dynamic Traffic Map"),
        ("5.4", "Moving Vehicle Visualization"),
        ("5.5", "Route-Bound Demonstration Flow"),
        ("5.6", "Normal Traffic Demonstration"),
        ("5.7", "Congestion and Accident Demonstrations"),
    ]:
        figure(doc, number, caption)
    chapter(doc, 6, "Testing and Validation")
    heading(doc, "6.1 Testing Strategy")
    p(doc, "Testing covers pure service logic, API contracts, model compatibility, database-backed workflows, frontend interaction, build behavior, and runtime smoke paths. Fixture-free tests are used where possible so feature and routing rules remain diagnosable without a live database.")
    figure(doc, "6.1", "Model Validation Results")
    chapter6_expansion(doc)
    for number, caption in [("6.2", "Model Confusion Matrix"), ("6.3", "Backend and Frontend Test Evidence")]:
        figure(doc, number, caption)
    chapter(doc, 7, "Deployment, Security and Performance")
    heading(doc, "7.1 Deployment Context")
    p(doc, "The documented deployment is a local academic prototype consisting of PostgreSQL/PostGIS, FastAPI, the frontend development server, and optional replay or simulation processes. Production orchestration, queue-backed ingestion, and cloud capacity are outside the measured scope.")
    figure(doc, "7.1", "Local Deployment Architecture")
    chapter7_expansion(doc)
    chapter(doc, 8, "Conclusion and Future Enhancements")
    heading(doc, "8.1 Conclusion")
    p(doc, "FedRouteAI demonstrates a complete and traceable traffic intelligence pipeline. Its contribution is the integration of federated tabular learning, causal traffic features, historical memory, a canonical directed road network, live ingestion, model persistence, dynamic mapping, and route-bound demonstrations. The documented metrics and limitations show that the prototype is suitable for academic evaluation but not unattended safety-critical operation.")
    heading(doc, "8.2 Objectives Achieved")
    p(doc, "The completed system ingests traffic observations, associates them with a canonical road network, constructs label-free Geo V2 features, runs a frozen federated MLP, persists predictions, presents live state on a React-Leaflet map, and calculates directed shortest routes. It also provides a route-bound demonstration that keeps controlled traffic behavior separate from model output.")
    heading(doc, "8.3 Major Contributions")
    p(doc, "The major contributions are the ordered 23-feature causal contract, eight-region federated training workflow, versioned OSM/PostGIS network with 2,968 segments and 11,259 directed transitions, integrated ingestion-to-map pipeline, and explicit evidence boundaries for demonstrations, predictions, and routing.")
    heading(doc, "8.4 Experimental Findings")
    p(doc, "The frozen artifact records validation macro F1 of 0.3042, test macro F1 of 0.3200, event-balanced macro F1 of 0.4459, anomaly recall of 0.3444, anomaly precision of 0.2093, and normal false-positive rate of 0.0031. Overall accuracy is high because normal traffic dominates the dataset, while diversion and construction remain difficult minority classes.")
    heading(doc, "8.5 Limitations")
    p(doc, "The documented dataset is geographically grounded but synthetic, minority-event performance remains limited, and the system is not approved for unattended safety-critical operation. Formal differential privacy, secure aggregation, production queueing, cloud orchestration, and learned traffic-aware route costs are not implemented.")
    heading(doc, "8.6 Future Enhancements")
    add_paragraphs(doc, [
        "Collect measured GPS traffic across seasons and cities and evaluate transfer beyond the current synthetic network.",
        "Improve minority-event sampling and event-specific calibration, especially for diversion and construction.",
        "Add formal differential privacy, secure aggregation, and auditable privacy accounting.",
        "Develop traffic-aware route costs only after prediction reliability is sufficient for operational use.",
        "Move ingestion and replay to queue-backed services and evaluate distributed deployment.",
        "Study graph neural networks as a future extension for learned spatial reasoning.",
    ])
    heading(doc, "8.7 Final Remarks")
    p(doc, "FedRouteAI is therefore best understood as a complete and academically honest local prototype: it demonstrates how federated learning, causal traffic features, spatial infrastructure, live services, and user-facing route inspection can be integrated while keeping unverified production and safety claims outside the project scope.")
    chapter(doc, 9, "Appendices")
    heading(doc, "APPENDIX A: Project Run and Reproduction Guide", level=2)
    p(doc, "Prepare Python and Node.js environments, start PostgreSQL with PostGIS, apply Alembic migrations, import the cached Geo V2 network, start the FastAPI backend and Vite frontend, open the Traffic Map, start live mode, calculate a directed route, and select a route-bound demonstration. Exact commands are maintained in HOW_TO_RUN_PROJECT.md and README.md.")
    heading(doc, "APPENDIX B: Evidence and Artifact Register", level=2)
    table(doc, "Table 9.2: Evidence Register", ["Evidence", "Role"], [["Geo V2 model report", "Frozen selection, metrics, limitations, and runtime contract"], ["Feature schema JSON", "Ordered 23-feature contract and version"], ["Network source JSON", "Cached OSM input for normalized network"], ["Dataset manifest", "Generated data configuration and counts"], ["Backend test suite", "Service, API, model, ingestion, and routing validation"], ["Frontend test suite", "Traffic Map and interaction validation"]])
    heading(doc, "APPENDIX C: Figure Insertion Register", level=2)
    p(doc, "All figure spaces are intentional placeholders. Final black-and-white figures may be inserted after the report draft is reviewed. Scenario screenshots must visibly distinguish controlled traffic behavior from independent model prediction.")
    appendices_expansion(doc)
    chapter(doc, 10, "References")
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
    doc.core_properties.comments = "Documentation draft with figure placeholders; no final figures inserted."
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
