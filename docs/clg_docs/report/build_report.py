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
OUT = ROOT / "FedRouteAI_Major_Project_Report.docx"

TITLE = "FedRouteAI: Adaptive Federated Learning for Resilient Edge-Based Traffic Anomaly Detection"
STUDENTS = [("MOGULOJU ABHIRAM", "23211A6774"), ("RAJULAPUDI ROHITH", "23211A67A0")]
GUIDE = "Mrs. S. Jyothsna"
DEPARTMENT = "Computer Science and Engineering (Data Science)"
COLLEGE = "B V RAJU INSTITUTE OF TECHNOLOGY"
ADDRESS = "Vishnupur, Narsapur, Medak, Telangana, India 502313"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_text(cell, text: str, bold: bool = False, size: float = 10) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.bold = bold
    r.font.name = "Times New Roman"
    r.font.size = Pt(size)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr)
    run._r.append(fld_char2)
    run.font.name = "Times New Roman"
    run.font.size = Pt(10)


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
        add_page_number(section.footer.paragraphs[0])
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

    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 12)):
        style = doc.styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True
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


def p(doc: Document, text: str, *, align=None, indent=True, after=6, bold=False, size=12):
    para = doc.add_paragraph()
    para.alignment = align or WD_ALIGN_PARAGRAPH.JUSTIFY
    para.paragraph_format.line_spacing = 1.5
    para.paragraph_format.space_after = Pt(after)
    para.paragraph_format.first_line_indent = Inches(0.3) if indent and align != WD_ALIGN_PARAGRAPH.CENTER else Inches(0)
    run = para.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.bold = bold
    return para


def chapter(doc: Document, number: int, title: str) -> None:
    doc.add_page_break()
    p(doc, f"CHAPTER-{number}", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=6, bold=True, size=14)
    p(doc, title.upper(), align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=12, bold=True, size=14)


def heading(doc: Document, text: str, level: int = 2) -> None:
    para = doc.add_paragraph(style=f"Heading {level}")
    para.paragraph_format.first_line_indent = Inches(0)
    para.add_run(text)


