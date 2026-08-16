import React from 'react';
import { AlertTriangle, CircleCheck, CircleHelp } from 'lucide-react';
import type { SegmentData } from '../../services/api/liveMapApi';
import type { LiveSegmentState } from '../../services/api/liveMapApi';

interface SegmentPopupProps {
  segment: SegmentData;
  state?: LiveSegmentState;
}

export const SegmentPopup: React.FC<SegmentPopupProps> = ({ segment, state }) => {
  const status = state ? state.current_event === 'normal' ? 'Normal' : state.current_event : 'No live data';
  const StatusIcon = !state ? CircleHelp : status === 'Normal' ? CircleCheck : AlertTriangle;
  return (
    <div className="w-56 text-textPrimary">
      <div className="mb-2 border-b border-border pb-2">
        <div className="font-semibold text-white">{segment.segment_id}</div>
        <div className="text-xs text-textSecondary">{segment.road_name} · {segment.region_id}</div>
      </div>
      <div className="space-y-1 text-sm">
        <Row label="Traffic status" value={status} icon={<StatusIcon className="h-3.5 w-3.5" />} />
        <Row label="Average speed" value={state ? `${state.average_speed_kmph.toFixed(1)} km/h` : 'Unknown'} />
        <Row label="Density" value={state ? state.density.toFixed(1) : 'Unknown'} />
        <Row label="Vehicles" value={state ? String(state.vehicle_count) : 'Unknown'} />
        <Row label="Availability" value={state ? state.available ? 'Available' : 'Blocked' : 'Unknown'} />
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
