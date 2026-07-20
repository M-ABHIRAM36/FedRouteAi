# Section Blueprint: 03_introduction.md

## Structure
1. Introduction
   - 1.1 Background
   - 1.2 Motivation
   - 1.3 Research Gap
   - 1.4 Contributions

## Purpose
- **What problem is being solved?** Decentralized multi-class traffic anomaly detection on edge devices that frequently experience dropped sensor packets or Out-Of-Distribution (OOD) telemetry.
- **Why is it important?** Centralized models violate privacy and scale poorly. Standard Federated Learning (FL) solves privacy but models fail gracefully during live inference when edge sensors drop essential feature data.
- **Why now?** With the rise of Connected and Automated Vehicles (CAVs), V2X federated networks are becoming standard. However, the robustness of these decentralized models against incomplete, noisy live inference data is an unsolved deployment roadblock.

## Evidence
- **References Supporting Paragraphs:**
  - *1.1 Background:* `zhang2024federated_its` (ITS/FL context), `mcmahan2017communication` (Foundational FedAvg).
  - *1.2 Motivation:* `liu2020privacy` (Privacy risks of central data), `zhao2018federated` (Heterogeneity challenges).
  - *1.3 Research Gap:* Derived from our *Literature Review* (Lack of OOD interception at inference time).
- **Implementation Evidence Mentioned:** The framework implementation, deployment-aware inference pipeline, and feature preprocessing consistency. Quantitative performance is reserved for the Results section.

## Figures & Tables
- **Figures:** None referenced in the Introduction (reserving Figure 1 for Methodology to maintain narrative focus).
- **Tables:** None.

## Claims
- **Claim 1:** Centralized ITS architectures pose privacy risks and communication bottlenecks. *(Support: `liu2020privacy`)*
- **Claim 2:** Incomplete or out-of-distribution feature vectors can reduce the reliability of machine learning models during edge inference. *(Supported by prior literature and the motivation for the proposed framework).*
- **Claim 3:** FedRouteAI safely handles missing features by reproducing the exact feature-generation fallback strategy used during training. *(Support: Implemented logic in `predict.py`).*
- **Claim 4:** The proposed framework is experimentally evaluated on a multi-class traffic anomaly dataset. Quantitative results are presented in Section VI.

## Reviewer Checklist
- [x] Is the motivation clear? *(Privacy + Edge deployment reality).*
- [x] Is the research gap explicit? *(Lack of inference-time OOD handling for incomplete data).*
- [x] Are contributions stated without exaggeration? *(Yes, avoiding words like "solves" or "perfectly").*
- [x] Is novelty distinguished from engineering? *(Yes. Research novelty = a deployment-aware inference strategy that maintains consistency between training-time and inference-time preprocessing).*
