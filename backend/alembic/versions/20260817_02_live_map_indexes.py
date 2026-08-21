"""Add indexes for live-map snapshot reads."""
from alembic import op


revision = "20260817_02"
down_revision = "20260816_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_live_batches_source_run_received",
        "live_ingestion_batches",
        ["source_id", "run_id", "received_at"],
    )
    op.create_index(
        "ix_gps_pings_batch_vehicle_timestamp",
        "gps_pings",
        ["ingestion_batch_id", "vehicle_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_gps_pings_batch_vehicle_timestamp", table_name="gps_pings")
    op.drop_index("ix_live_batches_source_run_received", table_name="live_ingestion_batches")
