# Section Blueprint: 06_experimental_setup_blueprint.md

## Structure
4. Experimental Setup
   - 4.1 Dataset Generation and Preprocessing
   - 4.2 Federated Simulation Environment
   - 4.3 Evaluation Metrics
   - 4.4 Baselines and Ablation Studies
   - 4.5 Implementation Details

## Purpose
- **4.1 Dataset Generation:** Clearly state that the dataset is synthetically generated to simulate distinct geographical zones (e.g., high, medium, low traffic). Explain *why* synthetic data is required: existing public datasets lack the controlled, non-IID feature dropouts necessary to evaluate edge robustness. Detail the 8 anomaly classes and class imbalance.
- **4.2 Federated Simulation:** Describe the edge node configuration. Explain how the data is distributed among clients to simulate real-world heterogeneity (non-IID distribution) using the Flower framework.
- **4.3 Evaluation Metrics:** Define the metrics used to validate the methodology.
  - *Macro F1:* Chosen over accuracy due to severe anomaly class imbalance.
  - *Inference Latency:* Measures the computational overhead of the OOD fallback logic at the edge.
  - *Communication Cost:* Measured as the total model parameters/bytes exchanged per federated round.
- **4.4 Baselines and Ablation Studies:** Map experiments directly to Section 3.
  - *Baselines:* Centralized MLP (upper bound), Standard FedAvg (base federated performance).
  - *Ablation 1:* AdaptiveFedAvg vs Standard FedAvg (validates Section 3.4).
  - *Ablation 2:* OOD preprocessing ON vs OFF (validates Section 3.3).
- **4.5 Implementation Details:** Provide software versions to satisfy IEEE reproducibility standards (Python, PyTorch, Flower, FastAPI, PostgreSQL).

## Claims to Support (No Spoilers)
- The synthetic dataset provides a rigorous testbed for non-IID edge failures.
- The evaluation protocol isolates each methodological contribution (aggregation strategy and OOD logic) to empirically validate their individual impact on system reliability.

## Reviewer Checklist
- [x] Is the synthetic nature of the dataset explicitly stated and justified?
- [x] Does the baseline truly represent standard FedAvg?
- [x] Are the ablation studies perfectly mapped to the methodological novelties (3.3 and 3.4)?
- [x] Are reproducibility details (versions, metrics definitions) thoroughly documented?
