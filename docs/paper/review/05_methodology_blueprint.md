# Section Blueprint: 05_methodology_blueprint.md

## Structure
3. Methodology
   - 3.1 Overall System Architecture
   - 3.2 Historical Memory and Feature Engineering
   - 3.3 Deployment-Aware Inference and OOD Mitigation
   - 3.4 Adaptive Federated Aggregation

## Purpose
- **3.1 Overall Architecture:** Introduce the end-to-end system integrating edge nodes, the FastAPI backend, and the PostgreSQL database. Address how this architecture enables privacy-preserving execution.
- **3.2 Historical Memory:** Explain how raw geospatial data (GPS, speed) is transformed into normalized relative ratios (e.g., `speed_ratio`) by comparing live telemetry against time-synchronized historical baselines without exposing the historical trajectories to the live edge model.
- **3.3 OOD Mitigation (The Core Novelty):** Detail the exact mathematical fallback mechanism. Explain how the inference pipeline intercepts dropped sensor packets or extreme inputs, strictly bounding them to the learned training distributions to prevent model saturation.
- **3.4 AdaptiveFedAvg:** Explain the modification to standard FedAvg, introducing dynamic client weighting to accommodate the heterogeneous computational capabilities of edge devices.

## Evidence (Implementation & Figures)
- **Figure 1:** Overall System Architecture (referenced in 3.1).
- **Figure 3:** Historical Memory Pipeline (referenced in 3.2).
- **Figure 8:** OOD Detection Pipeline (referenced in 3.3).
- **Figure 9:** Inference Pipeline (referenced in 3.3).
- **Implementation:** The `EventClassifierMLP` architecture and the deterministic fallback logic executed in the backend (`predict.py`).

## Claims
- **Claim 1:** The decoupled architecture ensures that raw historical trajectories are never transmitted to the live inference engine, maintaining strict V2X privacy.
- **Claim 2:** Engineering relative feature ratios (rather than absolute speeds/densities) allows the model to generalize across varied urban and highway road typologies.
- **Claim 3:** Reproducing the feature-generation fallback strategy used during training guarantees that incomplete edge vectors do not trigger mathematical instability during real-time classification.
- **Claim 4:** Adaptive federated aggregation improves upon standard uniform averaging by accounting for client-side data volatility and resource constraints.

## Reviewer Checklist
- [x] Does the section logically flow from the high-level architecture down to the specific algorithmic novelties?
- [x] Are the mathematical descriptions grounded entirely in the actual implementation (no hallucinated equations)?
- [x] Are the figures (Fig 1, 3, 8, 9) referenced effectively to support the text?
- [x] Does the text explicitly avoid reporting quantitative results (reserving them for the Results section)?
