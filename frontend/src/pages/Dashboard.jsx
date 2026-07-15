import React, { useEffect, useState } from "react";
import MapView from "../components/MapView.jsx";
import EventFeed from "../components/EventFeed.jsx";
import { getSegments, getActiveEvents } from "../api/client.js";

export default function Dashboard() {
  const [segments, setSegments] = useState([]);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    // TODO: poll on an interval (or move to a websocket) once the
    // backend can push live event updates instead of just serving
    // point-in-time snapshots
    Promise.all([getSegments(), getActiveEvents()])
      .then(([segs, evs]) => {
        setSegments(segs);
        setEvents(evs);
      })
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div style={{ display: "flex", height: "100vh", background: "#080c16", color: "#f1f4fb" }}>
      <div style={{ flex: 1 }}>
        <MapView segments={segments} activeEvents={events} />
      </div>
      <div style={{ width: 320, padding: 16, overflowY: "auto" }}>
        <h2>Active Events</h2>
        {error && <p style={{ color: "#ff6f59" }}>Failed to load: {error}</p>}
        <EventFeed events={events} />
      </div>
    </div>
  );
}
