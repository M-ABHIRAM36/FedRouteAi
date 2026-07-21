import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os

BASE_DIR = r"c:\Users\DELL\Desktop\Major Project\fedrouteai"
OUT_DIR = os.path.join(BASE_DIR, "docs", "paper", "final_compilable_project", "figures")
os.makedirs(OUT_DIR, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight"
})

IEEE_BLUE = "#0066CC"

def create_system_architecture():
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    
    # Subsystem background
    edge_box = patches.FancyBboxPatch((0.2, 3.2), 4.5, 1.5, boxstyle="round,pad=0.1", fc="#F5F7FA", ec="#787878", ls="--", lw=0.8)
    ax.add_patch(edge_box)
    ax.text(2.45, 4.4, "Edge Client Layer (Decentralized Nodes)", fontsize=9, fontweight="bold", ha="center")
    
    # Nodes
    node1 = patches.FancyBboxPatch((0.4, 3.4), 1.1, 0.8, boxstyle="round,pad=0.05", fc="white", ec="black", lw=0.8)
    node2 = patches.FancyBboxPatch((1.8, 3.4), 1.1, 0.8, boxstyle="round,pad=0.05", fc="white", ec="black", lw=0.8)
    nodeK = patches.FancyBboxPatch((3.2, 3.4), 1.2, 0.8, boxstyle="round,pad=0.05", fc="white", ec="black", lw=0.8)
    ax.add_patch(node1); ax.text(0.95, 3.8, "Client 1\nTelemetry", ha="center", va="center", fontsize=8)
    ax.add_patch(node2); ax.text(2.35, 3.8, "Client 2\nTelemetry", ha="center", va="center", fontsize=8)
    ax.add_patch(nodeK); ax.text(3.8, 3.8, "Client K\nTelemetry", ha="center", va="center", fontsize=8)
    
    # Historical Memory
    mem_box = patches.FancyBboxPatch((0.5, 1.2), 3.8, 1.0, boxstyle="round,pad=0.1", fc="#E6F0FA", ec=IEEE_BLUE, lw=1.2)
    ax.add_patch(mem_box)
    ax.text(2.4, 1.7, "Historical Memory Module\n(PostgreSQL Zone Baselines $v_{avg}, d_{avg}$)", ha="center", va="center", fontsize=8, color=IEEE_BLUE, fontweight="bold")
    
    # Feature Engineering
    feat_box = patches.FancyBboxPatch((5.2, 1.2), 2.2, 1.0, boxstyle="round,pad=0.1", fc="white", ec="black", lw=0.8)
    ax.add_patch(feat_box)
    ax.text(6.3, 1.7, "Feature Engineering\nNormalized Ratios", ha="center", va="center", fontsize=8)
    
    # MLP Engine
    mlp_box = patches.FancyBboxPatch((8.0, 1.2), 1.8, 1.0, boxstyle="round,pad=0.1", fc="#E6F0FA", ec=IEEE_BLUE, lw=1.2)
    ax.add_patch(mlp_box)
    ax.text(8.9, 1.7, "EventClassifierMLP\n3,240 Params", ha="center", va="center", fontsize=8, color=IEEE_BLUE, fontweight="bold")
    
    # Server & Aggregator
    srv_box = patches.FancyBboxPatch((5.2, 3.4), 2.2, 1.0, boxstyle="round,pad=0.1", fc="white", ec="black", lw=0.8)
    agg_box = patches.FancyBboxPatch((8.0, 3.4), 1.8, 1.0, boxstyle="round,pad=0.1", fc="#E6F0FA", ec=IEEE_BLUE, lw=1.2)
    ax.add_patch(srv_box); ax.text(6.3, 3.9, "FastAPI Backend\nFlower Server", ha="center", va="center", fontsize=8)
    ax.add_patch(agg_box); ax.text(8.9, 3.9, "AdaptiveFedAvg\nAggregator", ha="center", va="center", fontsize=8, color=IEEE_BLUE, fontweight="bold")
    
    # Arrows
    ax.annotate("", xy=(2.4, 2.3), xytext=(2.4, 3.2), arrowprops=dict(arrowstyle="->", color="black", lw=1))
    ax.annotate("", xy=(5.1, 1.7), xytext=(4.4, 1.7), arrowprops=dict(arrowstyle="->", color=IEEE_BLUE, lw=1.2))
    ax.annotate("", xy=(7.9, 1.7), xytext=(7.5, 1.7), arrowprops=dict(arrowstyle="->", color=IEEE_BLUE, lw=1.2))
    ax.annotate("", xy=(8.9, 3.3), xytext=(8.9, 2.3), arrowprops=dict(arrowstyle="->", color="black", lw=1))
    ax.annotate("", xy=(7.9, 3.9), xytext=(7.5, 3.9), arrowprops=dict(arrowstyle="->", color=IEEE_BLUE, lw=1.2))
    
    plt.savefig(os.path.join(OUT_DIR, "fig1_system_architecture.png"))
    plt.close()

if __name__ == "__main__":
    create_system_architecture()
    print("Standalone diagram PNG generated.")
