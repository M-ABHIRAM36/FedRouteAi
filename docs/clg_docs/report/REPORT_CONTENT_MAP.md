# FedRouteAI Report Content Map

Target: `FedRouteAI_Major_Project_Report_FINAL.docx`

## Chapter Map

| Chapter | Scope | Main evidence or output |
|---|---|---|
| 1. Introduction | Background, need, objectives, scope, limitations, organization | Problem definition and project boundaries |
| 2. Literature Survey | Intelligent transportation, GPS traffic analysis, anomaly detection, federated learning, MLPs, historical modeling, OSM/PostGIS, routing, research gap | Related-work comparison and project position |
| 3. Requirement Analysis and Feasibility Study | Stakeholders, functional and non-functional requirements, data/model/database/network requirements, feasibility, ethics, constraints | Requirement traceability and feasibility justification |
| 4. System Design and Architecture | Layering, dataset separation, federated architecture, Geo V2 contract, temporal/history/spatial features, OSM/PostGIS, backend, frontend, ingestion, prediction, routing, demonstration | System architecture and exact 23-feature contract |
| 5. Implementation | Dataset generation, regional partitioning, MLP, local training, FedAvg, adaptive aggregation, artifact handling, ingestion, aggregation, inference, persistence, map, routing, demonstrations, APIs, frontend, validation | Module-level implementation description |
| 6. Testing and Validation | Unit, backend, API, database, Geo V2, artifact, federated, routing, ingestion, frontend, map, demonstration, build, runtime, performance, limitations | 117 backend tests, 17 focused frontend tests, build and artifact evidence, frozen metrics |
| 7. Deployment, Security and Performance | Local deployment, configuration, security, validation, artifact integrity, data separation, privacy limitations, performance, browser and scalability concerns | Measured versus unmeasured operational claims |
| 8. Conclusion and Future Enhancements | Conclusion, achieved objectives, contributions, experimental findings, limitations, future enhancements, final remarks | Final project assessment and next research steps |
| 9. Appendices | Reproduction, evidence register, figure register, model configuration, network statistics, testing, telemetry, API, database, federated training, metrics, routing, demonstrations, frontend, operations, reproducibility, limitations, and submission review | Reproducibility and review material |
| 10. References | Research and technical sources | Bibliography |

## Figure Map

| Figure | Content | Status |
|---|---|---|
| 4.1 | Overall system architecture | Embedded grayscale figure |
| 4.2 | Federated learning architecture | Embedded grayscale figure |
| 4.3 | Regional client and server interaction | Embedded grayscale figure |
| 4.4 | End-to-end data pipeline | Embedded grayscale figure |
| 4.5 | Geo V2 feature construction pipeline | Embedded grayscale figure |
| 4.6 | Historical traffic memory and causal windows | Embedded grayscale figure |
| 4.7 | OSM/PostGIS network import | Embedded grayscale figure |
| 4.8 | Directed road network and transitions | Embedded grayscale figure |
| 4.9 | Backend service and repository layers | Embedded grayscale figure |
| 4.10 | Frontend map and API interaction | Embedded grayscale figure |
| 4.11 | Directed shortest-path routing | Embedded grayscale figure |
| 5.1 | Live GPS ingestion pipeline | Embedded grayscale figure |
| 5.2 | Frozen Geo V2 MLP inference | Embedded grayscale figure |
| 5.3 | Dynamic traffic map | Placeholder; real screenshot unavailable |
| 5.4 | Moving vehicle visualization | Placeholder; real screenshot unavailable |
| 5.5 | Route-bound demonstration flow | Placeholder; real screenshot unavailable |
| 5.6 | Normal traffic demonstration | Placeholder; real screenshot unavailable |
| 5.7 | Congestion and Accident demonstrations | Placeholder; real screenshot unavailable |
| 6.1 | Model validation results | Embedded grayscale figure |
| 6.2 | Model confusion matrix | Embedded from frozen artifact data |
| 6.3 | Backend and frontend test evidence | Embedded grayscale figure |
| 7.1 | Local deployment architecture | Embedded grayscale figure |

Editable SVG masters and PNG/PDF derivatives are stored under `docs/clg_docs/figures/`.

## Table Map

| Table | Planned content |
|---|---|
| 2.1 | Related approaches and FedRouteAI position |
| 3.1 | Functional requirements |
| 3.2 | Requirement traceability |
| 3.3 | Software and hardware requirements |
| 3.4 | Additional requirement evidence |
| 4.1 | Exact 23-feature Geo V2 contract |
| 4.2 | Dataset and runtime data separation |
| 4.3 | Database and network statistics |
| 5.1 | Major software modules |
| 5.2 | Model configuration |
| 5.3 | Demonstration controls |
| 5.4 | Additional implementation evidence |
| 6.1 | Test categories |
| 6.2 | Additional validation evidence |
| 7.1 | Deployment and performance evidence |
| 9.1 | Database and network evidence |
| 9.2 | Evidence register |

The generated DOCX contains 12 table objects; some planned table topics are combined into larger tables in the final document to avoid unnecessary fragmentation.

## Evidence Boundaries

- Training/evaluation data contains labels for supervised evaluation; runtime inference does not consume labels.
- Controlled scenario names are not model inputs and are not ground truth predictions.
- The default route cost is distance-based; predictions and explicit exclusions are separate route-inspection behavior.
- The documented model metrics come from the frozen artifact report.
- Unmeasured hardware, end-to-end production throughput, memory pressure, formal privacy guarantees, and production deployment claims are excluded.

## Format Structure

- Every chapter uses a dedicated centered separator page.
- Chapter content begins on the page following its separator.
- Front matter uses lower-case Roman numbering.
- Chapter 1 restarts page numbering with Arabic numeral 1.
- Page numbers are centered at the bottom.
- Formal front-matter order follows the college rule: cover/title, certificate,
  declaration, acknowledgement, abstract, contents, list of tables, list of
  figures, and abbreviations.
- The final Microsoft Word rendering is 75 pages.
