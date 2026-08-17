import React from 'react';
import { AlertTriangle, CircleCheck, CircleHelp } from 'lucide-react';
import type { LiveEvent, LiveSegmentState, SegmentData } from '../../services/api/liveMapApi';

interface SegmentPopupProps {
  segment: SegmentData;
  state?: LiveSegmentState;
  event?: LiveEvent;
}

const displayName = (value: string) => value.replaceAll('_', ' ');
const percentage = (value: number) => `${(value * 100).toFixed(1)}%`;
const objectValue = (value: Record<string, unknown>) => Object.entries(value).map(([key, item]) => `${displayName(key)}: ${typeof item === 'number' ? item.toFixed(2) : String(item)}`).join(', ');

export const SegmentPopup: React.FC<SegmentPopupProps> = ({ segment, state, event }) => {
  const prediction = state?.predicted_event ? displayName(state.predicted_event) : undefined;
  const StatusIcon = !state ? CircleHelp : prediction === 'normal' ? CircleCheck : prediction ? AlertTriangle : CircleHelp;
  return (
    <div className="w-64 text-textPrimary">
      <div className="mb-2 border-b border-border pb-2">
        <div className="font-semibold text-white">{segment.road_name}</div>
        <div className="text-xs text-textSecondary">{segment.segment_id} · {segment.region_id}</div>
      </div>
      <div className="space-y-1 text-sm">
        <Row label="Model prediction" value={prediction ?? 'No prediction'} icon={<StatusIcon className="h-3.5 w-3.5" />} />
        {state?.prediction_confidence != null && <Row label="Confidence" value={percentage(state.prediction_confidence)} />}
        {state?.prediction_model_version && <Row label="Model" value={state.prediction_model_version} />}
        <Row label="Average speed" value={state ? `${state.average_speed_kmph.toFixed(1)} km/h` : 'Unknown'} />
        <Row label="Density" value={state ? state.density.toFixed(1) : 'Unknown'} />
        {state?.occupancy != null && <Row label="Occupancy" value={percentage(state.occupancy)} />}
        <Row label="Vehicles" value={state ? String(state.vehicle_count) : 'Unknown'} />
        <Row label="Availability" value={state ? state.available ? 'Available' : 'Blocked' : 'Unknown'} />
        {segment.network_source && <Row label="Network source" value={segment.network_source} />}
        {segment.network_version && <Row label="Network version" value={segment.network_version} />}
        {segment.osm_way_id != null && <Row label="OSM way" value={String(segment.osm_way_id)} />}
        {state?.historical_baseline && <Row label="Baseline" value={objectValue(state.historical_baseline)} />}
        {state?.current_deviation && <Row label="Deviation" value={objectValue(state.current_deviation)} />}
        {event && <Row label="Scenario event" value={displayName(event.event_type)} />}
        {event?.source && <Row label="Event source" value={displayName(event.source)} />}
        {event?.severity != null && <Row label="Severity" value={percentage(event.severity)} />}
        <Row label="Last updated" value={state ? new Date(state.latest_timestamp).toLocaleTimeString() : 'Unknown'} />
      </div>
    </div>
  );
};

const Row = ({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) => (
  <div className="flex items-center justify-between gap-3">
    <span className="text-textSecondary">{label}</span>
    <span className="flex items-center gap-1 text-right font-medium text-textPrimary">{icon}{value}</span>
  </div>
);
