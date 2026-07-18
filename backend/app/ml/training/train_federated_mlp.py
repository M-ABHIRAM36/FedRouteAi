"""
Federated Learning Simulation Orchestrator (Flower + FedAvg) using multiprocessing.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path
import multiprocessing
import threading

import numpy as np
import pandas as pd
import torch
import flwr as fl

from app.ml.training.federated_client import RegionalFedRouteClient
from app.ml.training.federated_server import get_strategy

logger = logging.getLogger(__name__)


def seed_everything(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def start_flower_client(cid: str, data_dir: Path):
    """Entry point for a client process."""
    # Ensure reproducible client runs
    seed_everything(42 + int(cid))
    
    # Optional: stagger client start times slightly to prevent connection flood
    time.sleep(0.5 * int(cid))
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    region_id = f"REGION_{int(cid)+1:02d}"
    client = RegionalFedRouteClient(region_id, data_dir, device).to_client()
    
    fl.client.start_client(server_address="127.0.0.1:8080", client=client)


def run_simulation(data_dir: Path, global_feature_table: Path, output_dir: Path, num_rounds: int = 30):
    seed_everything(42)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    config_dict = {
        "learning_rate": 1e-3,
        "optimizer": "AdamW",
        "batch_size": 128,
        "local_epochs": 3,
        "num_rounds": num_rounds,
        "architecture_name": "EventClassifierMLP",
        "random_seed": 42
    }
    (output_dir / "config.json").write_text(json.dumps(config_dict, indent=2), encoding="utf-8")
    
    logger.info("=" * 70)
    logger.info(f"FedRouteAI — Federated FL (Multiprocess) (Device: {device})")
    logger.info("=" * 70)

    client_metrics_file = output_dir / "client_metrics.csv"
    if not client_metrics_file.exists():
        client_metrics_file.write_text("Round,Client_ID,Training_Loss,Validation_Loss,Validation_Macro_F1,Training_Time,Dataset_Size\n", encoding="utf-8")
    
    round_tracker = {"current_round": 1}
    
    def fit_metrics_aggregation_fn(results: list[tuple[int, dict]]) -> dict:
        current_round = round_tracker["current_round"]
        lines = []
        for num_examples, metrics in results:
            lines.append(
                f"{current_round},{metrics.get('region_id', 'UNK')},{metrics.get('train_loss', 0):.4f},"
                f"{metrics.get('val_loss', 0):.4f},{metrics.get('val_macro_f1', 0):.4f},"
                f"{metrics.get('train_time', 0):.4f},{metrics.get('dataset_size', num_examples)}"
            )
        with open(client_metrics_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
            
        round_tracker["current_round"] += 1
        return {}
    
    strategy = get_strategy(global_feature_table, output_dir, device, num_rounds)
    strategy.fit_metrics_aggregation_fn = fit_metrics_aggregation_fn

    start_time = time.time()
    
    # 1. Start the 8 clients as separate background processes
    client_processes = []
    for i in range(8):
        p = multiprocessing.Process(target=start_flower_client, args=(str(i), data_dir))
        p.daemon = True  # kill client when main process exits
        p.start()
        client_processes.append(p)
        
    logger.info("Started 8 Flower clients in background processes.")
    
    # 2. Start the Flower server in the main process
    logger.info("Starting Flower Server...")
    history = fl.server.start_server(
        server_address="127.0.0.1:8080",
        config=fl.server.ServerConfig(num_rounds=num_rounds),
        strategy=strategy,
    )
    
    total_time = time.time() - start_time
    logger.info(f"Federated Learning completed in {total_time:.2f}s")
    
    # Process history
    if history and history.losses_centralized:
        rounds = [r for r, _ in history.losses_centralized]
        losses = [l for _, l in history.losses_centralized]
        
        accs = dict(history.metrics_centralized.get("accuracy", []))
        f1s = dict(history.metrics_centralized.get("macro_f1", []))
        
        df_history = pd.DataFrame({
            "Round": rounds,
            "Global Loss": losses,
            "Global Accuracy": [accs.get(r, 0.0) for r in rounds],
            "Global Macro F1": [f1s.get(r, 0.0) for r in rounds],
            "Participating Clients": 8,
            "Total Time (s)": round(total_time, 2)
        })
        df_history.to_csv(output_dir / "federated_history.csv", index=False)
        logger.info(f"Saved federated history to {output_dir / 'federated_history.csv'}")
        
    # Wait for clients to terminate gracefully or force terminate
    for p in client_processes:
        p.terminate()
        p.join(timeout=1.0)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Required for multiprocessing on Windows
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="Run FL Simulation via Multiprocessing.")
    parser.add_argument(
        "--data-dir",
        default="data/calibration/high/features",
        help="Directory containing regional feature_table_REGION_XX.parquet files.",
    )
    parser.add_argument(
        "--global-feature-table",
        default="data/calibration/high/features/feature_table.parquet",
        help="Path to global feature_table.parquet for centralized evaluation.",
    )
    parser.add_argument(
        "--output-dir",
        default="app/ml/artifacts/federated",
        help="Directory to write all federated artifacts.",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=30,
        help="Number of FL communication rounds.",
    )
    args = parser.parse_args()

    run_simulation(
        data_dir=Path(args.data_dir),
        global_feature_table=Path(args.global_feature_table),
        output_dir=Path(args.output_dir),
        num_rounds=args.rounds
    )
