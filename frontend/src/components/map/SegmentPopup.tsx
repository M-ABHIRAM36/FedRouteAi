import React from 'react';
import { Activity, AlertTriangle, CheckCircle2, CircleHelp, Network, Radio, TrendingDown, TrendingUp } from 'lucide-react';
import type { LiveEvent, LiveSegmentState, SegmentData } from '../../services/api/liveMapApi';
import { segmentStyles, type SegmentTrafficStatus } from './segmentStyles';

interface SegmentPopupProps {
  segment: SegmentData;
  state?: LiveSegmentState;
  event?: LiveEvent;
  compact?: boolean;
}

const displayName = (value: string) => value.replaceAll('_', ' ');
const percentage = (value: number) => `${(value * 100).toFixed(1)}%`;
const numeric = (value: unknown): number | undefined => typeof value === 'number' && Number.isFinite(value) ? value : undefined;
const traceEntries = (state?: LiveSegmentState) => Object.entries({ ...(state?.historical_baseline ?? {}), ...(state?.current_deviation ?? {}) });

export const SegmentPopup: React.FC<SegmentPopupProps> = ({ segment, state, event, compact = false }) => {
  const prediction = state?.predicted_event;
  const style = prediction ? segmentStyles[prediction as SegmentTrafficStatus] : segmentStyles.unknown;
  const speedRatio = numeric(state?.current_deviation?.speed_to_baseline);
  const speedTrend = numeric(state?.current_deviation?.speed_trend);
  const neighborDelta = numeric(state?.current_deviation?.neighbor_speed_delta);
  const features = traceEntries(state);
  const StatusIcon = !prediction ? CircleHelp : prediction === 'normal' ? CheckCircle2 : AlertTriangle;

  return <div className={compact ? 'w-64 text-textPrimary' : 'text-textPrimary'}>
    <div className="border-b border-border pb-3">
      <div className="text-[10px] font-semibold uppercase text-textSecondary">{segment.segment_id}</div>
      <div className="mt-0.5 text-base font-semibold text-white">{segment.road_name || 'Unnamed OSM road'}</div>
      <div className="mt-1 flex flex-wrap gap-2 text-xs text-textSecondary"><span>{segment.region_id}</span><span>·</span><span>{segment.road_type}</span>{segment.osm_way_id != null && <><span>·</span><span>OSM {segment.osm_way_id}</span></>}</div>
    </div>

    <section className="border-b border-border py-3">
      <SectionLabel icon={<Activity className="h-3.5 w-3.5" />}>Model prediction</SectionLabel>
      {prediction ? <div className="mt-2 flex items-center justify-between gap-3"><div className="flex items-center gap-2 text-sm font-semibold uppercase" style={{ color: style.color }}><StatusIcon className="h-4 w-4" />{displayName(prediction)}</div>{state?.prediction_confidence != null && <div className="text-right"><div className="text-lg font-semibold text-white">{percentage(state.prediction_confidence)}</div><div className="text-[10px] text-textSecondary">Model score</div></div>}</div> : <div className="mt-2 flex items-center gap-2 text-sm text-textSecondary"><CircleHelp className="h-4 w-4" />No prediction available</div>}
      {state?.prediction_model_version && <div className="mt-2 truncate text-[10px] text-textSecondary" title={state.prediction_model_version}>{formatModelVersion(state.prediction_model_version)}</div>}
    </section>

    <section className="grid grid-cols-2 gap-x-4 gap-y-3 border-b border-border py-3">
      <Measure label="Average speed" value={state ? `${state.average_speed_kmph.toFixed(1)} km/h` : 'No data'} />
      <Measure label="Vehicles" value={state ? String(state.vehicle_count) : 'No data'} />
      <Measure label="Density" value={state ? state.density.toFixed(1) : 'No data'} />
      <Measure label="Availability" value={state ? state.available ? 'Available' : 'Unavailable' : 'No data'} />
    </section>

    {!compact && <section className="border-b border-border py-3">
      <SectionLabel icon={<Network className="h-3.5 w-3.5" />}>Model context</SectionLabel>
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3 xl:grid-cols-1">
        <ContextValue label="Speed vs baseline" value={speedRatio == null ? 'Unavailable' : `${speedRatio >= 1 ? '+' : ''}${((speedRatio - 1) * 100).toFixed(0)}%`} />
        <ContextValue label="Historical trend" value={speedTrend == null ? 'Unavailable' : `${speedTrend >= 0 ? 'Rising' : 'Declining'} ${Math.abs(speedTrend).toFixed(1)} km/h`} icon={speedTrend == null ? undefined : speedTrend >= 0 ? <TrendingUp className="h-3.5 w-3.5 text-success" /> : <TrendingDown className="h-3.5 w-3.5 text-warning" />} />
        <ContextValue label="Neighbor effect" value={neighborDelta == null ? 'Unavailable' : `${neighborDelta > 0 ? '+' : ''}${neighborDelta.toFixed(1)} km/h`} />
      </div>
    </section>}

    {event && <section className="border-b border-warning/30 bg-warning/5 px-3 py-3 -mx-3"><SectionLabel icon={<AlertTriangle className="h-3.5 w-3.5 text-warning" />}>Scenario ground truth</SectionLabel><div className="mt-1 text-sm font-semibold uppercase text-warning">{displayName(event.event_type)}</div><div className="mt-1 text-[10px] text-textSecondary">Demo metadata only. It is not part of model input.</div></section>}

    {!compact && features.length > 0 && <details className="border-b border-border py-3"><summary className="cursor-pointer text-[11px] font-semibold uppercase text-textSecondary focus-visible:outline-2 focus-visible:outline-primary">Feature trace <span className="font-normal normal-case">({features.length} recorded values)</span></summary><div className="mt-3 max-h-48 space-y-1 overflow-y-auto font-mono text-[10px]">{features.map(([key, value]) => <div key={key} className="flex justify-between gap-3"><span className="text-textSecondary">{displayName(key)}</span><span className="text-right text-textPrimary">{typeof value === 'number' ? value.toFixed(3) : String(value)}</span></div>)}</div></details>}

    <div className="pt-3 text-[10px] text-textSecondary"><div className="flex items-center gap-1.5"><Radio className="h-3 w-3" />{state ? `Telemetry ${new Date(state.latest_timestamp).toLocaleTimeString()}` : 'No live telemetry'}</div>{segment.network_version && <div className="mt-1">{segment.network_source} · {segment.network_version}</div>}</div>
  </div>;
};

const formatModelVersion = (version: string) => {
  const round = version.match(/-r(\d+)$/)?.[1];
  return round ? `Geo V2 federated · round ${Number(round)}` : version;
};

const SectionLabel = ({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) => <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase text-textSecondary">{icon}{children}</div>;
const Measure = ({ label, value }: { label: string; value: string }) => <div><div className="text-[10px] uppercase text-textSecondary">{label}</div><div className="mt-0.5 text-sm font-medium text-textPrimary">{value}</div></div>;
const ContextValue = ({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) => <div className="border-l-2 border-border pl-2"><div className="text-[10px] text-textSecondary">{label}</div><div className="mt-0.5 flex items-center gap-1 text-xs font-medium text-textPrimary">{icon}{value}</div></div>;