def table(doc: Document, caption: str, headers: list[str], rows: list[list[str]]) -> None:
    p(doc, caption, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=6, bold=True, size=11)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, value in enumerate(headers):
        set_cell_text(t.rows[0].cells[i], value, bold=True)
        set_cell_shading(t.rows[0].cells[i], "D9EAF7")
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
    run = box.add_run(f"[INSERT FIGURE {number} HERE]\n\nFIGURE SPACE RESERVED")
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(90, 90, 90)
    boxPr = OxmlElement("w:pBdr")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "8")
        el.set(qn("w:space"), "6")
        el.set(qn("w:color"), "B7B7B7")
        boxPr.append(el)
    box._p.get_or_add_pPr().append(boxPr)
    box.paragraph_format.line_spacing = height
    p(doc, f"Figure {number}: {caption}", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=8, size=11)


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

    doc.add_page_break()
    p(doc, COLLEGE, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=4, bold=True, size=13)
    p(doc, ADDRESS, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=18, size=11)
    p(doc, "BONAFIDE CERTIFICATE", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=18, bold=True, size=14)
    p(doc, f'This is to certify that this major project work entitled "{TITLE}", submitted by MOGULOJU ABHIRAM ({STUDENTS[0][1]}) and RAJULAPUDI ROHITH ({STUDENTS[1][1]}) to B V Raju Institute of Technology affiliated to JNTUH, Hyderabad, in partial fulfillment for the award of Bachelor of Technology in Computer Science and Engineering (Data Science), is a bonafide record of project work carried out under my supervision during the academic year 2025 - 2026 and that this work has not been submitted elsewhere for a degree.', after=36)
    table(doc, "", ["Supervisor", "Head of the Department"], [[f"{GUIDE}\nAssistant Professor", "Dr. R. V. Ramana Chary\nProfessor"]])
    p(doc, "Project Coordinator: Mr. Purnachandrarao Murala, Assistant Professor, CSE (Data Science)", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=32, size=11)
    p(doc, "Internal Examiner                         External Examiner", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=0, bold=True, size=11)

    doc.add_page_break()
    p(doc, COLLEGE, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=4, bold=True, size=13)
    p(doc, "DECLARATION", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=18, bold=True, size=14)
    p(doc, f'We hereby declare that the project titled "{TITLE}", submitted to B V Raju Institute of Technology (Autonomous) and affiliated with JNTUH, Hyderabad, in partial fulfillment of the requirements for the award of a Bachelor of Technology in Computer Science and Engineering (Data Science), represents our work and ideas in our own words. Wherever other authors\' ideas, methods, software, datasets, or words have been used, the original sources have been acknowledged through appropriate citations and references. We further declare that no claim of differential privacy, secure aggregation, formal privacy guarantee, or production deployment is made beyond the capabilities verified in the current implementation. We have adhered to the principles of academic honesty and integrity and have not fabricated or falsified any technical result.', after=18)
    p(doc, "Signatures:\n\n\nMOGULOJU ABHIRAM                         RAJULAPUDI ROHITH\n\nPlace: ____________________              Date: ____________________", indent=False, after=0)

    doc.add_page_break()
    p(doc, COLLEGE, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=4, bold=True, size=13)
    p(doc, "ACKNOWLEDGEMENT", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=18, bold=True, size=14)
    p(doc, "We express our sincere thanks to the Principal of B V Raju Institute of Technology for providing the facilities and academic environment required to complete this major project.")
    p(doc, "We are grateful to Dr. R. V. Ramana Chary, Professor and Head of the Department of Computer Science and Engineering (Data Science), for the support, review, and encouragement provided throughout the project work.")
    p(doc, "We thank Mr. Purnachandrarao Murala, Assistant Professor and Project Coordinator, for coordinating the project activities and providing timely suggestions during the development and documentation stages.")
    p(doc, f"We are especially thankful to our internal guide, {GUIDE}, Assistant Professor, Department of Computer Science and Engineering (Data Science), for her continuous guidance, technical feedback, and encouragement throughout the project.")
    p(doc, "Finally, we thank all faculty members, staff, parents, and friends who supported us directly or indirectly in completing this work.")

    doc.add_page_break()
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
    p(doc, "LIST OF FIGURES", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14, bold=True, size=14)
    figs = [
        "4.1 Overall System Architecture of FedRouteAI", "4.2 Federated Learning Architecture", "4.3 Regional Client Architecture", "4.4 End-to-End Data Pipeline", "4.5 Geo V2 Feature Pipeline", "4.6 Historical Traffic Memory", "4.7 OSM/PostGIS Road-Network Architecture", "4.8 Directed Road Network and Transitions", "4.9 Backend Service Architecture", "4.10 Frontend Architecture", "4.11 Directed Shortest-Path Routing", "5.1 Live GPS Ingestion Pipeline", "5.2 Dynamic Traffic Map", "5.3 Moving Vehicle Visualization", "5.4 Route-Bound Demonstration Flow", "5.5 Normal Traffic Demonstration", "5.6 Congestion Demonstration", "5.7 Accident Demonstration", "6.1 Model Validation Results", "6.2 Confusion Matrix", "6.3 Testing Evidence", "7.1 Local Deployment Architecture",
    ]
    for i, item in enumerate(figs, 1): p(doc, f"Figure {item:<55}{'—'}", indent=False, after=3, size=11)
    doc.add_page_break()
    p(doc, "LIST OF TABLES", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14, bold=True, size=14)
    tables = ["3.1 Functional Requirements", "3.2 Non-Functional Requirements", "3.3 Software and Hardware Requirements", "4.1 Geo V2 Feature Contract", "4.2 OSM/PostGIS Network Statistics", "5.1 Major Software Modules", "5.2 Federated Client Configuration", "5.3 API and Data Flow Summary", "6.1 Verification Summary", "6.2 Frozen Model Results", "7.1 Runtime Performance Evidence", "7.2 Current Limitations"]
    for item in tables: p(doc, f"Table {item}", indent=False, after=4, size=11)
    doc.add_page_break()
    p(doc, "LIST OF ABBREVIATIONS / SYMBOLS", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False, after=14, bold=True, size=14)
    table(doc, "", ["Abbreviation / Symbol", "Meaning"], [["AI", "Artificial Intelligence"], ["API", "Application Programming Interface"], ["FL", "Federated Learning"], ["FedAvg", "Federated Averaging"], ["GPS", "Global Positioning System"], ["MLP", "Multilayer Perceptron"], ["OSM", "OpenStreetMap"], ["PostGIS", "PostgreSQL spatial database extension"], ["REST", "Representational State Transfer"], ["GIS", "Geographic Information System"], ["FPR", "False Positive Rate"], ["F1", "Harmonic mean of precision and recall"], ["V1 / V2", "Version 1 / Geo V2 system contracts"], ["km/h", "Kilometres per hour"], ["m", "Metres"]])


def start_main_numbering(doc: Document) -> None:
    section = doc.add_section(WD_SECTION.CONTINUOUS)
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.5)
    section.footer_distance = Inches(0.5)
    add_page_number(section.footer.paragraphs[0])
    pg_num_type = OxmlElement("w:pgNumType")
    pg_num_type.set(qn("w:fmt"), "decimal")
    pg_num_type.set(qn("w:start"), "1")
    section._sectPr.append(pg_num_type)


def main_content(doc: Document) -> None:
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
