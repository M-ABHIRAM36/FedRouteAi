# AdaptiveFedAvg Analysis Report

## 1. Constraint Verification
✅ All mathematical constraints passed successfully. No anomalies detected.

## 2. Behavioral Highlights

- **Highest Weighted Client**: `REGION_03` (Mean Weight: 0.1598)
  - Driven by high dataset size or consistently high quality.
- **Lowest Weighted Client**: `REGION_08` (Mean Weight: 0.0943)
- **Most Consistent Client**: `REGION_08` (Std Dev: 0.0047)
- **Highest Rarity Bonus**: `REGION_08` (Mean Bonus: 1.0555)
  - This region contributed the highest proportion of rare events.

## 3. Reliability Gate Activations
No gate activations occurred. All clients maintained an EMA F1 above the threshold.

## 4. Visualizations
The following visualizations have been generated for publication:
- `weight_evolution.png`: Trajectories of client weights across rounds.
- `heatmap_weights.png`: Detailed heat map of contribution per round.
- `quality_vs_weight.png`: Correlation between model quality and final weight.
- `rarity_bonus_distribution.png`: Histogram of the rare-event multiplier.
- `gate_distribution.png`: Frequency of reliability gate activations.

## 5. Conclusion
The AdaptiveFedAvg mechanism operated as designed.