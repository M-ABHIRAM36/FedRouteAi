"""Create additive Geo V2 features using the fixed train-prehistory baseline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.geo_v2.dataset import join_targets  # noqa: E402
from app.ml.geo_v2.features import CausalFeatureBuilder, FEATURE_VARIANTS, METADATA_COLUMNS, TrainScaler  # noqa: E402
from app.services.geo_v2.network import load_overpass_json  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def prepare(source: Path, output: Path, osm: Path) -> Path:
    """Derive train and validation only; test is structurally excluded."""
    output.mkdir(parents=True, exist_ok=False)
    network = load_overpass_json(osm)
    builder = CausalFeatureBuilder(network)
    baseline = pd.read_csv(source / "normal_prehistory_baselines" / "train.csv")
    raw_tables = {}
    for split in ("train", "validation"):
        states = pd.read_csv(source / "traffic_states" / f"{split}.csv")
        truth = pd.read_csv(source / "scenario_ground_truth" / f"{split}.csv")
        raw_tables[split] = join_targets(builder.build(states, baseline, variant="history_spatial"), truth, split)
    columns = FEATURE_VARIANTS["history_spatial"]
    scaler = TrainScaler.fit(raw_tables["train"], columns)
    table_dir = output / "feature_tables" / "history_spatial"
    table_dir.mkdir(parents=True)
    for split in ("train", "validation"):
        table = scaler.transform(raw_tables[split], columns)[[*METADATA_COLUMNS, *columns, "label", "label_idx"]]
        table.to_csv(table_dir / f"{split}.csv", index=False)
    (output / "scalers").mkdir()
    _write_json(output / "scalers" / "history_spatial.json", {"fit_split": "train", "feature_order": columns, **scaler.as_dict()})
    _write_json(output / "manifest.json", {
        "dataset_version": "geo_v2_ml_v1_fixed_contract_v2", "source_dataset_version": "geo_v2_ml_v1",
        "network_version": "beeramguda-osm-20260506", "derived_splits": ["train", "validation"],
        "test_derived": False, "baseline_source": "canonical train normal prehistory only",
        "history_cadence_seconds": 120, "source_dataset_untouched": True,
    })
    return output


def finalize_test(source: Path, derived: Path, osm: Path) -> Path:
    """Derive test only after model selection with the frozen train-fit scaler."""
    target = derived / "feature_tables" / "history_spatial" / "test.csv"
    if target.exists():
        raise FileExistsError("derived final test already exists")
    network = load_overpass_json(osm)
    baseline = pd.read_csv(source / "normal_prehistory_baselines" / "train.csv")
    states = pd.read_csv(source / "traffic_states" / "test.csv")
    truth = pd.read_csv(source / "scenario_ground_truth" / "test.csv")
    raw = join_targets(CausalFeatureBuilder(network).build(states, baseline, variant="history_spatial"), truth, "test")
    saved = json.loads((derived / "scalers" / "history_spatial.json").read_text(encoding="utf-8"))
    columns = saved["feature_order"]
    scaler = TrainScaler(
        {name: saved["mean"][name] for name in columns},
        {name: saved["scale"][name] for name in columns},
    )
    table = scaler.transform(raw, columns)[[*METADATA_COLUMNS, *columns, "label", "label_idx"]]
    table.to_csv(target, index=False)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "finalize-test"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--osm", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.output, args.osm) if args.mode == "prepare" else finalize_test(args.source, args.output, args.osm)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
