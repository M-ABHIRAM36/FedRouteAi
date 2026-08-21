# FedRouteAI Figure Inventory

The final report embeds 17 generated technical figures. Each has an editable
SVG master and PNG/PDF derivatives under the corresponding format directory.
The 13 current-architecture replacement figures listed below were regenerated
and verified on 2026-08-22. PNG exports are RGB, 2400 pixels wide, and each
corresponding PDF has exactly one page. All technical figures use black,
white, and restrained academic accent fills.

| Figures | Master filename | Asset status | Evidence basis |
|---|---|---|---|
| 4.1 | `fig_4_1_overall_architecture.svg` | SVG, PNG, PDF; embedded | Runtime, federated-training, persistence, network, API, and presentation zones |
| 4.2 | `fig_4_2_federated_learning.svg` | SVG, PNG, PDF; embedded | Eight regional clients, local training, parameter updates, aggregation, and model distribution |
| 4.3 | `fig_4_3_regional_client_server.svg` | SVG, PNG, PDF; embedded | Explicit client/server round lifecycle and raw-data boundary |
| 4.4 | `fig_4_4_end_to_end_pipeline.svg` | SVG, PNG, PDF; embedded | Runtime inference and separately represented directed-routing branch |
| 4.5 | `fig_4_5_geo_v2_features.svg` | SVG, PNG, PDF; embedded | Exact ordered 23-feature `history_spatial_strong` contract and label-free inference |
| 4.6 | `fig_4_6_historical_memory.svg` | SVG, PNG, PDF; embedded | Normal prehistory, shifted causal windows, and leakage exclusions |
| 4.7 | `fig_4_7_osm_postgis.svg` | SVG, PNG, PDF; embedded | OSM import, canonical network, directed topology, version identity, and PostGIS consumers |
| 4.8 | `fig_4_8_directed_network.svg` | SVG, PNG, PDF; embedded | Graph-like canonical segments and legal directed transitions |
| 4.9 | `fig_4_9_backend_architecture.svg` | SVG, PNG, PDF; embedded | API, service, repository, model/database, ML, and routing boundaries |
| 4.10 | `fig_4_10_frontend_architecture.svg` | SVG, PNG, PDF; embedded | React API state and Leaflet layers with backend-owned inference/routing |
| 4.11 | `fig_4_11_routing.svg` | SVG, PNG, PDF; embedded | Distance-based directed shortest path and separate prediction inspection |
| 5.1 | `fig_5_1_live_ingestion.svg` | SVG, PNG, PDF; embedded | Append-only telemetry and current-state/prediction projection |
| 5.2 | `fig_5_2_frozen_mlp.svg` | SVG, PNG, PDF; embedded | Frozen MLP runtime |
| 6.1 | SVG, PNG, PDF; embedded | Frozen artifact metrics |
| 6.2 | SVG, PNG, PDF; embedded | Frozen `confusion_matrix.csv` |
| 6.3 | SVG, PNG, PDF; embedded | Verified backend/frontend test counts |
| 7.1 | `fig_7_1_deployment.svg` | SVG, PNG, PDF; embedded | Documented local deployment topology and artifact/network contracts |
| 5.3-5.7 | No generated asset; report placeholder retained | Real application screenshots unavailable |

UI/demo screenshots are intentionally not fabricated. When verified screenshots
become available, they can replace only figure positions 5.3 through 5.7.

## Export Verification

- Canonical architecture/implementation figures exported: 13 of 13.
- Each canonical figure has a non-empty SVG master, PDF derivative, and PNG
  derivative.
- PNG dimensions range from 2400x825 to 2400x1200 pixels at the generator's
  144 DPI rasterization setting.
- Every canonical PDF has one page and contains extractable title/body text.
- Structural checks found substantive text, technical rectangles, connectors,
  and the expected restrained palette in all 13 figures.
- The old reference figures under `docs/docs1.01/extracted_reference/figures/`
  were read for composition, density, and technical styling only; they were
  not overwritten or used as current-system evidence.
