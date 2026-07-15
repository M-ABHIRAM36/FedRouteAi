"""
Launches ONE Flower client for ONE region. Run this once per region
(8 terminals / 8 processes / 8 containers) against a running
flower_server (see backend/app/services/federated_learning/flower_server.py).

Usage:
    python run_client.py --region REGION_01
    python run_client.py --region REGION_02 --server 127.0.0.1:8080

This file intentionally lives OUTSIDE backend/ — in a real deployment
each region's client runs on that region's own infrastructure, with its
own access to that region's own database only. Keeping it a separate
top-level component (rather than a backend/ submodule) reflects that
it's not part of the central API service.
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.federated_learning.flower_client import start_client  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True, help="e.g. REGION_01")
    parser.add_argument("--server", default="127.0.0.1:8080")
    args = parser.parse_args()

    start_client(region_id=args.region, server_address=args.server)


if __name__ == "__main__":
    main()
