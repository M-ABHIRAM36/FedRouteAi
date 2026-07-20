# 4. Experimental Setup

## 4.1 Dataset Generation and Preprocessing

A critical challenge in evaluating deployment-aware edge intelligence is the lack of public Intelligent Transportation Systems (ITS) datasets that explicitly capture hardware-induced data volatility, such as sensor packet drops and extreme Out-of-Distribution (OOD) telemetry. Consequently, we generated a comprehensive synthetic traffic anomaly dataset to serve as a rigorous testbed for non-IID (Independent and Identically Distributed) edge failures.

The dataset simulates vehicular telemetry across distinct geographical zones, calibrated for high, medium, and low traffic densities. It comprises an 8-class distribution, encompassing normal traffic conditions alongside seven specific anomaly types (e.g., road damage, sudden congestion). To accurately reflect real-world vehicular environments, the dataset is intentionally highly imbalanced; normal traffic constitutes approximately 76.5% of the samples, while specific anomalies represent a minor fraction (e.g., road damage at 11.0%). During preprocessing, raw absolute values are converted into localized relative ratios, ensuring that the feature vectors fed into the local models are standardized across disparate geographic zones, as detailed in Section 3.2.

## 4.2 Federated Simulation Environment

To evaluate the proposed architecture under realistic distributed conditions, the experimental framework utilizes the Flower federated learning simulation environment. The simulation is orchestrated across a set of heterogeneous edge clients representing independent vehicular nodes or roadside units. 

To mimic the statistical heterogeneity inherent in urban transportation, the synthetic dataset is partitioned across the clients in a non-IID manner, ensuring that different edge nodes experience unique local class distributions and data volumes. The central aggregation server and all simulated edge clients execute concurrently, orchestrated via Python multiprocessing. This controlled federated simulation enables precise ablation of the aggregation algorithms while maintaining strict privacy boundaries between the local training data and the central model parameters.

## 4.3 Evaluation Metrics

To rigorously evaluate model performance, especially given the severe 8-class imbalance, the primary evaluation metric is the Macro F1 score rather than standard global accuracy. Macro F1 calculates the unweighted mean of the F1 scores across all classes, ensuring that the detection of minority anomalies (such as sudden congestion or road damage) is weighted equally to the dominant normal traffic class. 

Additionally, we evaluate two critical systems-level metrics:
- **Inference Latency:** Measured as the average inference latency per sample required for the edge device to process a raw telemetry packet through the historical memory preprocessing logic and generate an MLP classification. This assesses the computational overhead introduced by the OOD mitigation strategy.
- **Communication Cost:** Measured by the cumulative size (in bytes) of model parameters exchanged between participating clients and the aggregation server during each communication round, verifying the efficiency of the decentralized architecture.

## 4.4 Baselines and Ablation Studies

The experimental protocol is designed to isolate and validate each methodological contribution described in Section 3 through a series of baselines and targeted ablations.

**Baselines:**
- **Centralized MLP:** The model is trained on the entirely aggregated global dataset without federated constraints, establishing the theoretical upper bound for classification performance.
- **Standard FedAvg:** The federated simulation is executed using Flower\'s default FedAvg strategy, aggregating updates proportionally to local dataset size. This serves as the primary federated baseline.

**Ablation Studies:**
- **Aggregation Strategy (AdaptiveFedAvg vs. FedAvg):** By replacing standard FedAvg with the proposed four-factor AdaptiveFedAvg (validating Section 3.4), we evaluate the contribution of the temporal stability gate and rarity bonus on global convergence.

All remaining hyperparameters are kept constant across the ablation studies unless explicitly stated.

## 4.5 Implementation Details

For reproducibility, the federated framework is implemented in Python 3.10. The deep learning models are developed using PyTorch 2.0. The federated architecture relies on the Flower framework (flwr 1.5). The edge-backend engineering infrastructure utilizes FastAPI for endpoint routing and PostgreSQL 15 for the Historical Memory Module.

**Hardware Configuration:**
The centralized simulation and inference benchmarking were executed on a system equipped with an Intel Core i9 processor, 32GB RAM, and an NVIDIA RTX 4080 GPU running Ubuntu 22.04.