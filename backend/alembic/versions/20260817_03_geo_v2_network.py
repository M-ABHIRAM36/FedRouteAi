"""Add canonical OSM geometry, transitions, scenarios, and predictions."""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


revision = "20260817_03"
down_revision = "20260817_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.add_column("live_ingestion_batches", sa.Column("network_source", sa.String(40), nullable=True))
    op.add_column("live_ingestion_batches", sa.Column("network_version", sa.String(80), nullable=True))
    op.create_table(
        "geo_segment_metadata",
        sa.Column("segment_id", sa.String(30), sa.ForeignKey("segments.segment_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("network_source", sa.String(40), nullable=False),
        sa.Column("network_version", sa.String(80), nullable=False),
        sa.Column("osm_way_id", sa.BigInteger(), nullable=False),
        sa.Column("start_node_id", sa.BigInteger(), nullable=False),
        sa.Column("end_node_id", sa.BigInteger(), nullable=False),
        sa.Column("highway", sa.String(40), nullable=False),
        sa.Column("geometry", Geometry("LINESTRING", srid=4326, spatial_index=False), nullable=False),
        sa.Column("bridge", sa.Boolean(), nullable=False),
        sa.Column("tunnel", sa.Boolean(), nullable=False),
        sa.Column("junction", sa.String(40), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("network_version", "osm_way_id", "start_node_id", "end_node_id", name="uq_geo_osm_edge"),
    )
    op.create_index("ix_geo_segment_metadata_network_source", "geo_segment_metadata", ["network_source"])
    op.create_index("ix_geo_segment_metadata_network_version", "geo_segment_metadata", ["network_version"])
    op.create_index("ix_geo_segment_metadata_geometry", "geo_segment_metadata", ["geometry"], postgresql_using="gist")
    op.create_table(
        "geo_segment_transitions",
        sa.Column("from_segment_id", sa.String(30), sa.ForeignKey("segments.segment_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("to_segment_id", sa.String(30), sa.ForeignKey("segments.segment_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("via_node_id", sa.BigInteger(), primary_key=True),
        sa.Column("network_version", sa.String(80), nullable=False),
    )
    op.create_index("ix_geo_segment_transitions_network_version", "geo_segment_transitions", ["network_version"])
    op.create_table(
        "live_scenarios",
        sa.Column("event_id", sa.String(20), primary_key=True),
        sa.Column("source_id", sa.String(60), nullable=False), sa.Column("run_id", sa.String(80), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("primary_segment_id", sa.String(30), sa.ForeignKey("segments.segment_id"), nullable=False),
        sa.Column("region_id", sa.String(20), nullable=False), sa.Column("affected_segment_ids", sa.JSON(), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False), sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False), sa.Column("ground_truth_label", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_live_scenarios_source_id", "live_scenarios", ["source_id"])
    op.create_index("ix_live_scenarios_run_id", "live_scenarios", ["run_id"])
    op.create_index("ix_live_scenarios_run_time", "live_scenarios", ["run_id", "start_time", "end_time"])
    op.create_table(
        "segment_predictions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(60), nullable=False), sa.Column("run_id", sa.String(80), nullable=False),
        sa.Column("segment_id", sa.String(30), sa.ForeignKey("segments.segment_id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False), sa.Column("predicted_label", sa.String(40), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True), sa.Column("class_probabilities", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False), sa.Column("historical_baseline", sa.JSON(), nullable=False),
        sa.Column("current_deviation", sa.JSON(), nullable=False),
        sa.UniqueConstraint("source_id", "run_id", "segment_id", "timestamp", "model_version", name="uq_segment_prediction"),
    )
    op.create_index("ix_segment_predictions_segment_timestamp", "segment_predictions", ["segment_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("segment_predictions")
    op.drop_table("live_scenarios")
    op.drop_table("geo_segment_transitions")
    op.drop_index("ix_geo_segment_metadata_geometry", table_name="geo_segment_metadata")
    op.drop_table("geo_segment_metadata")
    op.drop_column("live_ingestion_batches", "network_version")
    op.drop_column("live_ingestion_batches", "network_source")
