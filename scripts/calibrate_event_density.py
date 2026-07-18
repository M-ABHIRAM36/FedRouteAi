"""
calibrate_event_density.py
---------------------------
Calibration study for Dataset Generator V2.

Generates THREE datasets at different event densities (Low / Medium / High),
runs the full feature pipeline on each, trains an XGBoost classifier with
identical hyperparameters, and produces a comparison table of:

  1. Event window %          -- dataset coverage
  2. Label distribution      -- per-class window count
  3. Macro F1                -- overall rare-class sensitivity
  4. Per-class F1            -- for the three rarest classes

Design principle: find the SMALLEST event density that achieves target
Macro F1 >= 0.55 and rare-class (accident, diversion, road_block) F1 >= 0.30.

Usage:
    cd backend
    PYTHONPATH=. python ../scripts/calibrate_event_density.py

Outputs:
    data/calibration/low/      -- dataset + features + XGBoost artifacts
    data/calibration/medium/   -- dataset + features + XGBoost artifacts
    data/calibration/high/     -- dataset + features + XGBoost artifacts
    data/calibration/calibration_report.md    -- markdown comparison table
    data/calibration/calibration_summary.csv  -- machine-readable
"""
from __future__ import annotations

import json
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ── Make project paths importable ───────────────────────────────────────────
SCRIPT_DIR    = Path(__file__).resolve().parent
REPO_ROOT     = SCRIPT_DIR.parent
BACKEND_DIR   = REPO_ROOT / "backend"
GENERATOR_DIR = REPO_ROOT / "scripts" / "dataset_generator"

sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(GENERATOR_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Calibration levels ───────────────────────────────────────────────────────
CALIBRATION_LEVELS = {
    "low":    (8,  12),
    "medium": (16, 22),
    "high":   (28, 35),
}

TARGET_MACRO_F1 = 0.55
TARGET_RARE_F1  = 0.30
RARE_CLASSES    = ["accident", "diversion", "road_block"]
LABEL_ORDER     = ["normal", "road_damage", "construction", "congestion",
                   "accident", "flood", "road_block", "diversion"]

CALIB_DIR = REPO_ROOT / "data" / "calibration"


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Dataset generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_dataset_for_level(level_name: str, ev_min: int, ev_max: int) -> Path:
    from generate_dataset import V2Config, main as gen_main
    out_dir = str(CALIB_DIR / level_name / "dataset")
    cfg = V2Config(
        seed=42,
        sim_start=datetime(2026, 7, 7, 0, 0, 0),
        memory_days=10,
        event_days=4,
        events_per_region_per_day_min=ev_min,
        events_per_region_per_day_max=ev_max,
        out_dir=out_dir,
    )
    logger.info(f"  Generating level={level_name}, events/region/day=({ev_min},{ev_max})")
    t0 = time.time()
    gen_main(cfg)
    logger.info(f"  Generated in {time.time()-t0:.0f}s")
    return Path(out_dir)


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Feature pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_feature_pipeline(level_name: str, dataset_dir: Path) -> Path:
    from app.ml.features.datasource import CSVSource
    from app.ml.features.pipeline import FeaturePipeline

    feature_dir = CALIB_DIR / level_name / "features"
    feature_dir.mkdir(parents=True, exist_ok=True)

    source = CSVSource(
        gps_path=dataset_dir / "global" / "gps_pings_all.csv",
        segments_path=dataset_dir / "road_network" / "segments.csv",
        memory_path=dataset_dir / "global" / "segment_historical_memory.csv",
    )
    logger.info(f"  Feature pipeline: level={level_name}")
    t0 = time.time()
    FeaturePipeline(source, output_dir=str(feature_dir)).run()
    logger.info(f"  Pipeline done in {time.time()-t0:.0f}s")
    return feature_dir / "feature_table.parquet"


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: XGBoost training + evaluation
# ─────────────────────────────────────────────────────────────────────────────

def train_and_evaluate(level_name: str, parquet_path: Path) -> dict:
    import xgboost as xgb
    from sklearn.metrics import f1_score, classification_report
    from sklearn.model_selection import train_test_split
    from app.ml.features.windowing import FEATURE_COLUMNS
    from app.ml.features.pipeline import LABEL_TO_IDX, IDX_TO_LABEL
    from app.ml.training.class_weights import (
        compute_class_weights, sample_weights_from_class_weights,
    )

    N_CLASSES = len(LABEL_TO_IDX)
    arts_dir  = CALIB_DIR / level_name / "xgboost"
    arts_dir.mkdir(parents=True, exist_ok=True)

    full_df = pd.read_parquet(parquet_path)

    # Drop classes with fewer than 2 samples (needed for stratified split)
    counts = full_df["label_idx"].value_counts()
    valid  = counts[counts >= 2].index
    df     = full_df[full_df["label_idx"].isin(valid)].copy()
    if len(df) < len(full_df):
        logger.warning(f"  Dropped {len(full_df)-len(df)} rows (classes < 2 samples)")

    train_df, test_df = train_test_split(
        df, test_size=0.20, stratify=df["label_idx"], random_state=42
    )
    X_train = train_df[FEATURE_COLUMNS].values.astype(np.float32)
    y_train = train_df["label_idx"].values.astype(np.int32)
    X_test  = test_df[FEATURE_COLUMNS].values.astype(np.float32)
    y_test  = test_df["label_idx"].values.astype(np.int32)

    logger.info(f"  XGBoost: train={len(X_train):,}, test={len(X_test):,}")

    cw  = compute_class_weights(y_train, n_classes=N_CLASSES)
    sw  = sample_weights_from_class_weights(y_train, cw)

    # Identical hyperparameters for all three levels (controlled comparison)
    model = xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=N_CLASSES,
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )
    t0 = time.time()
    model.fit(X_train, y_train, sample_weight=sw,
              eval_set=[(X_test, y_test)], verbose=False)
    logger.info(f"  Training done in {time.time()-t0:.0f}s")

    y_pred = model.predict(X_test)
    model.save_model(str(arts_dir / "xgboost_baseline.ubj"))

    label_names  = [IDX_TO_LABEL[i] for i in range(N_CLASSES)]
    pc_f1        = f1_score(y_test, y_pred, average=None,
                             labels=list(range(N_CLASSES)), zero_division=0)
    macro_f1     = float(f1_score(y_test, y_pred, average="macro",    zero_division=0))
    weighted_f1  = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))

    report = classification_report(y_test, y_pred, target_names=label_names, digits=4)
    (arts_dir / "classification_report.txt").write_text(report, encoding="utf-8")

    # Feature importance
    raw_fi = model.get_booster().get_score(importance_type="gain")
    fi = {
        FEATURE_COLUMNS[int(k[1:])] if k.startswith("f") and k[1:].isdigit() else k: round(v, 3)
        for k, v in raw_fi.items()
    }
    fi_sorted = dict(sorted(fi.items(), key=lambda x: x[1], reverse=True))

    # Label distribution
    label_dist = full_df.groupby("label_idx").size().reset_index(name="count")
    label_dist["label"] = label_dist["label_idx"].map(IDX_TO_LABEL)
    total_wins    = len(full_df)
    non_normal_w  = int(label_dist.loc[label_dist["label"] != "normal", "count"].sum())
    non_normal_pct = round(non_normal_w / total_wins * 100, 2)

    per_class = {}
    for i, name in enumerate(label_names):
        row = label_dist[label_dist["label"] == name]
        per_class[name] = {
            "windows": int(row["count"].iloc[0]) if len(row) else 0,
            "f1":      round(float(pc_f1[i]), 4),
        }

    metrics = {
        "level":               level_name,
        "total_windows":       total_wins,
        "non_normal_windows":  non_normal_w,
        "non_normal_pct":      non_normal_pct,
        "macro_f1":            round(macro_f1,    4),
        "weighted_f1":         round(weighted_f1, 4),
        "per_class":           per_class,
        "feature_importance_gain": fi_sorted,
    }
    (arts_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    logger.info(
        f"  [{level_name.upper()}] Macro F1={macro_f1:.4f} | "
        f"Non-normal={non_normal_pct:.1f}%"
    )
    return metrics


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Report
# ─────────────────────────────────────────────────────────────────────────────

def write_report(all_metrics: list[dict]) -> None:
    CALIB_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "# FedRouteAI — Event Density Calibration Study",
        "",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> Targets: Macro F1 >= {TARGET_MACRO_F1} | Rare F1 >= {TARGET_RARE_F1}",
        f"> Rare classes: {RARE_CLASSES}",
        "",
        "---",
        "",
        "## Summary",
        "",
    ]

    def mkrow(label, vals):
        return f"| {label} | " + " | ".join(str(v) for v in vals) + " |"

    header = "| Metric | " + " | ".join(m["level"].upper() for m in all_metrics) + " |"
    sep    = "| --- | " + " | ".join("---" for _ in all_metrics) + " |"
    lines += [header, sep]
    lines.append(mkrow("Events/region/day", [CALIBRATION_LEVELS[m["level"]] for m in all_metrics]))
    lines.append(mkrow("Total windows",     [f"{m['total_windows']:,}" for m in all_metrics]))
    lines.append(mkrow("Non-normal windows",
        [f"{m['non_normal_windows']:,} ({m['non_normal_pct']}%)" for m in all_metrics]))
    lines.append(mkrow("**Macro F1**",      [f"**{m['macro_f1']:.4f}**" for m in all_metrics]))
    lines.append(mkrow("Weighted F1",       [f"{m['weighted_f1']:.4f}" for m in all_metrics]))

    lines += ["", "---", "", "## Per-class breakdown", ""]
    h2  = "| Class | " + " | ".join(f"Win-{m['level']}" for m in all_metrics)
    h2 += " | " + " | ".join(f"F1-{m['level']}" for m in all_metrics) + " |"
    s2  = "| --- | " + " | ".join("---" for _ in range(len(all_metrics) * 2)) + " |"
    lines += [h2, s2]

    for label in LABEL_ORDER:
        wins = [m["per_class"].get(label, {"windows": 0})["windows"] for m in all_metrics]
        f1s_raw = [m["per_class"].get(label, {"f1": 0.0})["f1"] for m in all_metrics]
        if label in RARE_CLASSES:
            f1s = [f"**{v:.4f}** {'OK' if v >= TARGET_RARE_F1 else 'low'}" for v in f1s_raw]
        else:
            f1s = [f"{v:.4f}" for v in f1s_raw]
        lines.append(f"| {label} | " + " | ".join(str(w) for w in wins) +
                     " | " + " | ".join(f1s) + " |")

    lines += ["", "---", "", "## Feature importance — leakage check", ""]
    for m in all_metrics:
        lines.append(f"### {m['level'].upper()}")
        lines += ["| Rank | Feature | Gain |", "| --- | --- | --- |"]
        for rank, (feat, gain) in enumerate(list(m["feature_importance_gain"].items())[:8], 1):
            tag = " *(static)*" if feat in ["lane_count", "road_type", "flood_prone"] else ""
            lines.append(f"| {rank} | {feat}{tag} | {gain:.1f} |")
        lines.append("")

    lines += ["---", "", "## Recommendation", ""]
    recommendation = None
    for m in all_metrics:
        if (m["macro_f1"] >= TARGET_MACRO_F1 and
                all(m["per_class"].get(rc, {"f1": 0.0})["f1"] >= TARGET_RARE_F1
                    for rc in RARE_CLASSES)):
            recommendation = m["level"]
            break

    if recommendation:
        m_rec = next(m for m in all_metrics if m["level"] == recommendation)
        lines += [
            f"**Recommended: `{recommendation.upper()}` density "
            f"= events_per_region_per_day={CALIBRATION_LEVELS[recommendation]}**",
            "",
            f"- Non-normal windows: {m_rec['non_normal_pct']}%",
            f"- Macro F1: {m_rec['macro_f1']:.4f} (target >= {TARGET_MACRO_F1})",
            f"- This is the smallest density meeting both targets.",
            f"- Set in `V2Config`: `events_per_region_per_day_min={CALIBRATION_LEVELS[recommendation][0]}`, "
            f"`events_per_region_per_day_max={CALIBRATION_LEVELS[recommendation][1]}`",
        ]
    else:
        lines.append("**No level met both targets.** See notes above for next steps.")

    report_path = CALIB_DIR / "calibration_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Markdown report: {report_path}")

    # CSV
    csv_rows = []
    for m in all_metrics:
        row = {
            "level": m["level"],
            "ev_min": CALIBRATION_LEVELS[m["level"]][0],
            "ev_max": CALIBRATION_LEVELS[m["level"]][1],
            "total_windows": m["total_windows"],
            "non_normal_windows": m["non_normal_windows"],
            "non_normal_pct": m["non_normal_pct"],
            "macro_f1": m["macro_f1"],
            "weighted_f1": m["weighted_f1"],
        }
        for label in LABEL_ORDER:
            pc = m["per_class"].get(label, {"windows": 0, "f1": 0.0})
            row[f"win_{label}"] = pc["windows"]
            row[f"f1_{label}"]  = pc["f1"]
        csv_rows.append(row)
    pd.DataFrame(csv_rows).to_csv(CALIB_DIR / "calibration_summary.csv", index=False)

    # Stdout table
    print("\n" + "=" * 72)
    print("CALIBRATION STUDY RESULTS")
    print("=" * 72)
    print(f"{'Level':<10} {'ev/r/d':^12} {'NonNorm%':^10} {'MacroF1':^10}", end="")
    for rc in RARE_CLASSES:
        print(f"  {rc[:8]:^10}", end="")
    print()
    print("-" * 72)
    for m in all_metrics:
        lo, hi = CALIBRATION_LEVELS[m["level"]]
        print(f"{m['level']:<10} ({lo},{hi}){'':<5} "
              f"{m['non_normal_pct']:>6.1f}%    {m['macro_f1']:>7.4f}   ", end="")
        for rc in RARE_CLASSES:
            f1  = m["per_class"].get(rc, {"f1": 0.0})["f1"]
            ok  = " OK" if f1 >= TARGET_RARE_F1 else "   "
            print(f"  {f1:.4f}{ok}", end="")
        print()
    print("=" * 72)
    if recommendation:
        print(f"\n>>> RECOMMENDED: {recommendation.upper()} "
              f"(events_per_region_per_day={CALIBRATION_LEVELS[recommendation]}) <<<")
    else:
        print("\n>>> No level met targets — see calibration_report.md <<<")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 70)
    logger.info("FedRouteAI — Event Density Calibration Study")
    logger.info(f"Levels: {CALIBRATION_LEVELS}")
    logger.info(f"Targets: Macro F1>={TARGET_MACRO_F1}, rare F1>={TARGET_RARE_F1}")
    logger.info("=" * 70)

    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    all_metrics: list[dict] = []

    for level_name, (ev_min, ev_max) in CALIBRATION_LEVELS.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"LEVEL: {level_name.upper()} — ({ev_min},{ev_max}) events/region/day")
        logger.info(f"{'='*60}")
        t0 = time.time()

        dataset_dir  = generate_dataset_for_level(level_name, ev_min, ev_max)
        parquet_path = run_feature_pipeline(level_name, dataset_dir)
        metrics      = train_and_evaluate(level_name, parquet_path)
        all_metrics.append(metrics)

        logger.info(f"Level {level_name} complete in {time.time()-t0:.0f}s")

    write_report(all_metrics)
    logger.info(f"\nDone. Report: {CALIB_DIR / 'calibration_report.md'}")


if __name__ == "__main__":
    main()
