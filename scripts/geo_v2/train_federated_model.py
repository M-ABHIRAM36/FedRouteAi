"""CLI for additive Geo V2 centralized ablations and federated training."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ml.geo_v2.training import TrainingConfig, run_training  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the Geo V2 8-client adaptive federated MLP.")
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "data" / "geo_v2" / "fedrouteai_dataset_geo_v2_ml_v1")
    parser.add_argument("--artifact-root", type=Path, default=BACKEND / "app" / "ml" / "artifacts" / "geo_v2" / "federated")
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--dropout-rate", type=float, default=0.2)
    parser.add_argument("--optimizer", choices=("Adam", "AdamW"), default="AdamW")
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--centralized-epochs", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--local-epochs", type=int, default=2)
    parser.add_argument("--train-normal-cap", type=int, default=5_000)
    parser.add_argument("--validation-normal-cap", type=int, default=5_000)
    parser.add_argument("--csv-chunk-size", type=int, default=50_000)
    parser.add_argument("--alpha", type=float, default=0.3)
    parser.add_argument("--beta", type=float, default=0.3)
    parser.add_argument("--q-floor", type=float, default=0.10)
    parser.add_argument("--g-threshold", type=float, default=0.15)
    parser.add_argument("--g-min", type=float, default=0.50)
    parser.add_argument("--rare-threshold", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = TrainingConfig(**{
        name: getattr(args, name)
        for name in TrainingConfig.__dataclass_fields__
    })
    output = run_training(args.dataset_dir.resolve(), args.artifact_root.resolve(), args.run_id, config, ROOT)
    print(output)


if __name__ == "__main__":
    main()
