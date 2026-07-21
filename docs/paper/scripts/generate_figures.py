import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import numpy as np

# Set high-quality IEEE Conference matplotlib parameters
plt.rcParams.update({
    "text.usetex": False,
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 11,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.facecolor": "white",
    "figure.facecolor": "white",
    "axes.edgecolor": "black",
    "axes.linewidth": 0.5
})

BASE_DIR = r"c:\Users\DELL\Desktop\Major Project\fedrouteai"
OUT_DIR = os.path.join(BASE_DIR, "docs", "paper", "final_compilable_project", "figures")
os.makedirs(OUT_DIR, exist_ok=True)

DATA_DIR = os.path.join(BASE_DIR, "data", "calibration", "high", "features", "feature_table.parquet")
FEDAVG_HIST = os.path.join(BASE_DIR, "results", "fedavg", "federated_history.csv")
ADAPTIVE_HIST = os.path.join(BASE_DIR, "results", "adaptive", "adaptive_history.csv")
CONFUSION_MATRIX = os.path.join(BASE_DIR, "app", "ml", "artifacts", "adaptive_federated", "confusion_matrix.csv")

IEEE_BLUE = "#0066CC"

def plot_class_distribution():
    print("Generating Figure 9: Class Distribution...")
    df = pd.read_parquet(DATA_DIR)
    counts = df['label'].value_counts()
    
    plt.figure(figsize=(6, 3.5))
    bars = plt.barh(counts.index, counts.values, color=IEEE_BLUE, edgecolor="black", linewidth=0.5)
    plt.xscale('log')
    plt.xlabel('Number of Samples (Log Scale)')
    plt.ylabel('Traffic Anomaly Class')
    plt.grid(True, which="both", ls=":", lw=0.4, color="gray", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig9_class_distribution.png"))
    plt.close()

def plot_training_convergence():
    print("Generating Figure 7: Training Convergence...")
    fedavg = pd.read_csv(FEDAVG_HIST)
    adaptive = pd.read_csv(ADAPTIVE_HIST)
    
    plt.figure(figsize=(6, 3.5))
    plt.plot(fedavg['Round'], fedavg['Global Accuracy'], label="Standard FedAvg", linestyle='--', marker='o', markersize=3, color="black", linewidth=1.0)
    plt.plot(adaptive['Round'], adaptive['Global Accuracy'], label="AdaptiveFedAvg", linestyle='-', marker='s', markersize=3, color=IEEE_BLUE, linewidth=1.5)
    plt.xlabel('Federated Communication Round')
    plt.ylabel('Validation Accuracy')
    plt.legend(frameon=True, edgecolor="black", fontsize=8)
    plt.grid(True, ls=":", lw=0.4, color="gray", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig7_training_convergence.png"))
    plt.close()

def plot_confusion_matrix():
    print("Generating Figure 8: Confusion Matrix...")
    cm_df = pd.read_csv(CONFUSION_MATRIX, index_col=0)
    plt.figure(figsize=(5, 4.2))
    sns.heatmap(cm_df, annot=True, fmt='d', cmap='Blues', cbar=False, linewidths=0.5, linecolor="black")
    plt.xlabel('Predicted Label')
    plt.ylabel('True Label')
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig8_confusion_matrix.png"))
    plt.close()

if __name__ == "__main__":
    plot_class_distribution()
    plot_training_convergence()
    plot_confusion_matrix()
    print("Statistical figures generated successfully.")
