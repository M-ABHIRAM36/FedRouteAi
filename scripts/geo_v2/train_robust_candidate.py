"""Train a test-blind robust Geo V2 federated candidate."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.geo_v2.robust_training import RobustTrainingConfig, run_validation_candidate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--feature-variant", choices=("history_current", "history_spatial_strong", "history_spatial"), default="history_current")
    parser.add_argument("--loss", choices=("unweighted_nll", "power_weighted_nll"), default="unweighted_nll")
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--local-epochs", type=int, default=2)
    parser.add_argument("--target-local-anomaly-fraction", type=float, default=0.02)
    args = parser.parse_args()
    config = RobustTrainingConfig(
        feature_variant=args.feature_variant, loss=args.loss, rounds=args.rounds,
        local_epochs=args.local_epochs, target_local_anomaly_fraction=args.target_local_anomaly_fraction,
    )
    output = run_validation_candidate(args.dataset_dir, args.artifact_root, args.experiment_id, config)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
