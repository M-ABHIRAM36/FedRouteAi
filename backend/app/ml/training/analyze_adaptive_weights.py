"""
AdaptiveFedAvg Post-Experiment Analysis Module
----------------------------------------------
Verifies the correctness of the adaptive weighting mechanics, generates
publication-quality visualizations, and produces an automated markdown report.

Usage:
    cd backend
    PYTHONPATH=. python app/ml/training/analyze_adaptive_weights.py
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import logging

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)

def verify_constraints(df: pd.DataFrame, q_floor: float, beta: float, g_min: float) -> list[str]:
    """Verify mathematical constraints of the weighting factors."""
    anomalies = []
    
    # 1. Sum of normalized weights == 1 per round
    round_sums = df.groupby('round')['normalized_weight'].sum()
    for rnd, total in round_sums.items():
        if not math.isclose(total, 1.0, rel_tol=1e-4, abs_tol=1e-4):
            anomalies.append(f"Round {rnd}: Weights sum to {total:.6f} != 1.0")
            
    # 2. 0 <= normalized_weight <= 1
    out_of_bounds_w = df[(df['normalized_weight'] < 0) | (df['normalized_weight'] > 1.0001)]
    if not out_of_bounds_w.empty:
        anomalies.append(f"Found {len(out_of_bounds_w)} instances of normalized_weight out of bounds [0, 1].")
        
    # 3. quality >= q_floor
    out_of_bounds_q = df[df['quality'] < (q_floor - 1e-5)]
    if not out_of_bounds_q.empty:
        anomalies.append(f"Found {len(out_of_bounds_q)} instances of quality < q_floor ({q_floor}).")
        
    # 4. 1 <= rarity_bonus <= 1 + beta
    out_of_bounds_rho = df[(df['rarity_bonus'] < 1.0 - 1e-5) | (df['rarity_bonus'] > 1.0 + beta + 1e-5)]
    if not out_of_bounds_rho.empty:
        anomalies.append(f"Found {len(out_of_bounds_rho)} instances of rarity_bonus outside [1, 1+{beta}].")
        
    # 5. g_min <= gate <= 1
    out_of_bounds_g = df[(df['gate'] < g_min - 1e-5) | (df['gate'] > 1.0001)]
    if not out_of_bounds_g.empty:
        anomalies.append(f"Found {len(out_of_bounds_g)} instances of gate outside [{g_min}, 1].")
        
    return anomalies

def generate_plots(df: pd.DataFrame, output_dir: Path):
    """Generate publication-quality plots."""
    sns.set_theme(style="whitegrid")
    
    # 1. Weight Evolution (Line Plot)
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x='round', y='normalized_weight', hue='region_id', marker='o')
    plt.title("Adaptive Weight Evolution per Client", fontsize=14)
    plt.xlabel("Communication Round", fontsize=12)
    plt.ylabel("Normalized Weight (W_k)", fontsize=12)
    plt.legend(title="Region", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_dir / "weight_evolution.png", dpi=300)
    plt.close()
    
    # 2. Heatmap of Weights (Region vs Round)
    pivot_df = df.pivot(index='region_id', columns='round', values='normalized_weight')
    plt.figure(figsize=(12, 6))
    sns.heatmap(pivot_df, cmap="YlGnBu", annot=False, fmt=".3f", cbar_kws={'label': 'Normalized Weight'})
    plt.title("Heatmap of Client Weights Across Rounds", fontsize=14)
    plt.xlabel("Communication Round", fontsize=12)
    plt.ylabel("Region", fontsize=12)
    plt.tight_layout()
    plt.savefig(output_dir / "heatmap_weights.png", dpi=300)
    plt.close()
    
    # 3. Quality vs Weight (Scatter Plot)
    plt.figure(figsize=(8, 6))
    sns.scatterplot(data=df, x='quality', y='normalized_weight', hue='region_id', alpha=0.7)
    plt.title("Quality Factor vs Final Normalized Weight", fontsize=14)
    plt.xlabel("Quality Factor (max(Q_FLOOR, Val F1))", fontsize=12)
    plt.ylabel("Normalized Weight", fontsize=12)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_dir / "quality_vs_weight.png", dpi=300)
    plt.close()
    
    # 4. Rarity Bonus Distribution
    plt.figure(figsize=(8, 6))
    sns.histplot(data=df, x='rarity_bonus', bins=20, kde=True, color='purple')
    plt.title("Distribution of Rarity Bonus (\u03c1_k)", fontsize=14)
    plt.xlabel("Rarity Bonus Multiplier", fontsize=12)
    plt.ylabel("Frequency", fontsize=12)
    plt.tight_layout()
    plt.savefig(output_dir / "rarity_bonus_distribution.png", dpi=300)
    plt.close()
    
    # 5. Gate Distribution
    plt.figure(figsize=(8, 6))
    sns.histplot(data=df, x='gate', bins=20, kde=False, color='red')
    plt.title("Distribution of Reliability Gate (g_k)", fontsize=14)
    plt.xlabel("Gate Value", fontsize=12)
    plt.ylabel("Frequency", fontsize=12)
    plt.yscale("log") # Log scale helps see rare gate activations
    plt.tight_layout()
    plt.savefig(output_dir / "gate_distribution.png", dpi=300)
    plt.close()

def generate_summary_csv(df: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    """Compute per-region averages and save to CSV."""
    summary = df.groupby('region_id').agg(
        mean_weight=('normalized_weight', 'mean'),
        std_weight=('normalized_weight', 'std'),
        mean_quality=('quality', 'mean'),
        mean_gate=('gate', 'mean'),
        mean_rarity_bonus=('rarity_bonus', 'mean'),
        mean_f1=('val_macro_f1', 'mean')
    ).reset_index()
    
    summary.to_csv(output_dir / "adaptive_summary.csv", index=False)
    return summary

def generate_markdown_report(
    df: pd.DataFrame, 
    summary: pd.DataFrame, 
    anomalies: list[str], 
    output_dir: Path
):
    """Generate an automated markdown report explaining the FL dynamics."""
    highest_weight = summary.loc[summary['mean_weight'].idxmax()]
    lowest_weight = summary.loc[summary['mean_weight'].idxmin()]
    most_consistent = summary.loc[summary['std_weight'].fillna(0).idxmin()]
    highest_rarity = summary.loc[summary['mean_rarity_bonus'].idxmax()]
    
    gate_activations = df[df['gate'] < 0.99]
    gate_clients = gate_activations['region_id'].unique().tolist()
    
    report = [
        "# AdaptiveFedAvg Analysis Report",
        "",
        "## 1. Constraint Verification",
    ]
    
    if not anomalies:
        report.append("✅ All mathematical constraints passed successfully. No anomalies detected.")
    else:
        report.append("❌ Anomalies detected:")
        for a in anomalies:
            report.append(f"- {a}")
            
    report.extend([
        "",
        "## 2. Behavioral Highlights",
        "",
        f"- **Highest Weighted Client**: `{highest_weight['region_id']}` (Mean Weight: {highest_weight['mean_weight']:.4f})",
        f"  - Driven by high dataset size or consistently high quality.",
        f"- **Lowest Weighted Client**: `{lowest_weight['region_id']}` (Mean Weight: {lowest_weight['mean_weight']:.4f})",
        f"- **Most Consistent Client**: `{most_consistent['region_id']}` (Std Dev: {most_consistent['std_weight']:.4f})",
        f"- **Highest Rarity Bonus**: `{highest_rarity['region_id']}` (Mean Bonus: {highest_rarity['mean_rarity_bonus']:.4f})",
        f"  - This region contributed the highest proportion of rare events.",
        "",
        "## 3. Reliability Gate Activations",
    ])
    
    if len(gate_activations) == 0:
        report.append("No gate activations occurred. All clients maintained an EMA F1 above the threshold.")
    else:
        report.append(f"The reliability gate activated {len(gate_activations)} times across {len(gate_clients)} clients:")
        for client in gate_clients:
            client_acts = gate_activations[gate_activations['region_id'] == client]
            report.append(f"- `{client}`: {len(client_acts)} rounds affected (Minimum gate value: {client_acts['gate'].min():.4f})")
            
    report.extend([
        "",
        "## 4. Visualizations",
        "The following visualizations have been generated for publication:",
        "- `weight_evolution.png`: Trajectories of client weights across rounds.",
        "- `heatmap_weights.png`: Detailed heat map of contribution per round.",
        "- `quality_vs_weight.png`: Correlation between model quality and final weight.",
        "- `rarity_bonus_distribution.png`: Histogram of the rare-event multiplier.",
        "- `gate_distribution.png`: Frequency of reliability gate activations.",
        "",
        "## 5. Conclusion",
        "The AdaptiveFedAvg mechanism operated " + ("as designed." if not anomalies else "with anomalies.")
    ])
    
    with open(output_dir / "analysis_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report))

def main():
    parser = argparse.ArgumentParser(description="Analyze AdaptiveFedAvg weights")
    parser.add_argument("--weights-csv", default="app/ml/artifacts/adaptive_federated/adaptive_weights.csv", help="Path to adaptive_weights.csv")
    parser.add_argument("--output-dir", default="app/ml/artifacts/adaptive_federated/analysis", help="Directory for plots and reports")
    parser.add_argument("--q-floor", type=float, default=0.10)
    parser.add_argument("--beta", type=float, default=0.30)
    parser.add_argument("--g-min", type=float, default=0.50)
    
    args = parser.parse_args()
    
    weights_path = Path(args.weights_csv)
    output_dir = Path(args.output_dir)
    
    if not weights_path.exists():
        logger.error(f"Weights CSV not found: {weights_path}")
        return
        
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(weights_path)
    
    logger.info("1. Verifying constraints...")
    anomalies = verify_constraints(df, args.q_floor, args.beta, args.g_min)
    if anomalies:
        for a in anomalies:
            logger.warning(a)
    else:
        logger.info("All constraints verified successfully.")
        
    logger.info("2. Computing summaries...")
    summary_df = generate_summary_csv(df, output_dir)
    
    logger.info("3. Generating plots...")
    generate_plots(df, output_dir)
    
    logger.info("4. Generating markdown report...")
    generate_markdown_report(df, summary_df, anomalies, output_dir)
    
    logger.info(f"Analysis complete. Artifacts saved to {output_dir}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    main()
