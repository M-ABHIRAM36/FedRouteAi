# IEEE Conference Mock Review: Reviewer #2

## Evaluation Categories

**1. Novelty: 5/10**
While the combination of an adaptive federated learning algorithm with a deployment-aware inference pipeline is practically useful, the individual components (dynamic aggregation weights, threshold-based OOD detection, zero-imputation) are standard in literature. The novelty is heavily tied to the specific 4-factor formula of `AdaptiveFedAvg`, which the authors themselves admit failed to outperform the baseline.

**2. Technical Depth: 6/10**
The mathematical formulation of `AdaptiveFedAvg` (Equation 1) is straightforward, but its theoretical properties (e.g., convergence guarantees) are neither analyzed nor empirically proven to provide a benefit on the provided dataset.

**3. Methodology: 7/10**
The decoupling of the Historical Memory Module from the federated edge clients is architecturally sound. The use of zero-imputation instead of arbitrary clipping is mathematically safer.

**4. Experimental Design: 3/10**
This is the weakest aspect of the paper. The authors propose a "deployment-aware inference pipeline" (Section III-C) as a core contribution, yet provide *zero* experimental evaluation of this pipeline. There is no ablation study showing the accuracy of the OOD warnings, nor any demonstration of inference performance during active OOD events.

**5. Dataset: 4/10**
The dataset is entirely synthetic. More concerningly, it lacks the very characteristics (temporal volatility, extreme OOD events) that the proposed architecture was explicitly designed to handle. 

**6. Statistical Validity: 4/10**
The results in Section V report static percentage points (e.g., 82.21% vs 82.05%) without reporting standard deviations across multiple random seeds, making it impossible to determine if the +0.16% difference is statistically significant or merely noise.

**7. Reproducibility: 7/10**
The framework dependencies (Flower 1.5, PyTorch 2.0) and hardware are clearly listed. However, because the synthetic dataset generator is not mathematically defined or publicly released, true reproducibility is impossible.

**8. Writing: 9/10**
The writing is exceptionally clear, objective, and devoid of marketing language. The transparency in the discussion section is highly commendable.

**9. Citations: 8/10**
The citations are adequate, though the Related Work section could better integrate recent (2024-2025) papers specifically addressing OOD detection in V2X networks.

**10. Limitations: 9/10**
The authors provide a highly accurate and self-aware Limitations section.

---

## Detailed Criticisms

### Criticism 1: Lack of Empirical Proof for Core Contribution
- **Evidence:** Section III-C dedicates significant space to the "deployment-aware inference pipeline," detailing threshold detection and zero-imputation. However, Section IV (Experimental Setup) and Section V (Results) contain absolutely no ablation study or metrics evaluating this pipeline. The reader must take its efficacy on faith.
- **Severity:** Major
- **Recommendation:** Introduce a targeted ablation experiment. Subject a client to simulated sensor failure (packet drops or adversarial noise) and report the classification accuracy with OOD mitigation ENABLED vs DISABLED.
- **Affect on Acceptance:** Highly likely to trigger a Rejection if not addressed. A core methodological contribution cannot remain entirely unevaluated.

### Criticism 2: Ineffective Evaluation Dataset
- **Evidence:** The authors state in Section V-B: *"the synthetic dataset's non-IID distribution did not exhibit sufficient temporal volatility during training to explicitly trigger severe divergence in the standard FedAvg baseline."* Consequently, `AdaptiveFedAvg` performed identically to `FedAvg`.
- **Severity:** Major
- **Recommendation:** If `AdaptiveFedAvg` is designed to solve temporal volatility, the evaluation dataset *must* contain temporal volatility. The authors must inject erratic packet drops or shifting distributions into the synthetic dataset to prove the algorithm's utility. 
- **Affect on Acceptance:** Highly likely to trigger a Rejection. Proposing a complex 4-factor algorithm that fails to beat a basic baseline on the chosen dataset severely undermines the paper's technical contribution.

### Criticism 3: Missing Statistical Significance
- **Evidence:** Section V-A claims that `AdaptiveFedAvg` achieved 82.21% accuracy while standard FedAvg achieved 82.05%. 
- **Severity:** Moderate
- **Recommendation:** A 0.16% difference is negligible in deep learning. The authors must run the simulation across at least 3-5 different random seeds and report the mean and standard deviation (e.g., $82.21 \pm 0.45\%$) to prove this is not random noise.
- **Affect on Acceptance:** Likely to trigger a Major Revision. Reviewers require statistical rigor when comparing heavily overlapping metrics.

### Criticism 4: Unexplained Threshold Derivations
- **Evidence:** Section III-C states: *"the system establishes explicit distributional thresholds for normalized feature vectors (e.g., speed\_ratio > 3.0 and density\_ratio > 7.0)."* The manuscript never explains how 3.0 or 7.0 were chosen.
- **Severity:** Minor
- **Recommendation:** Add a single sentence clarifying whether these thresholds were derived empirically via validation set percentiles (e.g., the 99th percentile of the training distribution) or chosen heuristically.
- **Affect on Acceptance:** Unlikely to affect acceptance, but addressing it improves scientific rigor.

---

## Final Recommendation
**Recommendation: Reject (with encouragement to resubmit)**

**Final Verdict:** While the manuscript is beautifully written and highly honest, it suffers from a fatal experimental flaw: the proposed algorithmic contributions (`AdaptiveFedAvg` and OOD Mitigation) are either entirely unevaluated or evaluated on a dataset that admittedly fails to test their capabilities. A conference paper cannot be accepted when the primary proposed algorithm performs identically to the baseline due to inadequate dataset design, and the secondary contribution (OOD inference) is missing from the results section entirely. The authors should revise the experimental design to include severe noise injection and submit to the next conference cycle.
