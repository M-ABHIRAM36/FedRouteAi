import type { PathOptions } from 'leaflet';
import type { LiveSegmentState } from '../../services/api/liveMapApi';

export type SegmentTrafficStatus = 'normal' | 'congestion' | 'construction' | 'accident' | 'flood' | 'diversion' | 'road_damage' | 'road_block' | 'blocked' | 'telemetry_clear' | 'telemetry_slow' | 'telemetry_dense' | 'unknown';

export interface SegmentStyle extends PathOptions {
  label: string;
  status: SegmentTrafficStatus;
}

export const segmentStyles: Record<SegmentTrafficStatus, SegmentStyle> = {
  normal: { color: '#4ade80', weight: 4, opacity: 0.82, label: 'Normal', status: 'normal' },
  congestion: { color: '#f59e0b', weight: 6, opacity: 0.9, dashArray: '8 6', label: 'Congestion', status: 'congestion' },
  construction: { color: '#f97316', weight: 7, opacity: 0.92, dashArray: '10 5', label: 'Construction', status: 'construction' },
  accident: { color: '#ef4444', weight: 8, opacity: 0.95, dashArray: '2 7', label: 'Accident', status: 'accident' },
  flood: { color: '#38bdf8', weight: 7, opacity: 0.92, dashArray: '4 5', label: 'Flood', status: 'flood' },
  diversion: { color: '#c084fc', weight: 6, opacity: 0.9, dashArray: '12 6', label: 'Diversion', status: 'diversion' },
  road_damage: { color: '#eab308', weight: 7, opacity: 0.92, dashArray: '2 5', label: 'Road damage', status: 'road_damage' },
  road_block: { color: '#f43f5e', weight: 8, opacity: 0.95, dashArray: '3 10', label: 'Road block', status: 'road_block' },
  blocked: { color: '#f43f5e', weight: 8, opacity: 0.95, dashArray: '3 10', label: 'Road blocked', status: 'blocked' },
  telemetry_clear: { color: '#84cc16', weight: 4, opacity: 0.78, label: 'Telemetry: flowing', status: 'telemetry_clear' },
  telemetry_slow: { color: '#fbbf24', weight: 5, opacity: 0.86, label: 'Telemetry: slow', status: 'telemetry_slow' },
  telemetry_dense: { color: '#fb7185', weight: 6, opacity: 0.88, dashArray: '7 5', label: 'Telemetry: dense', status: 'telemetry_dense' },
  unknown: { color: '#94a3b8', weight: 3, opacity: 0.42, dashArray: '2 7', label: 'No live data', status: 'unknown' },
};

export const getPredictionStyle = (state?: LiveSegmentState): SegmentStyle => {
  if (!state?.predicted_event) return segmentStyles.unknown;
  return segmentStyles[state.predicted_event as SegmentTrafficStatus] ?? segmentStyles.unknown;
};

export const getTelemetryStyle = (state?: LiveSegmentState, maxSpeedKmph?: number): SegmentStyle => {
  if (!state) return segmentStyles.unknown;
  if (!state.available) return segmentStyles.blocked;
  if ((state.occupancy != null && state.occupancy >= 0.75) || state.density >= 20) return segmentStyles.telemetry_dense;
  if (maxSpeedKmph && state.average_speed_kmph / maxSpeedKmph <= 0.45) return segmentStyles.telemetry_slow;
  return segmentStyles.telemetry_clear;
};

export const getSegmentStyle = (state?: LiveSegmentState, maxSpeedKmph?: number): SegmentStyle =>
  state?.predicted_event ? getPredictionStyle(state) : getTelemetryStyle(state, maxSpeedKmph);

export const predictionLegend = ['normal', 'congestion', 'construction', 'accident', 'flood', 'diversion', 'road_damage', 'road_block'].map(
  (status) => segmentStyles[status as SegmentTrafficStatus],
);
export const telemetryLegend = ['telemetry_clear', 'telemetry_slow', 'telemetry_dense'].map(
  (status) => segmentStyles[status as SegmentTrafficStatus],
);
