import axios from "axios";

// Vite proxies /api -> the FastAPI backend (see vite.config.js) in dev;
// in prod, point this at wherever the backend is actually deployed.
const client = axios.create({ baseURL: "/api/v1" });

export const getSegments = (regionId) =>
  client.get("/segments", { params: regionId ? { region_id: regionId } : {} }).then((r) => r.data);

export const getActiveEvents = () => client.get("/events").then((r) => r.data);

export const computeRoute = (originSegmentId, destinationSegmentId) =>
  client
    .post("/routes", {
      origin_segment_id: originSegmentId,
      destination_segment_id: destinationSegmentId,
      avoid_active_events: true,
    })
    .then((r) => r.data);

export const getFederatedStatus = () => client.get("/federated/status").then((r) => r.data);

export default client;
