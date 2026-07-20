import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
import numpy as np

# Set paper-style matplotlib parameters
plt.rcParams.update({
    "text.usetex": False,
    "font.family": "serif",
    "font.size": 12,
    "axes.labelsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 12,
    "figure.titlesize": 16,
    "figure.dpi": 300
})

BASE_DIR = r"c:\Users\DELL\Desktop\Major Project\fedrouteai"
OUT_DIR = os.path.join(BASE_DIR, "docs", "paper", "figures")
DATA_DIR = os.path.join(BASE_DIR, "data", "calibration", "high", "features", "feature_table.parquet")
FEDAVG_HIST = os.path.join(BASE_DIR, "results", "fedavg", "federated_history.csv")
ADAPTIVE_HIST = os.path.join(BASE_DIR, "results", "adaptive", "adaptive_history.csv")
CONFUSION_MATRIX = os.path.join(BASE_DIR, "app", "ml", "artifacts", "adaptive_federated", "confusion_matrix.csv")

def plot_class_distribution():
    print("Generating Figure 1: Class Distribution...")
    df = pd.read_parquet(DATA_DIR)
    counts = df['label'].value_counts()
    
    plt.figure(figsize=(10, 6))
    sns.barplot(x=counts.values, y=counts.index, palette="viridis")
    plt.xscale('log')
    plt.xlabel('Number of Samples (Log Scale)')
    plt.ylabel('Traffic Event Class')
    plt.title('Dataset Class Distribution (Imbalanced)')
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig1_class_distribution.png"))
    plt.close()

def plot_training_convergence():
    print("Generating Figure 2: Training Convergence...")
    fedavg = pd.read_csv(FEDAVG_HIST)
    adaptive = pd.read_csv(ADAPTIVE_HIST)
    
    plt.figure(figsize=(10, 6))
    plt.plot(fedavg['Round'], fedavg['Global Accuracy'], label="FedAvg", linestyle='--', marker='o', markersize=4)
    plt.plot(adaptive['Round'], adaptive['Global Accuracy'], label="AdaptiveFedAvg", linewidth=2.5, marker='s', markersize=4)
    plt.xlabel('Federated Communication Round')
    plt.ylabel('Validation Accuracy')
    plt.title('Convergence: FedAvg vs AdaptiveFedAvg')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig2_training_convergence.png"))
    plt.close()

def plot_confusion_matrix():
    print("Generating Figure 3: Confusion Matrix...")
    cm_df = pd.read_csv(CONFUSION_MATRIX, index_col=0)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm_df, annot=True, fmt='d', cmap='Blues', cbar=False)
    plt.xlabel('Predicted Label')
    plt.ylabel('True Label')
    plt.title('OOD-Aware Inference Confusion Matrix')
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "fig3_confusion_matrix.png"))
    plt.close()

if __name__ == "__main__":
    plot_class_distribution()
    plot_training_convergence()
    plot_confusion_matrix()
    print("All figures generated successfully.")
