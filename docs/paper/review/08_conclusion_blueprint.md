# Section Blueprint: 08_conclusion_blueprint.md

## Structure
6. Conclusion

### Paragraph 1: Context & Core Contribution
- **Problem:** Reliable, real-time traffic anomaly detection in intelligent transportation systems is hindered by decentralized data silos, extreme class imbalance, and edge hardware constraints.
- **Solution:** FedRouteAI, a federated learning framework integrating deployment-aware edge inference and an adaptive aggregation strategy.
- **Contribution:** Demonstrates that decentralized training can effectively regularize highly imbalanced telemetry data while satisfying the strict computational requirements of vehicular edge computing.

### Paragraph 2: Empirical Findings
- **Federated Effectiveness:** The federated approaches inherently mitigated the catastrophic overfitting seen in the Centralized MLP baseline, achieving superior generalization (peak accuracy of 82.21%).
- **AdaptiveFedAvg vs. FedAvg:** Standard FedAvg proved highly robust under controlled conditions, performing comparably to the four-factor AdaptiveFedAvg algorithm, which remains suited for environments with severe temporal volatility.
- **Systems Feasibility:** The architecture maintains a minimal communication footprint (207.36 KB per round) and sub-millisecond edge inference latency (0.2069 ms per sample), confirming its viability for real-time edge deployment.

### Paragraph 3: Limitations & Future Work
- **Limitations:** The primary reliance on a synthetic dataset limited the full evaluation of the Out-of-Distribution anomaly warning layer and the temporal reliability gate under physical hardware degradation.
- **Future Work:** Future research will focus on deploying the inference pipeline on physical roadside units to validate the system under real-world sensor noise and network latency.

## Requirements
- Length: Strictly 3 paragraphs, 300-450 words total.
- Tone: Maintain the same objective, evidence-driven IEEE style established in the Results section.
