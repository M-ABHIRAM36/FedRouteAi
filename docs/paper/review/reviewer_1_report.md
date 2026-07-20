# IEEE Conference Mock Review: Reviewer #1

## Evaluation Categories

**1. Novelty: 7/10**
*Justification:* The integration of federated learning into ITS is not entirely new. However, the specific combination of a historical memory module for relative feature engineering alongside a four-factor adaptive aggregation algorithm (`AdaptiveFedAvg`) and deployment-aware inference (OOD warnings) presents a compelling, systems-level approach to a recognized problem.

**2. Technical Correctness: 9/10**
*Justification:* The paper accurately describes its methods and limits claims to what was experimentally measured. The decision to use deterministic zero-imputation coupled with dynamic OOD threshold warnings instead of arbitrary clipping is mathematically sound and highly practical for edge deployment. 

**3. Methodology: 8/10**
*Justification:* The decoupled architecture (Edge, Backend, Memory Module) is well-reasoned. The `AdaptiveFedAvg` algorithm is clearly formulated with four distinct factors ($n_k, q_k, \rho_k, g_k$). The only slight drawback is the reliance on a completely synthetic dataset, which inherently limits the evaluation of real-world edge volatility.

**4. Experimental Validation: 7/10**
*Justification:* The inclusion of latency and communication metrics (0.2069 ms inference, 207.36 KB payload) is excellent and grounds the paper in physical reality. However, standard FedAvg performed almost identically to the proposed `AdaptiveFedAvg`. While the authors transparently acknowledge this as a result of lacking temporal volatility in the synthetic dataset, it weakens the empirical necessity of the proposed aggregation algorithm.

**5. Writing Quality: 9/10**
*Justification:* The paper is exceptionally well-written. It employs objective, scientific language, entirely avoids promotional rhetoric, and logically structures the narrative from theory to implementation to results. 

**6. Reproducibility: 8/10**
*Justification:* Hyperparameters, hardware specifications, dataset distributions, and software versions (Python 3.10, PyTorch 2.0, Flower 1.5) are well-documented. Releasing the synthetic dataset generator and source code would elevate this to a 10.

**7. Organization: 9/10**
*Justification:* The paper flows logically according to standard IEEE structure. The explicit separation of "Overall System Architecture" from "Deployment-Aware Inference" in Section III is highly effective. 

**8. References: 8/10**
*Justification:* The bibliography covers fundamental FL literature (McMahan) and modern ITS applications. The references are highly relevant, though a few more recent citations specifically addressing edge-OOD mitigation in V2X networks could strengthen Section II-C.

**9. Figures and Tables: 8/10**
*Justification:* Table I (Dataset Statistics) clearly communicates the class imbalance challenge. The placeholder figures for Architecture and Historical Memory are appropriately placed, assuming the final graphical representations are clear and informative.

**10. Overall Contribution: 8/10**
*Justification:* A solid, highly transparent engineering paper that bridges theoretical federated learning with the harsh realities of ITS edge deployment. The honest reporting of the `AdaptiveFedAvg` vs `FedAvg` results is refreshing and scientifically mature.

---

## Formal Review

**Summary of the Paper**
The manuscript presents `FedRouteAI`, a federated learning framework designed for multi-class traffic anomaly detection in Intelligent Transportation Systems (ITS). To address the challenges of data privacy, extreme class imbalance, and volatile edge sensor inputs, the authors propose an architecture featuring a Historical Memory Module for relative feature normalization, a deployment-aware inference pipeline (zero-imputation and dynamic OOD warnings), and a four-factor Adaptive Federated Aggregation strategy (`AdaptiveFedAvg`). The system is evaluated on a synthetic 8-class vehicular telemetry dataset. Results indicate the federated approach successfully regularized the imbalanced data compared to a centralized baseline, and achieved sub-millisecond inference latency (0.2069 ms) suitable for edge deployment.

**Major Strengths**
- **Deployment-Aware Pragmatism:** The paper excels in recognizing the difference between simulation and physical deployment. The dynamic OOD warning system and zero-imputation fallback is a highly practical solution to sensor packet drops.
- **Scientific Honesty:** The authors transparently report that the proposed `AdaptiveFedAvg` algorithm achieved nearly identical variance (0.0011 vs 0.0010) and performance to standard `FedAvg`. Rather than hiding this, they provide a strong, objective analysis of why standard dataset-proportional scaling is robust under controlled simulations.
- **Systems-Level Metrics:** Benchmarking inference latency (0.2069 ms) and communication overhead (207.36 KB) elevates this beyond a purely theoretical machine learning paper.

**Major Weaknesses**
- **Synthetic Dataset Limitations:** The entire experimental validation relies on a synthetic dataset. Crucially, as the authors admit in Section V-D, this synthetic data lacked the severe temporal volatility required to trigger the reliability gate ($g_k$) in their proposed `AdaptiveFedAvg` algorithm. This makes it difficult to fully validate the necessity of the proposed adaptive aggregation method.
- **Lack of OOD Mitigation Benchmarks:** While the paper proposes a deployment-aware inference pipeline (OOD warnings and zero-imputation), there is no specific ablation study isolating the performance of the system when OOD events occur versus when they do not. The reader is left to trust the architectural design without empirical proof of its superiority over baseline inference.

**Minor Comments**
- In Section III-C, the text provides threshold examples (`speed_ratio > 3.0`). It would be beneficial to briefly state how these thresholds were statistically derived during the training phase.
- Ensure the capitalization of "AdaptiveFedAvg" is completely consistent in the final manuscript and charts.

**Questions for the Authors**
1. Given that `AdaptiveFedAvg` showed no significant improvement over `FedAvg` on the current dataset, under what specific statistical conditions (e.g., packet drop rate, adversarial interference frequency) do you hypothesize the temporal reliability gate ($g_k$) becomes mathematically critical?
2. How does the deterministic zero-imputation affect the final MLP activation distributions compared to mean-imputation?

**Suggested Improvements**
- Introduce a targeted, synthetic "noise injection" ablation experiment. By manually forcing extreme volatility/packet drops onto 2 of the 8 simulated clients, the authors could empirically trigger the $g_k$ gate and prove the superiority of `AdaptiveFedAvg` over standard `FedAvg`. 
- Explicitly state in the abstract that the evaluation was performed on a synthetic dataset to set correct expectations immediately.

---

## Final Recommendation
**Recommendation: Weak Accept**

**Final Verdict:** The manuscript is highly transparent, impeccably written, and presents a pragmatic, systems-level architecture for vehicular edge computing. While the reliance on a non-volatile synthetic dataset fails to empirically prove the superiority of the proposed adaptive aggregation algorithm over baselines, the authors' honest discussion of this limitation, combined with the excellent latency benchmarking and robust feature engineering methodology, make this a valuable contribution to the ITS engineering community.
