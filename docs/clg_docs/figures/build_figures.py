from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import fitz
from reportlab.graphics import renderPDF
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
    page = fitz.open(pdf_target)[0]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
    pixmap.save(str(PNG / f"{name}.png"))


def box(x: int, y: int, w: int, h: int, title: str, lines: list[str], dashed: bool = False) -> str:
    cls = "dash" if dashed else "box"
    text = f'<text x="{x+w/2}" y="{y+26}" text-anchor="middle" class="head">{escape(title)}</text>'
    for i, line in enumerate(lines):
        text += f'<text x="{x+w/2}" y="{y+52+i*18}" text-anchor="middle" class="body">{escape(line)}</text>'
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" class="{cls}"/>{text}'


def flow(name: str, title: str, labels: list[str], subtitle: str = "") -> None:
    width, h = 1500, 230
    body = f'<text x="750" y="32" text-anchor="middle" class="title">{escape(title)}</text>'
    if subtitle:
        body += f'<text x="750" y="55" text-anchor="middle" class="small">{escape(subtitle)}</text>'
    y, w, gap = 85, 178, 18
    for i, label in enumerate(labels):
        x = 30 + i * (w + gap)
        body += box(x, y, w, 85, label, [])
        if i < len(labels) - 1:
            body += f'<line x1="{x+w+4}" y1="{y+42}" x2="{x+w+gap-5}" y2="{y+42}" class="arrow"/>'
    svg(name, width, h, body)


flow("fig_4_1_overall_architecture", "Overall System Architecture of FedRouteAI", ["Regional GPS\nsources", "Local\npreprocessing", "Local MLP\nclients", "Adaptive\naggregation", "Global Geo V2\nmodel", "Runtime\ninference", "Prediction\npersistence", "FastAPI +\nReact/Leaflet"], "Training and runtime meet through a versioned model artifact; OSM/PostGIS and directed routing form the spatial subsystem.")


