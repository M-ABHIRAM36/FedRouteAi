import React from "react";

/** Simple live-feed list of active events — sidebar next to MapView. */
export default function EventFeed({ events = [] }) {
  if (events.length === 0) {
    return <p style={{ color: "#94a3b8" }}>No active events.</p>;
  }
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {events.map((e) => (
        <li
          key={e.event_id}
          style={{
            padding: "10px 12px",
            marginBottom: 8,
            borderRadius: 8,
            background: "#111a2e",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <div style={{ fontWeight: 600 }}>{e.event}</div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>
            {e.segment_id} · confidence {(e.confidence * 100).toFixed(0)}%
          </div>
        </li>
      ))}
    </ul>
  );
}
