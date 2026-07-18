"""
Feature Pipeline
-----------------
Orchestrates the 7-stage process that turns raw data into a training-ready
feature table. Each stage is a distinct, loggable step — easy to debug,
easy to extend (swap out one stage without touching the others).

Stages:
  1. Load         — pull DataFrames from a FeatureSource
  2. Window       — slide 20-min tumbling windows, extract ratio features
  3. Encode       — encode label strings to integers, drop neighbor_effect rows
  4. Normalize    — ensure features are in consistent numeric ranges (already
                    done in windowing.py for most; this stage handles any
                    global normalization if needed later)
  5. Split        — stratified 80/20 train/test + per-region splits
  6. Save         — write parquet files to artifacts/feature_tables/
  7. Report       — print EDA summary (label distribution, feature stats)

Usage (CLI):
    cd backend
    PYTHONPATH=. python app/ml/features/pipeline.py --source csv
    PYTHONPATH=. python app/ml/features/pipeline.py --source db

Usage (programmatic):
    from app.ml.features.pipeline import FeaturePipeline, PipelineResult
    from app.ml.features.datasource import CSVSource

    source = CSVSource(gps_path=..., segments_path=..., memory_path=...)
    pipeline = FeaturePipeline(source, output_dir="app/ml/artifacts/feature_tables")
    result = pipeline.run()
    # result.train_df, result.test_df, result.region_dfs
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from app.ml.features.datasource import FeatureSource
from app.ml.features.windowing import extract_windowed_features, FEATURE_COLUMNS

logger = logging.getLogger(__name__)

# Label → integer mapping (canonical, matches constants.EventType order)
# "normal" = 0 so that the model's default/uncertain prediction is "normal"
LABEL_TO_IDX: dict[str, int] = {
    "normal": 0,
    "congestion": 1,
    "construction": 2,
    "flood": 3,
    "road_block": 4,
    "road_damage": 5,
    "accident": 6,
    "diversion": 7,
}
IDX_TO_LABEL: dict[int, str] = {v: k for k, v in LABEL_TO_IDX.items()}


@dataclass
class PipelineResult:
    """All outputs from a pipeline run."""
    full_df: pd.DataFrame                       # all windows, with encoded labels
    train_df: pd.DataFrame                      # 80% stratified split
    test_df: pd.DataFrame                       # 20% stratified split
    region_dfs: dict[str, pd.DataFrame] = field(default_factory=dict)  # per-region subsets
    label_distribution: dict[str, int] = field(default_factory=dict)
    feature_stats: pd.DataFrame | None = None


class FeaturePipeline:
    """Runs the 7 pipeline stages and returns a PipelineResult."""

    def __init__(
        self,
        source: FeatureSource,
        output_dir: str | Path = "app/ml/artifacts/feature_tables",
        test_size: float = 0.20,
        random_state: int = 42,
    ) -> None:
        self.source = source
        self.output_dir = Path(output_dir)
        self.test_size = test_size
        self.random_state = random_state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> PipelineResult:
        """Execute all 7 stages in sequence and return the result."""
        logger.info("FeaturePipeline: starting. Source: %s", self.source.description())

        # Stage 1 — Load
        gps_df, segments_df, memory_df = self._stage_load()

        # Stage 2 — Window & extract features
        windowed_df = self._stage_window(gps_df, segments_df, memory_df)

        # Stage 3 — Encode labels to integers, filter unknown labels
        encoded_df = self._stage_encode(windowed_df)

        # Stage 4 — Normalize (currently a no-op beyond what windowing did;
        #           reserved for future global scaling if needed)
        normalized_df = self._stage_normalize(encoded_df)

        # Stage 5 — Stratified train/test split + per-region subsets
        train_df, test_df, region_dfs = self._stage_split(normalized_df)

        # Stage 6 — Save parquet outputs
        self._stage_save(normalized_df, train_df, test_df, region_dfs)

        # Stage 7 — EDA report
        label_dist, feat_stats = self._stage_report(normalized_df)

        logger.info("FeaturePipeline: complete. %d training rows, %d test rows.",
                    len(train_df), len(test_df))
        return PipelineResult(
            full_df=normalized_df,
            train_df=train_df,
            test_df=test_df,
            region_dfs=region_dfs,
            label_distribution=label_dist,
            feature_stats=feat_stats,
        )

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    def _stage_load(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        logger.info("Stage 1/7: Load")
        gps_df, segments_df, memory_df = self.source.load()
        logger.info("  GPS pings: %d rows | Segments: %d | Memory: %d",
                    len(gps_df), len(segments_df), len(memory_df))
        return gps_df, segments_df, memory_df

    def _stage_window(
        self,
        gps_df: pd.DataFrame,
        segments_df: pd.DataFrame,
        memory_df: pd.DataFrame,
    ) -> pd.DataFrame:
        logger.info("Stage 2/7: Window & extract features")
        df = extract_windowed_features(gps_df, segments_df, memory_df)
        logger.info("  Produced %d feature windows", len(df))
        if len(df) == 0:
            raise RuntimeError(
                "No feature windows produced. Check that gps_pings_all.csv "
                "has non-null 'label' and matching segment_historical_memory rows."
            )
        return df

    def _stage_encode(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Stage 3/7: Encode labels")
        # Keep only known labels (LABEL_TO_IDX); unknown labels (e.g. stray strings) → drop
        before = len(df)
        df = df[df["label"].isin(LABEL_TO_IDX)].copy()
        dropped = before - len(df)
        if dropped:
            logger.info("  Dropped %d rows with unrecognized labels", dropped)

        df["label_idx"] = df["label"].map(LABEL_TO_IDX)
        logger.info("  Label distribution (after encode):")
        for label, count in df["label"].value_counts().items():
            logger.info("    %-30s %d", label, count)
        return df

    def _stage_normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Stage 4/7: Normalize (pass-through — ratios already unit-scale)")
        # The ratio features (0-3) are already relative to baseline (≈1.0 for normal).
        # hour_of_day_norm is /24. road_type is 0-3. lane_count is 1-4. flood_prone is 0/1.
        # neighbor features mirror ratio features. No further normalization needed for
        # tree models (XGBoost). MLP training uses batch normalization inside the model.
        return df

    def _stage_split(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
        logger.info("Stage 5/7: Train/test split (stratified, test_size=%.0f%%)",
                    self.test_size * 100)
        train_df, test_df = train_test_split(
            df,
            test_size=self.test_size,
            stratify=df["label_idx"],
            random_state=self.random_state,
        )
        logger.info("  Train: %d rows | Test: %d rows", len(train_df), len(test_df))

        region_dfs: dict[str, pd.DataFrame] = {}
        for region_id, region_df in df.groupby("region_id"):
            if len(region_df) > 0:
                region_dfs[str(region_id)] = region_df.reset_index(drop=True)
        logger.info("  Per-region splits: %d regions", len(region_dfs))

        return train_df.reset_index(drop=True), test_df.reset_index(drop=True), region_dfs

    def _stage_save(
        self,
        full_df: pd.DataFrame,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        region_dfs: dict[str, pd.DataFrame],
    ) -> None:
        logger.info("Stage 6/7: Save -> %s", self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        full_df.to_parquet(self.output_dir / "feature_table.parquet", index=False)
        train_df.to_parquet(self.output_dir / "feature_table_train.parquet", index=False)
        test_df.to_parquet(self.output_dir / "feature_table_test.parquet", index=False)

        for region_id, rdf in region_dfs.items():
            rdf.to_parquet(
                self.output_dir / f"feature_table_{region_id}.parquet", index=False
            )

        logger.info("  Saved: feature_table.parquet, _train, _test, %d region files",
                    len(region_dfs))

    def _stage_report(self, df: pd.DataFrame) -> tuple[dict[str, int], pd.DataFrame]:
        logger.info("Stage 7/7: EDA report")
        label_dist = df["label"].value_counts().to_dict()

        print("\n" + "=" * 60)
        print("FEATURE PIPELINE — EDA REPORT")
        print("=" * 60)
        print(f"Total windows : {len(df):,}")
        print(f"Unique segments: {df['segment_id'].nunique()}")
        print(f"Regions        : {df['region_id'].nunique()}")
        print(f"\nLabel distribution:")
        for label, count in sorted(label_dist.items(), key=lambda x: -x[1]):
            pct = count / len(df) * 100
            print(f"  {label:<30} {count:>8,}  ({pct:.1f}%)")

        feat_stats = df[FEATURE_COLUMNS].describe().T
        print(f"\nFeature statistics (10 features):")
        print(feat_stats[["mean", "std", "min", "max"]].to_string())
        print("=" * 60 + "\n")

        return label_dist, feat_stats


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    # Allow running from backend/ with PYTHONPATH=.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Build the ML feature table from raw data."
    )
    parser.add_argument(
        "--source", choices=["csv", "db"], default="csv",
        help="Data source: 'csv' (default) reads from data/raw/; 'db' reads from PostgreSQL."
    )
    parser.add_argument(
        "--output-dir", default="app/ml/artifacts/feature_tables",
        help="Directory to write parquet files to."
    )
    args = parser.parse_args()

    if args.source == "csv":
        from app.ml.features.datasource import CSVSource
        # Resolve fedrouteai/ root: pipeline.py is at backend/app/ml/features/pipeline.py
        # → parents[0]=features/, [1]=ml/, [2]=app/, [3]=backend/, [4]=fedrouteai/
        here = Path(__file__).resolve()
        base = here.parents[4]  # fedrouteai/
        source = CSVSource(
            gps_path=base / "data/raw/fedrouteai_dataset/global/gps_pings_all.csv",
            segments_path=base / "data/raw/fedrouteai_dataset/road_network/segments.csv",
            memory_path=base / "data/raw/fedrouteai_dataset/global/segment_historical_memory.csv",
        )
    else:
        from app.ml.features.datasource import DatabaseSource
        from app.core.config import settings
        source = DatabaseSource(db_url=settings.DATABASE_URL)

    pipeline = FeaturePipeline(source=source, output_dir=args.output_dir)
    result = pipeline.run()

    # Save label distribution for downstream scripts
    dist_path = Path(args.output_dir) / "label_distribution.json"
    dist_path.write_text(json.dumps(result.label_distribution, indent=2))
    print(f"Label distribution saved to {dist_path}")
    print(f"\nDone. Feature table: {Path(args.output_dir) / 'feature_table.parquet'}")
