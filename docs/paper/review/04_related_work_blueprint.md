# Section Blueprint: 04_related_work.md

## Structure
2. Related Work
   - 2.1 Federated Learning in Intelligent Transportation Systems
   - 2.2 Traffic Anomaly Detection and Trajectory Analysis
   - 2.3 Edge Deployment Challenges and Out-of-Distribution Mitigation
   - 2.4 Summary of Research Gap

## Purpose
- **2.1 FL in ITS:** Existing federated learning frameworks have primarily focused on privacy-preserving distributed training and communication efficiency. Comparatively fewer studies have examined inference robustness under incomplete feature availability.
- **2.2 Traffic Anomaly Detection:** Focus on how traffic anomaly detection often relies on centralized, high-dimensional spatial representations.
- **2.3 Edge & OOD:** Review OOD techniques broadly in CV/NLP, leading to the challenge of applying them directly to constrained edge traffic sensors.
- **2.4 Summary:** Synthesize the above to perfectly transition into Methodology, using the phrasing: "These observations motivate the approach proposed in this paper."

## Evidence (References to Include)
- **2.1 FL in ITS:** `zhang2024federated_its` (ST-data FL), `liu2020privacy` (FedGRU privacy), `yuan2023urban` (Traffic heterogeneity), `chellapandi2024cav` (CAV security).
- **2.2 Traffic Anomaly Detection:** `zhang2022deep` (Centralized ResNet), `jiang2023gnn` (Centralized ST-GNN), `kong2018realtime` (Grid clustering), `su2020trajectory` (Trajectory mining limitations).
- **2.3 Edge Deployment & OOD:** `zhao2018federated` (Non-IID divergence), `reddi2021adaptive` (Adaptive optimization), `wang2019adaptive` (Resource constraints), `liang2018enhancing` (ODIN/softmax limitations).

## Claims
- **Claim 1:** Many existing ITS federated learning studies primarily evaluate performance under complete feature availability and controlled experimental settings, leaving inference robustness under incomplete feature conditions comparatively underexplored.
- **Claim 2:** Many trajectory-based approaches rely on processing high-dimensional GPS trajectories or centralized spatial representations, which can be computationally prohibitive for edge devices and expose spatial data.
- **Claim 3:** Many OOD detection techniques in computer vision and natural language processing rely on confidence calibration or post-hoc scoring methods. Their direct applicability to resource-constrained intelligent transportation deployments remains an active area of research.

## Reviewer Checklist
- [x] Does this section *synthesize* literature rather than just listing papers chronologically?
- [x] Are the limitations of existing works stated fairly (without aggressive bashing or universal statements)?
- [x] Does each subsection end with a transition highlighting the insufficient exploration of inference robustness?
- [x] Is the specific method (FedRouteAI) avoided in this section, instead ending 2.4 with "These observations motivate the methodology presented in the next section"?
