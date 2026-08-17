"""Perform the non-repeatable final test evaluation for one accepted candidate."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.ml.geo_v2.robust_training import finalize_once  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--test-csv", type=Path, required=True)
    args = parser.parse_args()
    print(finalize_once(args.candidate_dir, args.test_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
