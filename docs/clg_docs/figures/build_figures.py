from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

try:
    import fitz
except ModuleNotFoundError:  # ReportLab fallback keeps the figure build portable.
    fitz = None
from reportlab.graphics import renderPDF, renderPM
from svglib.svglib import svg2rlg


ROOT = Path(__file__).resolve().parent
SVG = ROOT / "svg"
PNG = ROOT / "png"
PDF = ROOT / "pdf"
for directory in (SVG, PNG, PDF):
    directory.mkdir(parents=True, exist_ok=True)


STYLE = """<style>
.title{font-family:'Times New Roman',serif;font-weight:700;font-size:22px;fill:#000}
.head{font-family:'Times New Roman',serif;font-weight:700;font-size:15px;fill:#000}
.body{font-family:'Times New Roman',serif;font-size:13px;fill:#000}
.small{font-family:'Times New Roman',serif;font-size:11px;fill:#000}
.box{fill:#fff;stroke:#000;stroke-width:2}
.dash{fill:#fff;stroke:#000;stroke-width:2;stroke-dasharray:8 6}
.arrow{stroke:#000;stroke-width:2;fill:none;marker-end:url(#arrow)}
</style>"""


def svg(name: str, width: int, height: int, body: str) -> None:
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="4" orient="auto"><path d="M0 0 L9 4 L0 8 Z" fill="#000"/></marker></defs>{STYLE}{body}</svg>'''
    target = SVG / f"{name}.svg"
    target.write_text(content, encoding="utf-8")
    drawing = svg2rlg(str(target))
    pdf_target = PDF / f"{name}.pdf"
    renderPDF.drawToFile(drawing, str(pdf_target))
    png_target = PNG / f"{name}.png"
    if fitz is not None:
        page = fitz.open(pdf_target)[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
        pixmap.save(str(png_target))
    else:
        renderPM.drawToFile(drawing, str(png_target), fmt="PNG", dpi=144)


def text_lines(x: int, y: int, lines: list[str], cls: str = "body", anchor: str = "middle", gap: int = 16) -> str:
    return "".join(
        f'<text x="{x}" y="{y + i * gap}" text-anchor="{anchor}" class="{cls}">{escape(line)}</text>'
        for i, line in enumerate(lines)
    )


def panel(x: int, y: int, w: int, h: int, title: str, lines: list[str], kind: str = "box") -> str:
    fill = {"blue": "#e8eef2", "gray": "#f2f2f2", "warm": "#f4eee5", "dash": "#fff"}.get(kind, "#fff")
    stroke = "dash" if kind == "dash" else "box"
    body = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" class="{stroke}" style="fill:{fill}"/>'
    body += text_lines(x + w // 2, y + 24, [title], "head")
    body += text_lines(x + w // 2, y + 48, lines, "small", gap=15)
    return body


def box(x: int, y: int, w: int, h: int, title: str, lines: list[str], dashed: bool = False) -> str:
    """Compatibility wrapper for the unchanged validation figures."""
    return panel(x, y, w, h, title, lines, "dash" if dashed else "box")


def group(x: int, y: int, w: int, h: int, title: str, kind: str = "dash") -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" class="{kind}" fill="none"/><text x="{x+14}" y="{y+22}" class="head">{escape(title)}</text>'


def arrow(x1: int, y1: int, x2: int, y2: int, label: str = "") -> str:
    body = f'<path d="M{x1} {y1} L{x2} {y2}" class="arrow"/>'
    if label:
        body += text_lines((x1 + x2) // 2, (y1 + y2) // 2 - 7, [label], "small")
    return body


def title_block(title: str, subtitle: str = "", width: int = 1600) -> str:
    body = text_lines(width // 2, 32, [title], "title")
    if subtitle:
        body += text_lines(width // 2, 55, [subtitle], "small")
    return body


def overall() -> None:
    body = title_block("Overall System Architecture of FedRouteAI", "Runtime inference, federated training, canonical network services, and presentation are separated by responsibility.")
    body += group(25, 75, 430, 475, "A. TELEMETRY AND SPATIAL STATE")
    body += panel(50, 115, 180, 76, "GPS / live telemetry", ["validated batches", "source_id, run_id, timestamp"], "blue")
    body += panel(250, 115, 180, 76, "Segment association", ["canonical segment", "continuity + geometry"], "blue")
    body += arrow(230, 153, 250, 153)
    body += panel(50, 225, 180, 76, "Traffic aggregation", ["time-window state", "speed, count, occupancy"], "blue")
    body += panel(250, 225, 180, 76, "Historical memory", ["normal prehistory", "causal prior rows"], "blue")
    body += arrow(140, 191, 140, 225); body += arrow(340, 191, 340, 225)
    body += panel(50, 335, 180, 76, "Canonical network", ["OSM-derived geometry", "metadata + directed edges"], "warm")
    body += panel(250, 335, 180, 76, "PostgreSQL + PostGIS", ["pings, states, events", "segments, transitions"], "warm")
    body += arrow(140, 301, 140, 335); body += arrow(340, 301, 340, 335)
    body += panel(50, 445, 380, 76, "Network identity", ["beeramguda-osm-20260506", "shared by association, spatial context, map, routing"], "gray")
    body += arrow(240, 411, 240, 445)

    body += group(485, 75, 510, 475, "B. GEO V2 RUNTIME INFERENCE")
    body += panel(515, 115, 210, 78, "Feature construction", ["history_spatial_strong", "current + history + neighbor"], "blue")
    body += panel(755, 115, 210, 78, "Ordered contract", ["23 features", "label-free input"], "gray")
    body += arrow(725, 154, 755, 154)
    body += panel(515, 230, 210, 78, "Artifact validation", ["feature order + scaler", "metadata compatibility"], "gray")
    body += panel(755, 230, 210, 78, "Frozen Geo V2 MLP", ["8 classes", "evaluation mode"], "blue")
    body += arrow(620, 193, 620, 230); body += arrow(860, 193, 860, 230)
    body += arrow(725, 269, 755, 269)
    body += panel(515, 345, 210, 78, "Prediction state", ["probabilities + status", "events / coverage"], "blue")
    body += panel(755, 345, 210, 78, "Persistence", ["prediction records", "live snapshot"], "warm")
    body += arrow(620, 308, 620, 345); body += arrow(860, 308, 860, 345)
    body += arrow(725, 384, 755, 384)
    body += panel(515, 460, 450, 64, "FastAPI service boundary", ["prediction, ingest, events, segments, metrics, demo"], "gray")
    body += arrow(740, 423, 740, 460)

    body += group(1005, 75, 570, 475, "C. FEDERATED TRAINING AND DELIVERY")
    body += panel(1035, 115, 230, 78, "REGION_01 ... REGION_08", ["regional data remains local", "local preprocessing + MLP"], "blue")
    body += panel(1315, 115, 230, 78, "Local updates", ["parameters + metadata", "no raw GPS upload"], "blue")
    body += arrow(1265, 154, 1315, 154)
    body += panel(1035, 230, 230, 78, "Adaptive FedAvg family", ["server-side aggregation", "bounded client weighting"], "gray")
    body += panel(1315, 230, 230, 78, "Global candidate", ["round history", "validation selection"], "gray")
    body += arrow(1150, 193, 1150, 230); body += arrow(1430, 193, 1430, 230)
    body += arrow(1265, 269, 1315, 269)
    body += panel(1035, 345, 510, 78, "Versioned deployment artifact", ["selected checkpoint + scaler + schema + provenance", "runtime loads only compatible artifact"], "warm")
    body += arrow(1290, 308, 1290, 345)
    body += panel(1035, 460, 510, 64, "Distribution", ["global parameters/checkpoint available to regional clients and runtime"], "blue")
    body += arrow(1290, 423, 1290, 460)
    body += '<path d="M1035 492 L985 492 L985 154 L965 154" class="arrow"/>'
    body += text_lines(1000, 485, ["artifact"], "small")
    body += text_lines(800, 580, ["Presentation and routing consume persisted state and canonical network services; routing is not ML inference."], "small")
    svg("fig_4_1_overall_architecture", 1600, 610, body)


def federated() -> None:
    body = title_block("Federated Learning Architecture", "Eight geographic clients compute locally; only model updates and training metadata cross the aggregation boundary.")
    body += group(25, 78, 610, 480, "REGIONAL CLIENTS: LOCAL DATA AND LOCAL TRAINING")
    for i in range(8):
        col, row = i % 2, i // 2
        x, y = 55 + col * 285, 115 + row * 92
        body += panel(x, y, 250, 68, f"REGION_{i+1:02d}", ["regional telemetry/history", "Geo V2 features -> local MLP"], "blue")
        body += arrow(x + 125, y + 68, 720, 260)
    body += group(685, 78, 430, 480, "SERVER-SIDE FEDERATED COORDINATION")
    body += panel(725, 125, 350, 82, "Receive client updates", ["parameter arrays + sample counts", "quality/round metadata"], "gray")
    body += panel(725, 245, 350, 96, "Adaptive FedAvg aggregation", ["FedAvg-family parameter aggregation", "adaptive weighting as implemented", "no raw GPS records"], "warm")
    body += arrow(900, 207, 900, 245)
    body += panel(725, 385, 350, 82, "Global model candidate", ["round checkpoint + validation metrics", "select deployment candidate"], "gray")
    body += arrow(900, 341, 900, 385)
    body += group(1165, 78, 410, 480, "MODEL DISTRIBUTION")
    body += panel(1200, 145, 340, 90, "Selected global artifact", ["state_dict + scaler + feature schema", "network/model version + provenance"], "warm")
    body += arrow(1075, 426, 1200, 190)
    body += panel(1200, 300, 340, 82, "Runtime Geo V2 ModelStore", ["compatibility validation", "fail-closed loading"], "blue")
    body += arrow(1370, 235, 1370, 300)
    body += panel(1200, 435, 340, 82, "Next-round regional sync", ["distribute parameters", "clients continue local training"], "blue")
    body += arrow(1370, 382, 1370, 435)
    body += '<path d="M1200 476 L1115 476 L1115 120 L635 120" class="arrow"/>'
    body += text_lines(1120, 466, ["parameters only"], "small")
    svg("fig_4_2_federated_learning", 1600, 600, body)


def regional() -> None:
    body = title_block("Regional Client and Server Interaction", "The training lifecycle is split into an explicit client boundary and an aggregation server boundary.")
    body += group(25, 85, 700, 470, "CLIENT PROCESS: ONE REGION")
    body += panel(55, 130, 280, 76, "Regional dataset", ["local feature tables", "labels used only for training/evaluation"], "blue")
    body += panel(390, 130, 280, 76, "Preprocess + feature build", ["normalization", "Geo V2 ordered 23-feature rows"], "blue")
    body += arrow(335, 168, 390, 168)
    body += panel(55, 250, 280, 76, "Local MLP", ["local epochs", "class-aware training configuration"], "blue")
    body += panel(390, 250, 280, 76, "Evaluation", ["local metrics", "sample count + metadata"], "gray")
    body += arrow(195, 206, 195, 250); body += arrow(530, 206, 530, 250)
    body += panel(220, 380, 280, 82, "Client update", ["model parameter arrays", "no raw regional rows"], "warm")
    body += arrow(335, 288, 335, 380)
    body += panel(55, 490, 615, 42, "Receive global parameters for the next round", [], "gray")
    body += '<path d="M500 462 L620 462 L620 511 L670 511" class="arrow"/>'
    body += group(785, 85, 790, 470, "SERVER PROCESS: FEDERATED COORDINATION")
    body += panel(825, 135, 300, 76, "Collect updates", ["all participating region updates", "round and quality metadata"], "gray")
    body += panel(1200, 135, 300, 76, "Aggregate parameters", ["FedAvg-family / adaptive aggregation", "bounded weights as configured"], "warm")
    body += arrow(1125, 173, 1200, 173)
    body += panel(825, 265, 675, 78, "Global model", ["candidate checkpoint, validation selection, artifact metadata"], "blue")
    body += arrow(1350, 211, 1350, 265)
    body += panel(825, 395, 300, 76, "Persist round state", ["round record + metrics", "checkpoint history"], "gray")
    body += panel(1200, 395, 300, 76, "Synchronize clients", ["global parameters", "next local round"], "blue")
    body += arrow(1350, 343, 975, 395); body += arrow(1350, 343, 1350, 395)
    body += '<path d="M1200 433 L750 433 L750 511 L670 511" class="arrow"/>'
    svg("fig_4_3_regional_client_server", 1600, 600, body)


def end_to_end() -> None:
    body = title_block("End-to-End Data Pipeline", "Runtime telemetry becomes persisted traffic state and a label-free prediction; routing follows a separate directed-network branch.")
    body += group(25, 82, 1060, 250, "RUNTIME INGESTION AND PREDICTION")
    labels = [
        ("GPS telemetry", ["batch validation", "timestamp + source"]),
        ("Segment association", ["canonical OSM/PostGIS", "geometry continuity"]),
        ("Time-window state", ["speed/count/occupancy", "segment projection"]),
        ("Historical memory", ["normal baselines", "causal prior rows"]),
        ("Geo V2 features", ["history_spatial_strong", "ordered 23 features"]),
        ("Artifact + MLP", ["compatibility check", "8-class label-free inference"]),
        ("Prediction state", ["persist result", "live snapshot/API"]),
    ]
    for i, (head, lines) in enumerate(labels):
        x = 50 + i * 145
        body += panel(x, 145, 125, 110, head, lines, "blue" if i in (0, 4, 5) else "gray")
        if i < len(labels) - 1: body += arrow(x + 125, 200, x + 145, 200)
    body += group(25, 365, 1060, 170, "SEPARATE ROUTE BRANCH")
    body += panel(60, 415, 210, 76, "Origin / destination", ["validated coordinates"], "warm")
    body += panel(330, 415, 210, 76, "Directed graph", ["canonical segments", "persisted transitions"], "warm")
    body += panel(600, 415, 210, 76, "Shortest route", ["distance-based default", "event/exclusion inspection"], "warm")
    body += panel(870, 415, 180, 76, "Route response", ["ordered IDs + geometry"], "warm")
    body += arrow(270, 453, 330, 453); body += arrow(540, 453, 600, 453); body += arrow(810, 453, 870, 453)
    body += group(1135, 82, 440, 453, "PRESENTATION AND CONTROL SURFACES")
    body += panel(1170, 135, 370, 82, "FastAPI endpoints", ["ingest | prediction | events", "segments | routes | demo | metrics"], "gray")
    body += panel(1170, 270, 370, 82, "React + Leaflet", ["network, vehicles, traffic, events", "predictions, routes, live scenarios"], "blue")
    body += arrow(1355, 217, 1355, 270)
    body += panel(1170, 405, 370, 82, "Reportable state", ["API snapshots and route responses", "no labels in runtime feature input"], "gray")
    body += arrow(1355, 352, 1355, 405)
    svg("fig_4_4_end_to_end_pipeline", 1600, 580, body)


def features() -> None:
    body = title_block("Geo V2 Feature Construction Pipeline", "Promoted variant: history_spatial_strong | feature_version: geo-v2-history_spatial_strong-23-v2 | runtime input is label-free.")
    groups = [
        ("CURRENT TRAFFIC", ["avg_speed_kmph", "speed_std_kmph", "vehicle_count", "occupancy", "flow_rate_vph", "stopped_fraction"]),
        ("TEMPORAL ENCODINGS", ["hour_sin", "hour_cos"]),
        ("ROAD METADATA", ["road_type_code", "lane_count", "max_speed_kmph"]),
        ("NORMAL BASELINES", ["baseline_speed_kmph", "baseline_speed_std_kmph", "baseline_vehicle_count"]),
        ("BASELINE DEVIATIONS", ["speed_to_baseline", "count_to_baseline", "std_to_baseline"]),
        ("PRIOR-WINDOW STATISTICS", ["prior_speed_mean_3", "prior_count_mean_3"]),
        ("TRENDS", ["speed_trend", "count_trend"]),
        ("LOW-SPEED PERSISTENCE", ["low_speed_persistence_3"]),
        ("DIRECTED NEIGHBOR CONTEXT", ["neighbor_speed_delta"]),
    ]
    for i, (head, lines) in enumerate(groups):
        col, row = i % 3, i // 3
        x, y = 35 + col * 365, 90 + row * 105
        body += panel(x, y, 330, 82, head, lines, "blue" if i in (0, 8) else "gray")
    body += arrow(800, 410, 800, 450)
    body += panel(450, 450, 700, 75, "EXACT ORDERED 23-FEATURE VECTOR", ["current state + temporal + road metadata + baselines + deviations", "prior windows + trends + persistence + directed neighbor_speed_delta"], "warm")
    body += arrow(800, 525, 800, 565)
    body += panel(450, 565, 700, 72, "MODEL INPUT VALIDATION AND SCALING", ["feature order, finite values, positive scaler, metadata compatibility", "forbidden runtime fields: labels, scenarios, event IDs, vehicle IDs, severity"], "gray")
    body += arrow(800, 637, 800, 677)
    body += panel(450, 677, 700, 78, "FROZEN GEOV2MLP", ["input = 23 ordered values | evaluation mode", "8-class probabilities: normal, congestion, construction, flood, road_block, road_damage, accident, diversion"], "blue")
    svg("fig_4_5_geo_v2_features", 1600, 800, body)


def history() -> None:
    body = title_block("Historical Traffic Memory and Causal Windows", "Baseline construction uses normal prehistory; each prediction reads only shifted prior windows and current context.")
    body += group(40, 90, 1520, 215, "TEMPORAL RECORDS FOR ONE SEGMENT")
    xs = [100, 340, 580, 820, 1060, 1300]
    names = [("normal prehistory", "baseline source"), ("baseline", "mean/std/count"), ("t-3", "prior window"), ("t-2", "prior window"), ("t-1", "prior window"), ("CURRENT t", "inference state")]
    for i, (head, sub) in enumerate(names):
        body += panel(xs[i], 150, 180, 86, head, [sub], "warm" if i == 5 else "blue")
        if i < len(xs)-1: body += arrow(xs[i] + 180, 193, xs[i+1], 193)
    body += text_lines(800, 275, ["shifted causal window: t-3, t-2, t-1 -> current t"], "small")
    body += group(40, 345, 730, 245, "FEATURE MEMORY BUILD")
    body += panel(75, 405, 285, 92, "Normal prehistory filter", ["known normal windows", "exclude current event windows"], "blue")
    body += panel(445, 405, 285, 92, "Baseline aggregation", ["speed / variability / count", "segment and time context"], "gray")
    body += arrow(360, 451, 445, 451)
    body += panel(260, 525, 330, 44, "Persist historical memory rows", [], "warm")
    body += arrow(587, 497, 425, 525)
    body += group(815, 345, 745, 245, "CAUSALITY GUARANTEE")
    body += panel(850, 405, 300, 92, "Allowed for prediction at t", ["historical baseline", "t-3, t-2, t-1", "current telemetry"], "blue")
    body += panel(1200, 405, 320, 92, "Excluded from prediction at t", ["future windows", "current/future abnormal values", "labels or scenario names"], "gray")
    body += arrow(1150, 451, 1200, 451, "no future leakage")
    body += text_lines(800, 650, ["The runtime cache supplements request-order history; durable database rows remain the source of prior context."], "small")
    svg("fig_4_6_historical_memory", 1600, 690, body)


def network_import() -> None:
    body = title_block("OSM/PostGIS Network Import", "OSM supplies road structure, geometry, metadata, and topology; it is not the ML training dataset.")
    body += group(35, 90, 530, 430, "INGEST AND NORMALIZE")
    body += panel(70, 145, 210, 82, "OpenStreetMap source", ["road geometry", "road attributes"], "blue")
    body += panel(320, 145, 210, 82, "Cached road data", ["repeatable import input", "network source identity"], "gray")
    body += arrow(280, 186, 320, 186)
    body += panel(70, 280, 210, 82, "Network normalization", ["canonical segment IDs", "road metadata"], "warm")
    body += panel(320, 280, 210, 82, "Directed topology", ["legal transitions", "one-way direction"], "warm")
    body += arrow(175, 227, 175, 280); body += arrow(425, 227, 425, 280)
    body += panel(155, 415, 310, 64, "Canonical network manifest", ["beeramguda-osm-20260506"], "gray")
    body += arrow(280, 362, 280, 415)
    body += group(625, 90, 935, 430, "POSTGIS PERSISTENCE AND SHARED CONSUMERS")
    body += panel(665, 150, 280, 96, "PostgreSQL + PostGIS", ["segments and geometry", "metadata and transitions", "spatial indexes"], "warm")
    body += arrow(565, 447, 665, 198)
    consumers = [("Segment association", "GPS -> canonical segment", 1030, 125), ("Spatial feature context", "directed neighbor speed", 1300, 125), ("Map rendering", "geometry + live state", 1030, 305), ("Directed routing", "graph + transitions", 1300, 305)]
    for head, sub, x, y in consumers:
        body += panel(x, y, 220, 82, head, [sub], "blue")
        body += arrow(945, 198, x, y + 41)
    body += text_lines(1090, 475, ["The canonical network is the shared spatial reference for ML context, persistence, map display, and routing."], "small")
    svg("fig_4_7_osm_postgis", 1600, 570, body)


def topology() -> None:
    body = title_block("Directed Road Network and Transitions", "A transition is a persisted directed relationship between canonical segment IDs; reverse movement is a separate edge when present.")
    body += group(35, 90, 1010, 430, "DIRECTED SEGMENT GRAPH")
    body += panel(100, 180, 210, 100, "SEG_A_104", ["geometry + metadata", "outgoing: B, D"], "blue")
    body += panel(430, 130, 210, 100, "SEG_B_105", ["geometry + metadata", "outgoing: C"], "blue")
    body += panel(430, 300, 210, 100, "SEG_D_220", ["alternative branch", "outgoing: E"], "blue")
    body += panel(760, 180, 210, 100, "SEG_C_106", ["candidate path", "outgoing: terminal"], "blue")
    body += panel(760, 350, 210, 100, "SEG_E_221", ["alternative path", "outgoing: C"], "blue")
    body += arrow(310, 210, 430, 180, "A -> B")
    body += arrow(310, 240, 430, 350, "A -> D")
    body += arrow(640, 180, 760, 210, "B -> C")
    body += arrow(640, 350, 760, 400, "D -> E")
    body += arrow(970, 400, 1010, 250, "E -> C")
    body += group(1090, 90, 470, 430, "GRAPH CONSEQUENCES")
    body += panel(1125, 150, 400, 90, "Legal traversal", ["routing follows stored directed transitions", "missing reverse edge means no reverse traversal"], "gray")
    body += panel(1125, 285, 400, 90, "Shared topology", ["OSM/PostGIS network version", "neighbor context uses directed adjacency"], "warm")
    body += panel(1125, 420, 400, 64, "Current network evidence", ["2,968 canonical segments | 11,259 directed transitions"], "blue")
    svg("fig_4_8_directed_network", 1600, 570, body)


def backend_layers() -> None:
    body = title_block("Backend Service and Repository Layers", "One-directional ownership keeps request parsing, business rules, database access, and models separate.")
    body += group(40, 90, 850, 470, "BACKEND REQUEST PATH")
    body += panel(80, 145, 350, 82, "API / endpoint layer", ["FastAPI routers and schemas", "parse request -> call service"], "blue")
    body += panel(500, 145, 350, 82, "Service layer", ["ingestion | Geo V2 prediction", "routing | demo | federated status"], "warm")
    body += arrow(430, 186, 500, 186)
    body += panel(80, 285, 350, 82, "Repository layer", ["GeoV2Repository", "segment/event/ping/live repositories"], "gray")
    body += panel(500, 285, 350, 82, "ML subsystem", ["feature contract + model store", "artifact validation + inference"], "blue")
    body += arrow(675, 227, 675, 285); body += arrow(255, 227, 255, 285)
    body += panel(80, 425, 350, 82, "Models and schemas", ["SQLAlchemy database models", "Pydantic API contracts"], "gray")
    body += panel(500, 425, 350, 82, "Routing graph cache", ["canonical directed graph", "distance-based shortest path"], "warm")
    body += arrow(255, 367, 255, 425); body += arrow(675, 367, 675, 425)
    body += group(950, 90, 610, 470, "PERSISTENCE AND EXTERNAL EFFECTS")
    body += panel(990, 155, 530, 90, "PostgreSQL + PostGIS", ["GPS pings | live ingestion | historical memory", "events | predictions | segments | directed transitions"], "warm")
    body += arrow(850, 466, 990, 200)
    body += panel(990, 300, 250, 82, "React/Leaflet API", ["live snapshot", "map + route responses"], "blue")
    body += panel(1270, 300, 250, 82, "Federated process", ["regional clients", "aggregation/status"], "blue")
    body += arrow(850, 186, 990, 341); body += arrow(850, 186, 1270, 341)
    body += panel(990, 435, 530, 64, "Layering rule", ["endpoint never bypasses service/repository ownership; business logic stays in services"], "gray")
    svg("fig_4_9_backend_architecture", 1600, 600, body)


def frontend() -> None:
    body = title_block("Frontend Map and API Interaction", "React owns presentation state; inference, persistence, network topology, and routing remain backend responsibilities.")
    body += group(35, 90, 590, 460, "REACT APPLICATION")
    body += panel(70, 145, 240, 80, "React application", ["scenario controls", "live state + route state"], "blue")
    body += panel(350, 145, 240, 80, "API client", ["typed requests", "polling / action endpoints"], "gray")
    body += arrow(310, 185, 350, 185)
    body += panel(70, 280, 240, 96, "Leaflet map", ["road network layer", "vehicles + traffic state", "predictions + events"], "blue")
    body += panel(350, 280, 240, 96, "Route / demo views", ["ordered route geometry", "coverage + inspection", "live vehicle visualization"], "blue")
    body += arrow(190, 225, 190, 280); body += arrow(470, 225, 470, 280)
    body += panel(160, 430, 300, 64, "Presentation state", ["map layers compose API snapshots; no model logic in UI"], "gray")
    body += arrow(330, 376, 310, 430)
    body += group(685, 90, 875, 460, "BACKEND API AND DATA SERVICES")
    body += panel(725, 145, 360, 82, "FastAPI endpoints", ["live map | ingest | prediction | events", "segments | routes | Geo V2 demo"], "gray")
    body += panel(1150, 145, 360, 82, "Backend services", ["feature/inference | repositories", "directed routing | snapshot assembly"], "warm")
    body += arrow(1085, 186, 1150, 186)
    body += panel(725, 285, 360, 96, "Live and prediction responses", ["vehicles, segment state, events", "probabilities, confidence, coverage"], "blue")
    body += panel(1150, 285, 360, 96, "Network and route responses", ["canonical geometry + metadata", "ordered IDs, distance, duration"], "blue")
    body += arrow(905, 227, 905, 285); body += arrow(1330, 227, 1330, 285)
    body += panel(915, 440, 360, 64, "Leaflet layer update", ["network | traffic | vehicles | predictions | events | routes"], "gray")
    body += arrow(1085, 381, 1095, 440)
    svg("fig_4_10_frontend_architecture", 1600, 600, body)


def routing() -> None:
    body = title_block("Directed Shortest-Path Routing", "Default cost is distance on the canonical directed network; Geo V2 predictions support inspection/coverage and explicit event penalties, not learned route optimization.")
    body += group(35, 90, 1030, 430, "ROUTE COMPUTATION")
    body += panel(70, 160, 205, 92, "Origin + destination", ["validated coordinates", "network version"], "blue")
    body += panel(335, 160, 205, 92, "Snap to segments", ["nearest canonical geometry", "start/end segment IDs"], "gray")
    body += panel(600, 160, 205, 92, "Directed graph", ["segments + transitions", "cached by network identity"], "warm")
    body += panel(865, 160, 165, 92, "Dijkstra / A*", ["distance cost", "legal edges"], "warm")
    body += arrow(275, 206, 335, 206); body += arrow(540, 206, 600, 206); body += arrow(805, 206, 865, 206)
    body += panel(220, 315, 250, 92, "Ordered segment IDs", ["directed path result", "transition order preserved"], "blue")
    body += panel(520, 315, 250, 92, "Route geometry", ["ordered OSM segment geometry", "map-ready polyline"], "blue")
    body += panel(820, 315, 210, 92, "Distance + duration", ["response metrics", "route inspection"], "gray")
    body += arrow(947, 252, 345, 315); body += arrow(470, 361, 520, 361); body += arrow(770, 361, 820, 361)
    body += group(1110, 90, 450, 430, "PREDICTION-AWARE INSPECTION")
    body += panel(1145, 160, 380, 92, "Latest prediction coverage", ["covered segments", "abnormal segment count", "warnings"], "blue")
    body += panel(1145, 300, 380, 92, "Separate optional behavior", ["active-event penalties / explicit exclusions", "recommended route around known events"], "warm")
    body += arrow(1335, 252, 1335, 300)
    body += text_lines(1335, 460, ["No claim that the MLP directly learns route cost."], "small")
    svg("fig_4_11_routing", 1600, 570, body)


def live_ingestion() -> None:
    body = title_block("Live GPS Ingestion Pipeline", "Append-only telemetry history is separated from the current segment-state projection used by live snapshots.")
    body += group(35, 90, 1030, 440, "LIVE INGESTION AND PREDICTION")
    steps = [("Telemetry batch", ["one device trajectory", "GPS observations"]), ("Validation", ["schema + coordinates", "receipt / run identity"]), ("Append history", ["persist GPS pings", "audit trail"]), ("Segment state", ["map-match", "current segment projection"]), ("Aggregate", ["time-window traffic", "speed/count features"]), ("Geo V2 inference", ["history + spatial context", "23 ordered label-free values"]), ("Snapshot", ["prediction persistence", "vehicles/events/map state"])]
    for i, (head, lines) in enumerate(steps):
        x = 55 + (i % 4) * 245; y = 145 + (i // 4) * 145
        body += panel(x, y, 205, 90, head, lines, "blue" if i in (0, 5, 6) else "gray")
        if i in (0, 1, 2): body += arrow(x + 205, y + 45, x + 245, y + 45)
        if i == 3: body += arrow(x + 205, y + 45, x + 245, y + 45)
    body += arrow(1020, 190, 1020, 290)
    body += arrow(260, 235, 260, 290)
    body += panel(55, 335, 430, 82, "Append-only telemetry path", ["raw GPS pings remain historical records", "used for replay, memory building, and audit"], "warm")
    body += panel(570, 335, 430, 82, "Current-state projection", ["latest segment traffic/prediction state", "served by scoped live snapshots"], "blue")
    body += text_lines(800, 485, ["Background orchestration may trigger detection; runtime inference does not consume event labels or scenario names."], "small")
    body += group(1110, 90, 450, 440, "PERSISTED OUTPUTS")
    body += panel(1145, 160, 380, 92, "PostgreSQL + PostGIS", ["gps_pings | live_ingestion", "historical_memory | predictions", "events | segments"], "warm")
    body += panel(1145, 315, 380, 92, "API snapshot", ["map geometry + vehicles", "traffic state + predictions", "event and route state"], "blue")
    body += arrow(1335, 252, 1335, 315)
    svg("fig_5_1_live_ingestion", 1600, 570, body)


def deployment() -> None:
    body = title_block("Local Deployment Architecture", "Local academic prototype: frontend, backend, database/network state, and versioned ML artifact are run as coordinated processes.")
    body += group(35, 95, 650, 400, "PRESENTATION AND APPLICATION HOST")
    body += panel(75, 155, 250, 100, "React + Vite frontend", ["Leaflet map", "live vehicles / routes / demos", "browser client"], "blue")
    body += panel(395, 155, 250, 100, "FastAPI backend", ["API routers", "services + repositories", "runtime Geo V2 inference"], "blue")
    body += arrow(325, 205, 395, 205, "HTTP API")
    body += panel(175, 335, 390, 86, "run_project.py / local scripts", ["backend from backend/", "frontend from frontend/", "dataset, replay, training support"], "gray")
    body += arrow(520, 255, 520, 335)
    body += group(755, 95, 805, 400, "DATA, NETWORK, AND MODEL ARTIFACTS")
    body += panel(795, 155, 235, 100, "PostgreSQL + PostGIS", ["pings / memory / events", "segments + transitions", "live/prediction state"], "warm")
    body += panel(1080, 155, 205, 100, "OSM-derived network", ["geometry", "metadata", "network version"], "warm")
    body += panel(1335, 155, 190, 100, "Geo V2 artifact", ["best_model.pt", "scaler + schema", "provenance metadata"], "blue")
    body += arrow(645, 205, 795, 205, "SQL/PostGIS")
    body += arrow(1030, 205, 1080, 205)
    body += arrow(1285, 205, 1335, 205)
    body += panel(850, 335, 570, 86, "Shared local contract", ["network version + 23-feature order + model metadata", "artifact validation fails closed for mismatch"], "gray")
    body += arrow(1180, 255, 1180, 335)
    body += text_lines(800, 475, ["No cloud infrastructure, formal privacy mechanism, or unattended safety-critical deployment is implied."], "small")
    svg("fig_7_1_deployment", 1600, 550, body)


overall()
federated()
regional()
end_to_end()
features()
history()
network_import()
topology()
backend_layers()
frontend()
routing()
live_ingestion()
deployment()


def validation() -> None:
    values = [("Validation macro F1", 0.3042), ("Test macro F1", 0.3200), ("Event-balanced F1", 0.4459), ("Anomaly recall", 0.3444), ("Anomaly precision", 0.2093)]
    body = '<text x="750" y="35" text-anchor="middle" class="title">Frozen Geo V2 Model Validation Results</text>'
    for i, (label, value) in enumerate(values):
        y = 82 + i * 72
        body += f'<text x="40" y="{y+22}" class="body">{escape(label)}</text><rect x="300" y="{y}" width="900" height="34" class="box"/>'
        body += f'<rect x="300" y="{y}" width="{900*value}" height="34" fill="#555" stroke="#000" stroke-width="1"/><text x="1230" y="{y+23}" class="body">{value:.4f}</text>'
    body += '<text x="40" y="462" class="small">Test accuracy = 0.9952; normal false-positive rate = 0.0031. Accuracy is dominated by the normal class.</text>'
    body += '<text x="40" y="484" class="small">Not approved for unattended safety-critical operation.</text>'
    svg("fig_6_1_model_validation", 1500, 520, body)


def confusion() -> None:
    import csv
    source = ROOT.parents[2] / "backend/app/ml/artifacts/geo_v2/federated/robust-v2-hs1-prior2-unweighted-bw3-22-50r2e-seed42/confusion_matrix.csv"
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    labels = rows[0][1:]
    values = [[int(value) for value in row[1:]] for row in rows[1:]]
    maximum = max(max(row) for row in values)
    cell, ox, oy = 112, 280, 120
    body = '<text x="750" y="34" text-anchor="middle" class="title">Frozen Artifact Confusion Matrix</text><text x="750" y="58" text-anchor="middle" class="small">Rows = actual class; columns = predicted class</text>'
    for i, label in enumerate(labels):
        body += f'<text x="{ox+i*cell+cell/2}" y="100" text-anchor="middle" class="small">{escape(label.replace("_", " "))}</text>'
        body += f'<text x="{ox-10}" y="{oy+i*cell+cell/2+4}" text-anchor="end" class="small">{escape(label.replace("_", " "))}</text>'
    for r, row in enumerate(values):
        for c, value in enumerate(row):
            shade = 255 - round(190 * value / maximum)
            text_color = "#fff" if shade < 128 else "#000"
            body += f'<rect x="{ox+c*cell}" y="{oy+r*cell}" width="{cell}" height="{cell}" fill="rgb({shade},{shade},{shade})" stroke="#000" stroke-width="1"/><text x="{ox+c*cell+cell/2}" y="{oy+r*cell+cell/2+5}" text-anchor="middle" font-family="Times New Roman" font-size="14" fill="{text_color}">{value}</text>'
    svg("fig_6_2_confusion_matrix", 1500, 1060, body)


def tests() -> None:
    body = '<text x="750" y="35" text-anchor="middle" class="title">Backend and Frontend Test Evidence</text>'
    body += box(120, 100, 500, 150, "Backend verification", ["117 tests passed", "Python compilation passed", "FastAPI import passed"])
    body += box(880, 100, 500, 150, "Frontend verification", ["17 Traffic Map tests passed", "TypeScript compilation passed", "Vite production build passed"])
    body += '<line x1="620" y1="175" x2="880" y2="175" class="arrow"/>'
    body += box(430, 330, 640, 120, "Verified project evidence", ["Geo V2 artifact compatibility passed", "2,968 segments and 11,259 transitions", "No fabricated runtime or hardware measurements"])
    svg("fig_6_3_test_evidence", 1500, 510, body)


validation()
confusion()
tests()