def federated() -> None:
    body = '<text x="750" y="32" text-anchor="middle" class="title">Federated Learning Architecture</text>'
    for i in range(8):
        x = 30 + (i % 4) * 275
        y = 70 + (i // 4) * 100
        body += box(x, y, 230, 68, f"REGION_{i+1:02d}", ["local traffic data → Geo V2 → MLP"])
        body += f'<line x1="{x+115}" y1="{y+68}" x2="750" y2="285" class="arrow"/>'
    body += box(570, 285, 360, 82, "Adaptive FedAvg", ["8 parameter updates", "RAW LOCAL DATA STAYS WITH CLIENT"])
    body += '<line x1="750" y1="367" x2="750" y2="430" class="arrow"/>'
    body += box(570, 430, 360, 70, "Global Geo V2 model", ["distribute parameters for next round"])
    svg("fig_4_2_federated_learning", 1500, 540, body)


federated()
flow("fig_4_3_regional_client_server", "Regional Client and Server Interaction", ["Regional\ntelemetry", "History +\nfeatures", "Local MLP\ntraining", "Evaluation +\nupdate", "Receive\nupdates", "Adaptive\naggregation", "Distribute\nglobal model"])
flow("fig_4_4_end_to_end_pipeline", "End-to-End Data Pipeline", ["GPS\nobservations", "Segment\nassociation", "Temporal\naggregation", "Baseline +\nhistory", "23-feature\nvector", "Frozen\nMLP", "Prediction\npersistence", "Traffic\nMap"], "Inference input contains no label or scenario field.")


def features() -> None:
    body = '<text x="750" y="32" text-anchor="middle" class="title">Geo V2 Feature Construction Pipeline</text>'
    groups = [
        ("CURRENT TRAFFIC", ["avg_speed_kmph", "speed_std_kmph", "vehicle_count", "occupancy", "flow_rate_vph", "stopped_fraction"]),
        ("TEMPORAL", ["hour_sin", "hour_cos"]),
        ("ROAD METADATA", ["road_type_code", "lane_count", "max_speed_kmph"]),
        ("HISTORICAL BASELINE", ["baseline_speed_kmph", "baseline_speed_std_kmph", "baseline_vehicle_count"]),
        ("DEVIATION", ["speed_to_baseline", "count_to_baseline", "std_to_baseline"]),
        ("PRIOR WINDOWS / TRENDS", ["prior_speed_mean_3", "prior_count_mean_3", "speed_trend", "count_trend", "low_speed_persistence_3"]),
        ("SPATIAL", ["neighbor_speed_delta"]),
    ]
    x, y = 28, 68
    for idx, (title, lines) in enumerate(groups):
        w = 340 if idx in (0, 5) else 300
        col = idx % 2
        row = idx // 2
        xx, yy = 28 + col * 390, 68 + row * 112
        body += box(xx, yy, w, 92, title, lines)
    body += '<line x1="750" y1="495" x2="750" y2="545" class="arrow"/>'
    body += box(480, 545, 540, 70, "Ordered 23-feature vector", ["geo-v2-history_spatial_strong-23-v2 → frozen Geo V2 MLP"])
    svg("fig_4_5_geo_v2_features", 1500, 660, body)


features()
flow("fig_4_6_historical_causal_windows", "Historical Traffic Memory and Causal Windows", ["Normal\nprehistory", "Baseline\nconstruction", "t-3", "t-2", "t-1", "CURRENT t"], "Shifted prior observations only; no future information and no current-value leakage.")
flow("fig_4_7_osm_postgis_import", "OSM/PostGIS Network Import", ["OSM source", "Cached\nnetwork", "Normalization", "2,968\nsegments", "11,259\ndirected transitions", "PostGIS +\nnetwork version", "API / ML /\nrouting / map"])


def topology() -> None:
    body = '<text x="750" y="35" text-anchor="middle" class="title">Directed Road Network and Transitions</text>'
    body += box(90, 130, 250, 90, "Segment A", ["outgoing transition → B"])
    body += box(625, 130, 250, 90, "Segment B", ["outgoing transition → C"])
    body += box(1160, 130, 250, 90, "Segment C", ["terminal example"])
    body += '<line x1="340" y1="175" x2="625" y2="175" class="arrow"/><line x1="875" y1="175" x2="1160" y2="175" class="arrow"/>'
    body += box(360, 320, 780, 100, "Direction rule", ["A → B → C is legal when persisted as directed transitions", "a reverse edge is separate and may be absent for one-way roads"])
    body += '<path d="M625 225 C625 285 340 285 215 225" class="arrow"/>'
    body += '<text x="410" y="275" class="small">optional reverse edge only when network contains it</text>'
    svg("fig_4_8_directed_network", 1500, 500, body)


topology()
flow("fig_4_9_backend_layers", "Backend Service and Repository Layers", ["Frontend /\nAPI request", "FastAPI\nendpoint", "Service layer\nML / routing / ingest / demo", "Repository\nlayer", "PostgreSQL /\nPostGIS"], "Endpoint parsing, business logic, and database access remain separate.")
flow("fig_4_10_frontend_api_interaction", "Frontend Map and API Interaction", ["React Traffic\nMap", "Typed API\nclients", "FastAPI", "Network + live\nsnapshot", "Predictions +\nvehicles + events", "Route + demo\nstate", "Map layers"])
flow("fig_4_11_directed_shortest_path", "Directed Shortest-Path Routing", ["Origin /\ndestination", "Snap to\nroad", "Directed\ngraph", "Dijkstra", "Ordered\nsegment IDs", "Route\ngeometry", "Distance +\nETA"], "DEFAULT COST = DISTANCE; prediction inspection and explicit exclusions are separate paths.")
flow("fig_5_1_live_ingestion", "Live GPS Ingestion Pipeline", ["Trusted GPS\nbatch", "Validate +\nreceipt", "Persist\nhistory", "Aggregate\nsegments", "Build\nfeatures", "Infer +\npersist", "Scoped live\nsnapshot"])
flow("fig_5_2_frozen_mlp", "Frozen Geo V2 MLP Inference", ["23 ordered\nfeatures", "Artifact +\nscaler check", "GeoV2MLP\nevaluation mode", "8-class\nlog-softmax", "Prediction +\nconfidence"])
flow("fig_7_1_local_deployment", "Local Deployment Architecture", ["PostgreSQL /\nPostGIS", "FastAPI\nbackend", "React / Vite\nfrontend"], "LOCAL ACADEMIC PROTOTYPE; optional Geo V2 simulator / replay / demonstration is not cloud infrastructure.")


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
