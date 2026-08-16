"""HTTP client that feeds simulator ticks into the trusted live endpoint."""
from __future__ import annotations

from datetime import datetime
import time

import httpx


class LiveIngestionClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        source_id: str,
        run_id: str,
        *,
        max_attempts: int = 3,
        timeout_seconds: float = 30.0,
    ):
        self.endpoint = f"{base_url.rstrip('/')}/api/v1/ingest/live/batch"
        self.api_key = api_key
        self.source_id = source_id
        self.run_id = run_id
        self.max_attempts = max_attempts
        self.timeout_seconds = timeout_seconds

    def ingest(self, tick_number: int, observations: list[dict]) -> dict:
        payload = {
            "source_id": self.source_id,
            "run_id": self.run_id,
            "batch_id": f"tick-{tick_number:08d}",
            "tick_number": tick_number,
            "observations": [
                {
                    "observation_id": f"{tick_number}:{row['vehicle_id']}",
                    **row,
                    "timestamp": _isoformat(row["timestamp"]),
                }
                for row in observations
            ],
        }
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = httpx.post(
                    self.endpoint,
                    json=payload,
                    headers={"X-Live-Ingest-Key": self.api_key},
                    timeout=self.timeout_seconds,
                )
                if response.status_code < 500:
                    response.raise_for_status()
                    return response.json()
                last_error = RuntimeError(f"ingestion returned HTTP {response.status_code}: {response.text}")
            except httpx.HTTPStatusError:
                raise
            except (httpx.TransportError, RuntimeError) as error:
                last_error = error
            if attempt < self.max_attempts:
                time.sleep(0.5 * attempt)
        raise RuntimeError(f"ingestion failed after {self.max_attempts} attempts: {last_error}")


def _isoformat(value) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)
