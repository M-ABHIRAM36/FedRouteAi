# Section Blueprint: 07_results_blueprint.md

## Structure
5. Results
   - 5.1 Overall Classification Performance
   - 5.2 AdaptiveFedAvg Analysis
   - 5.3 Latency and Communication Overhead
   - 5.4 Discussion

## Purpose
- **5.1 Overall Classification Performance:** Present the global performance metrics for the Centralized MLP (upper bound), standard FedAvg, and AdaptiveFedAvg. Compare Global Accuracy (~82.2%) and Macro F1 scores, referencing the metrics exported in `metrics.json`.
- **5.2 AdaptiveFedAvg Analysis:** Evaluate the specific contribution of the four-factor weighting algorithm. Reference Figure 5 (Convergence) to demonstrate how the temporal stability gate ($g_k$) prevents model divergence compared to size-proportional standard FedAvg during highly volatile training rounds.
- **5.3 Latency and Communication Overhead:** Report the exact systems-level measurements.
  - *Latency:* Average edge inference time per sample (ms), proving that OOD logic does not break real-time V2X constraints.
  - *Communication:* Total bytes exchanged per round, proving the efficiency of the architecture.
- **5.5 Discussion:** Synthesize the findings. How does bridging the gap between federated training and edge inference advance intelligent transportation systems? Acknowledge any limitations.

## Claims to Support (Code-to-Paper Audit)
- Every single metric reported in this section MUST be traceable directly to a CSV or JSON file in `app/ml/artifacts/`.
- If standard FedAvg achieves a marginally higher Macro F1 but lower stability than AdaptiveFedAvg, the text must transparently reflect that trade-off, strictly adhering to the experimental data.

## Reviewer Checklist
- [x] Does the structure exactly follow the blueprint (Experiment $\rightarrow$ Result)?
- [x] Are the quantitative claims backed by the actual exported logs?
- [x] Is the discussion grounded in the empirical evidence rather than speculation?
