import React from "react";
import { MapContainer, TileLayer, Polyline, Popup } from "react-leaflet";

/**
 * Renders road segments as colored polylines. Segments involved in an
 * active event are drawn in the event's color; everything else is
 * neutral gray. `segments` and `activeEvents` come from the parent
 * Dashboard page (see pages/Dashboard.jsx), which owns the data
 * fetching — this component only renders.
 */
const EVENT_COLOR = {
  congestion: "#ffb84d",
  road_block: "#ff4d4d",
  road_damage: "#c084fc",
  construction: "#facc15",
  flood: "#38bdf8",
  accident: "#ef4444",
  diversion: "#a78bfa",
};

export default function MapView({ segments = [], activeEvents = [], center = [17.385, 78.4867] }) {
  const eventBySegment = Object.fromEntries(activeEvents.map((e) => [e.segment_id, e]));

  return (
    <MapContainer center={center} zoom={14} style={{ height: "100%", width: "100%" }}>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; OpenStreetMap contributors'
      />
      {segments.map((seg) => {
        const event = eventBySegment[seg.segment_id];
        return (
          <Polyline
            key={seg.segment_id}
            positions={[
              [seg.start_lat, seg.start_lon],
              [seg.end_lat, seg.end_lon],
            ]}
            pathOptions={{
              color: event ? EVENT_COLOR[event.event] || "#ff0000" : "#64748b",
              weight: event ? 5 : 3,
            }}
          >
            <Popup>
              <strong>{seg.road_name}</strong> ({seg.segment_id})
              {event && (
                <div>
                  <em>{event.event}</em> — confidence {event.confidence}
                </div>
              )}
            </Popup>
          </Polyline>
        );
      })}
    </MapContainer>
  );
}
