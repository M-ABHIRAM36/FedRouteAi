"""Add live ingestion receipts, observation identities, and current state.

This is an extension migration. The original project has no committed
baseline revision, so it assumes the existing V1 tables already exist.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260816_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_ingestion_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.String(length=60), nullable=False),
        sa.Column("run_id", sa.String(length=80), nullable=False),
        sa.Column("batch_id", sa.String(length=80), nullable=False),
        sa.Column("tick_number", sa.Integer(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("segment_count", sa.Integer(), nullable=False),
        sa.Column("region_count", sa.Integer(), nullable=False),
        sa.Column("average_speed_kmph", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "run_id", "batch_id", name="uq_live_batch_identity"),
    )
    op.create_index("ix_live_ingestion_batches_source_id", "live_ingestion_batches", ["source_id"])
    op.create_index("ix_live_ingestion_batches_observed_at", "live_ingestion_batches", ["observed_at"])
    op.add_column("gps_pings", sa.Column("ingestion_batch_id", sa.Integer(), nullable=True))
    op.add_column("gps_pings", sa.Column("observation_id", sa.String(length=100), nullable=True))
    op.create_foreign_key(
        "fk_gps_pings_ingestion_batch_id",
        "gps_pings",
        "live_ingestion_batches",
        ["ingestion_batch_id"],
        ["id"],
    )
    op.create_index("ix_gps_pings_ingestion_batch_id", "gps_pings", ["ingestion_batch_id"])
    op.create_index("ix_gps_pings_segment_timestamp", "gps_pings", ["segment_id", "timestamp"])
    op.create_index("ix_gps_pings_region_timestamp", "gps_pings", ["region_id", "timestamp"])
    op.create_unique_constraint(
        "uq_gps_ping_batch_observation",
        "gps_pings",
        ["ingestion_batch_id", "observation_id"],
    )
    op.create_table(
        "segment_current_state",
        sa.Column("segment_id", sa.String(length=30), nullable=False),
        sa.Column("region_id", sa.String(length=20), nullable=False),
        sa.Column("latest_timestamp", sa.DateTime(), nullable=False),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_count", sa.Integer(), nullable=False),
        sa.Column("average_speed_kmph", sa.Float(), nullable=False),
        sa.Column("density", sa.Float(), nullable=False),
        sa.Column("current_event", sa.String(length=20), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["segment_id"], ["segments.segment_id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["live_ingestion_batches.id"]),
        sa.PrimaryKeyConstraint("segment_id"),
    )
    op.create_index("ix_segment_current_state_region_id", "segment_current_state", ["region_id"])
    op.create_index("ix_segment_current_state_latest_timestamp", "segment_current_state", ["latest_timestamp"])


def downgrade() -> None:
    op.drop_index("ix_segment_current_state_latest_timestamp", table_name="segment_current_state")
    op.drop_index("ix_segment_current_state_region_id", table_name="segment_current_state")
    op.drop_table("segment_current_state")
    op.drop_constraint("uq_gps_ping_batch_observation", "gps_pings", type_="unique")
    op.drop_index("ix_gps_pings_region_timestamp", table_name="gps_pings")
    op.drop_index("ix_gps_pings_segment_timestamp", table_name="gps_pings")
    op.drop_index("ix_gps_pings_ingestion_batch_id", table_name="gps_pings")
    op.drop_constraint("fk_gps_pings_ingestion_batch_id", "gps_pings", type_="foreignkey")
    op.drop_column("gps_pings", "observation_id")
    op.drop_column("gps_pings", "ingestion_batch_id")
    op.drop_index("ix_live_ingestion_batches_observed_at", table_name="live_ingestion_batches")
    op.drop_index("ix_live_ingestion_batches_source_id", table_name="live_ingestion_batches")
    op.drop_table("live_ingestion_batches")
