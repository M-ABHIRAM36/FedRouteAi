import type { PathOptions } from 'leaflet';
import type { LiveSegmentState } from '../../services/api/liveMapApi';

export type SegmentTrafficStatus = 'normal' | 'congestion' | 'construction' | 'accident' | 'flood' | 'diversion' | 'road_damage' | 'blocked' | 'unknown';

export interface SegmentStyle extends PathOptions {
  label: string;
  status: SegmentTrafficStatus;
}

const styles: Record<SegmentTrafficStatus, SegmentStyle> = {
  normal: { color: '#4ade80', weight: 4, opacity: 0.82, label: 'Normal', status: 'normal' },
  congestion: { color: '#f59e0b', weight: 6, opacity: 0.9, dashArray: '8 6', label: 'Congestion', status: 'congestion' },
  construction: { color: '#f97316', weight: 7, opacity: 0.92, dashArray: '10 5', label: 'Construction', status: 'construction' },
  accident: { color: '#ef4444', weight: 8, opacity: 0.95, dashArray: '2 7', label: 'Accident', status: 'accident' },
  flood: { color: '#38bdf8', weight: 7, opacity: 0.92, dashArray: '4 5', label: 'Flood', status: 'flood' },
  diversion: { color: '#c084fc', weight: 6, opacity: 0.9, dashArray: '12 6', label: 'Diversion', status: 'diversion' },
  road_damage: { color: '#eab308', weight: 7, opacity: 0.92, dashArray: '2 5', label: 'Road damage', status: 'road_damage' },
  blocked: { color: '#f43f5e', weight: 8, opacity: 0.95, dashArray: '3 10', label: 'Road blocked', status: 'blocked' },
  unknown: { color: '#94a3b8', weight: 3, opacity: 0.42, dashArray: '2 7', label: 'No live data', status: 'unknown' },
};

export const getSegmentStyle = (state?: LiveSegmentState): SegmentStyle => {
  if (!state) return styles.unknown;
  if (!state.available || state.current_event === 'road_block') return styles.blocked;
  return styles[state.current_event as SegmentTrafficStatus] ?? styles.unknown;
};

export const segmentLegend = Object.values(styles);
