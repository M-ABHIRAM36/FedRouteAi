import React from "react";

/** TODO: wire this up to GET /segments/{id} + /segments/{id}/neighbors
 * once a segment is clicked on the map — currently a placeholder panel. */
export default function SegmentDetail({ segment }) {
  if (!segment) return <p style={{ color: "#94a3b8" }}>Select a segment on the map.</p>;
  return (
    <div>
      <h3>{segment.road_name}</h3>
      <p>{segment.segment_id}</p>
      {/* TODO: historical memory chart, neighbor list, event history */}
    </div>
  );
}
