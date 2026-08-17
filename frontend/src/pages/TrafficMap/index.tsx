import { useEffect, useMemo, useRef, useState } from 'react';
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import type { LatLngBoundsExpression, Map as LeafletMap } from 'leaflet';
import { Activity, Car, ChevronDown, Clock3, Eye, EyeOff, Layers3, LocateFixed, Pause, Play, Radio, RotateCcw, TriangleAlert, Wifi, WifiOff, X } from 'lucide-react';
import 'leaflet/dist/leaflet.css';
import { useQuery } from '@tanstack/react-query';
import { PageContainer } from '../../components/common/PageContainer';
import { fetchLiveSnapshot, fetchSegments, type LiveEvent, type LiveMapSnapshot, type LiveVehicle } from '../../services/api/liveMapApi';
import { MapLegend } from '../../components/map/MapLegend';
import { SegmentPopup } from '../../components/map/SegmentPopup';
import { getPredictionStyle, getTelemetryStyle, segmentStyles } from '../../components/map/segmentStyles';
import { getSegmentMidpoint, getSegmentPositions } from '../../components/map/segmentGeometry';
import { AnimatedVehicleLayer } from '../../components/map/AnimatedVehicleLayer';
import { vehicleTone } from '../../components/map/vehicleAnimation';
import { connectionStatus, snapshotAgeSeconds, type ConnectionStatus } from './trafficMapState';

type LayerState = { predictions: boolean; telemetry: boolean; vehicles: boolean; events: boolean; network: boolean };
type TimelineEntry = { tick: number; observedAt: string; prediction?: string; speed?: number };

const statusColors: Record<ConnectionStatus, string> = {
  CONNECTING: 'text-primary border-primary/30 bg-primary/10', LIVE: 'text-success border-success/30 bg-success/10',
  DELAYED: 'text-warning border-warning/30 bg-warning/10', STALE: 'text-warning border-warning/30 bg-warning/10',
  PAUSED: 'text-textSecondary border-border bg-surfaceHover', OFFLINE: 'text-danger border-danger/30 bg-danger/10',
};

const FitNetwork = ({ bounds, resetKey }: { bounds: LatLngBoundsExpression; resetKey: number }) => { const map = useMap(); useEffect(() => { map.fitBounds(bounds, { padding: [24, 24], maxZoom: 14 }); }, [bounds, map, resetKey]); return null; };
const ViewportTracker = ({ onChange }: { onChange: (map: LeafletMap) => void }) => { useMapEvents({ moveend: (event) => onChange(event.target), zoomend: (event) => onChange(event.target) }); return null; };

const TrafficMap = () => {
  const [liveMode, setLiveMode] = useState(false);
  const [layers, setLayers] = useState<LayerState>({ predictions: true, telemetry: false, vehicles: true, events: true, network: false });
  const [region, setRegion] = useState('all');
  const [selectedSegmentId, setSelectedSegmentId] = useState<string>();
  const [selectedVehicleId, setSelectedVehicleId] = useState<string>();
  const [fitKey, setFitKey] = useState(0);
  const [visibleVehicleCount, setVisibleVehicleCount] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [liveSession, setLiveSession] = useState(0);
  const [lastSnapshot, setLastSnapshot] = useState<LiveMapSnapshot>();
  const viewportRef = useRef<LeafletMap | undefined>(undefined);

  const liveQuery = useQuery({
    queryKey: ['live-map', 'snapshot', liveSession],
    queryFn: async () => ({ snapshot: await fetchLiveSnapshot(), clientReceivedAt: Date.now() }),
    enabled: liveMode,
    refetchInterval: liveMode ? (query) => (query.state.data?.snapshot.poll_interval_seconds ?? 4) * 1000 : false,
    retry: false, refetchOnWindowFocus: false,
  });
  const currentReceipt = liveQuery.data?.clientReceivedAt;
  const snapshot = liveQuery.data?.snapshot ?? lastSnapshot;
  const networkSource = snapshot?.network_source;
  const staticQuery = useQuery({
    queryKey: ['live-map', 'segments', networkSource ?? 'default'], queryFn: () => fetchSegments(networkSource),
    staleTime: Infinity, retry: 1, placeholderData: (previous) => previous,
  });
  const segments = useMemo(() => staticQuery.data ?? [], [staticQuery.data]);
  const states = useMemo(() => new Map((snapshot?.segments ?? []).map((state) => [state.segment_id, state])), [snapshot]);
  const events = snapshot?.events;
  const eventBySegment = useMemo(() => indexEvents(events ?? []), [events]);
  const regions = useMemo(() => [...new Set(segments.map((segment) => segment.region_id))].sort(), [segments]);
  const filteredSegments = useMemo(() => segments.filter((segment) => region === 'all' || segment.region_id === region), [segments, region]);
  const filteredVehicles = useMemo(() => (snapshot?.vehicles ?? []).filter((vehicle) => region === 'all' || vehicle.region_id === region), [snapshot, region]);
  const selectedSegment = segments.find((segment) => segment.segment_id === selectedSegmentId);
  const selectedState = selectedSegmentId ? states.get(selectedSegmentId) : undefined;
  const selectedVehicle = filteredVehicles.find((vehicle) => vehicle.vehicle_id === selectedVehicleId);
  const selectedEvent = selectedSegmentId ? eventBySegment.get(selectedSegmentId) : undefined;
  const bounds = useMemo<LatLngBoundsExpression | undefined>(() => segments.length ? segments.flatMap((segment) => getSegmentPositions(segment)) : undefined, [segments]);
  const status = connectionStatus(liveMode, currentReceipt, liveQuery.isError, now);
  const age = snapshotAgeSeconds(currentReceipt, now);
  const predictedEvents = useMemo(() => (snapshot?.segments ?? []).filter((state) => state.predicted_event && state.predicted_event !== 'normal').length, [snapshot]);
  const predictionCounts = useMemo(() => countPredictions(snapshot), [snapshot]);

  useEffect(() => {
    if (!liveMode) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [liveMode]);
  useEffect(() => {
    if (liveQuery.data?.snapshot) setLastSnapshot(liveQuery.data.snapshot);
  }, [liveQuery.data]);
  useEffect(() => {
    if (!snapshot || !selectedSegmentId) return;
    const state = states.get(selectedSegmentId);
    setTimeline((entries) => {
      if (entries.at(-1)?.tick === snapshot.tick_number) return entries;
      return [...entries, { tick: snapshot.tick_number, observedAt: snapshot.observed_at, prediction: state?.predicted_event ?? undefined, speed: state?.average_speed_kmph }].slice(-6);
    });
  }, [selectedSegmentId, snapshot, states]);
  useEffect(() => { setTimeline([]); }, [selectedSegmentId]);
  useEffect(() => {
    if (!layers.vehicles || !snapshot) return setVisibleVehicleCount(0);
    if (viewportRef.current) setVisibleVehicleCount(filteredVehicles.filter((vehicle) => viewportRef.current!.getBounds().contains([vehicle.lat, vehicle.lon])).length);
    else setVisibleVehicleCount(filteredVehicles.length);
  }, [filteredVehicles, layers.vehicles, snapshot]);

  const handleViewport = (map: LeafletMap) => { viewportRef.current = map; if (layers.vehicles) setVisibleVehicleCount(filteredVehicles.filter((vehicle) => map.getBounds().contains([vehicle.lat, vehicle.lon])).length); };
  const focusSegment = (segmentId: string) => { setSelectedSegmentId(segmentId); setSelectedVehicleId(undefined); };
  const focusVehicle = (vehicleId: string) => { setSelectedVehicleId(vehicleId); setSelectedSegmentId(undefined); };
  const toggleLive = () => {
    if (liveMode) setLiveMode(false);
    else { setNow(Date.now()); setLiveSession((session) => session + 1); setLiveMode(true); }
  };

  if (staticQuery.isLoading) return <MapLoading label="Loading Geo V2 network..." />;
  if (staticQuery.isError) return <MapLoading label="Road network unavailable. Start the backend and reload." error />;
  if (!bounds) return <MapLoading label="Network loaded. Waiting for road geometry..." />;

  return <PageContainer className="max-w-[1800px] space-y-3">
    <header className="flex flex-col gap-3 border-b border-border pb-3 lg:flex-row lg:items-end lg:justify-between">
      <div><div className="mb-1 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-primary"><Activity className="h-3.5 w-3.5" />Geo V2 traffic intelligence</div><h1 className="text-2xl font-semibold text-white">Live operations map</h1><p className="mt-1 text-xs text-textSecondary"><span>{networkSource ?? 'Canonical network'} · {segments.length.toLocaleString()} segments</span>{snapshot?.network_version && <span className="ml-2 text-textSecondary/70">{snapshot.network_version}</span>}</p></div>
      <div className="flex flex-wrap items-center gap-2"><ModelStatus snapshot={snapshot} /><LiveStatus status={status} age={age} hasError={liveQuery.isError} /><button type="button" onClick={toggleLive} className={`flex h-9 items-center gap-2 px-3 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-primary ${liveMode ? 'border border-danger/40 bg-danger/10 text-danger' : 'bg-primary text-white hover:bg-primaryHover'}`}>{liveMode ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}{liveMode ? 'Pause live' : 'Start live'}</button></div>
    </header>

    <MetricBar snapshot={snapshot} predictedEvents={predictedEvents} status={status} age={age} />
    {liveQuery.isError && <div role="alert" className="border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{liveQuery.error instanceof Error ? liveQuery.error.message : 'Live telemetry is unavailable.'}</div>}

    <div className="grid min-h-[620px] gap-3 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="relative min-h-[520px] overflow-hidden border border-border bg-[#101820] xl:min-h-[620px]">
        <MapContainer bounds={bounds} className="h-full min-h-[520px] w-full xl:min-h-[620px]" zoomControl preferCanvas>
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" errorTileUrl="" />
          <FitNetwork bounds={bounds} resetKey={fitKey} /><ViewportTracker onChange={handleViewport} />
          <MapControls layers={layers} setLayers={setLayers} regions={regions} region={region} setRegion={setRegion} onFit={() => setFitKey((key) => key + 1)} />
          {layers.network && filteredSegments.map((segment) => <Polyline key={`network-${segment.segment_id}`} positions={getSegmentPositions(segment)} pathOptions={{ color: '#64748b', weight: 1.5, opacity: 0.3 }} />)}
          {layers.telemetry && filteredSegments.map((segment) => { const state = states.get(segment.segment_id); return <Polyline key={`telemetry-${segment.segment_id}`} positions={getSegmentPositions(segment)} pathOptions={{ ...getTelemetryStyle(state, segment.max_speed_kmph), weight: 8, opacity: 0.22 }} eventHandlers={{ click: () => focusSegment(segment.segment_id), mouseover: (event) => event.target.setStyle({ opacity: 0.45 }), mouseout: (event) => event.target.setStyle({ opacity: 0.22 }) }} />; })}
          {layers.predictions && filteredSegments.map((segment) => { const state = states.get(segment.segment_id); const selected = selectedSegmentId === segment.segment_id; const style = getPredictionStyle(state); return <Polyline key={`prediction-${segment.segment_id}`} positions={getSegmentPositions(segment)} pathOptions={{ ...style, weight: selected ? Number(style.weight ?? 4) + 3 : style.weight, opacity: selected ? 1 : style.opacity }} eventHandlers={{ click: () => focusSegment(segment.segment_id), mouseover: (event) => event.target.setStyle({ weight: Number(style.weight ?? 4) + 2, opacity: 1 }), mouseout: (event) => event.target.setStyle({ weight: selected ? Number(style.weight ?? 4) + 3 : style.weight, opacity: selected ? 1 : style.opacity }) }}><Popup><SegmentPopup compact segment={segment} state={state} event={eventBySegment.get(segment.segment_id)} /></Popup></Polyline>; })}
          {layers.vehicles && <AnimatedVehicleLayer vehicles={filteredVehicles} selectedVehicleId={selectedVehicleId} paused={status === 'STALE' || status === 'PAUSED' || status === 'OFFLINE'} onSelect={focusVehicle} />}
          {layers.events && (events ?? []).filter((event) => region === 'all' || event.region_id === region).map((event) => { const segment = segments.find((item) => item.segment_id === event.segment_id); return segment ? <CircleMarker key={`event-${event.event_id}`} center={getSegmentMidpoint(segment)} radius={8} pathOptions={{ color: '#fff', fillColor: '#f59e0b', fillOpacity: 0.8, weight: 2 }} eventHandlers={{ click: () => focusSegment(event.segment_id) }} /> : null; })}
        </MapContainer>
        <div className="absolute bottom-3 left-3 z-[500]"><MapLegend /></div>
        {layers.vehicles && snapshot && <div className="absolute bottom-3 right-3 z-[500] border border-border bg-surface/95 px-3 py-2 text-[10px] text-textSecondary shadow-lg">Vehicles in view <span className="font-semibold text-white">{visibleVehicleCount}</span> / {filteredVehicles.length}</div>}
        {!snapshot && <div className="pointer-events-none absolute inset-x-0 top-16 z-[450] mx-auto w-fit border border-border bg-surface/95 px-4 py-2 text-xs text-textSecondary">Network loaded · waiting for live telemetry</div>}
      </div>

      <InspectionPanel selectedSegment={selectedSegment} selectedState={selectedState} selectedEvent={selectedEvent} selectedVehicle={selectedVehicle} timeline={timeline} predictionCounts={predictionCounts} snapshot={snapshot} onClose={() => { setSelectedSegmentId(undefined); setSelectedVehicleId(undefined); }} />
    </div>
  </PageContainer>;
};

const indexEvents = (events: LiveEvent[]) => { const result = new Map<string, LiveEvent>(); for (const event of events) { result.set(event.segment_id, event); for (const segmentId of event.affected_segment_ids ?? []) result.set(segmentId, event); } return result; };
const countPredictions = (snapshot?: LiveMapSnapshot) => Object.entries((snapshot?.segments ?? []).reduce<Record<string, number>>((counts, state) => { const key = state.predicted_event ?? 'no_prediction'; counts[key] = (counts[key] ?? 0) + 1; return counts; }, {})).sort((a, b) => b[1] - a[1]);

const ModelStatus = ({ snapshot }: { snapshot?: LiveMapSnapshot }) => { const modelVersion = snapshot?.segments.find((state) => state.prediction_model_version)?.prediction_model_version; return <div className="border border-border bg-surface px-3 py-1.5"><div className="text-[9px] font-semibold uppercase text-textSecondary">Model</div><div className="text-xs font-medium text-textPrimary">{modelVersion ? 'Geo V2 · round 45' : 'Awaiting predictions'}</div></div>; };
const receiptLabel = (age: number) => age < 2 ? 'Received just now' : `Received ${Math.floor(age)}s ago`;
const LiveStatus = ({ status, age, hasError }: { status: ConnectionStatus; age: number; hasError: boolean }) => <div className={`flex h-9 items-center gap-2 border px-3 ${statusColors[status]}`}><span className={`h-2 w-2 rounded-full ${status === 'LIVE' ? 'animate-pulse bg-success' : 'bg-current'}`} /><div><div className="text-[10px] font-semibold">{status}</div><div className="text-[9px] opacity-80">{status === 'STALE' && hasError ? 'Backend connection unavailable' : Number.isFinite(age) ? receiptLabel(age) : 'No snapshot this session'}</div></div></div>;

const MetricBar = ({ snapshot, predictedEvents, status, age }: { snapshot?: LiveMapSnapshot; predictedEvents: number; status: ConnectionStatus; age: number }) => <section className="grid grid-cols-2 border border-border bg-surface sm:grid-cols-3 xl:grid-cols-6"><Metric icon={<Car />} label="Vehicles" value={snapshot ? snapshot.summary.vehicle_count.toLocaleString() : '—'} detail="authoritative GPS" /><Metric icon={<Layers3 />} label="Active segments" value={snapshot ? snapshot.summary.active_segments.toLocaleString() : '—'} detail="observed now" /><Metric icon={<TriangleAlert />} label="Predicted events" value={snapshot ? predictedEvents.toLocaleString() : '—'} detail="non-normal model output" /><Metric icon={<Radio />} label="Average speed" value={snapshot ? `${snapshot.summary.average_speed_kmph.toFixed(1)}` : '—'} detail="km/h" /><Metric icon={<Clock3 />} label="Last telemetry" value={snapshot ? new Date(snapshot.observed_at).toLocaleTimeString() : '—'} detail={snapshot ? `tick ${snapshot.tick_number}` : 'waiting'} /><Metric icon={status === 'LIVE' ? <Wifi /> : <WifiOff />} label="Data freshness" value={status} detail={Number.isFinite(age) ? receiptLabel(age) : 'not connected'} /></section>;
const Metric = ({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail: string }) => <div className="flex min-h-20 items-center gap-3 border-b border-r border-border px-3 py-3 last:border-r-0 sm:border-b-0"><span className="text-primary [&>svg]:h-4 [&>svg]:w-4">{icon}</span><div className="min-w-0"><div className="text-[9px] font-semibold uppercase tracking-wider text-textSecondary">{label}</div><div className="truncate text-lg font-semibold text-white">{value}</div><div className="truncate text-[9px] text-textSecondary">{detail}</div></div></div>;

const MapControls = ({ layers, setLayers, regions, region, setRegion, onFit }: { layers: LayerState; setLayers: React.Dispatch<React.SetStateAction<LayerState>>; regions: string[]; region: string; setRegion: (value: string) => void; onFit: () => void }) => <div className="pointer-events-none absolute left-3 right-3 top-3 z-[500] flex flex-wrap items-start justify-between gap-2"><div className="pointer-events-auto flex border border-border bg-surface/95 p-1 shadow-lg"><ControlButton label="Fit network" onClick={onFit}><LocateFixed /></ControlButton><ControlButton label="Reset view" onClick={onFit}><RotateCcw /></ControlButton></div><div className="pointer-events-auto flex flex-wrap justify-end gap-2"><div className="border border-border bg-surface/95 p-1 shadow-lg"><div className="px-2 py-1 text-[9px] font-semibold uppercase text-textSecondary">Map layers</div><div className="flex flex-wrap">{([['predictions', 'Predictions'], ['telemetry', 'Telemetry'], ['vehicles', 'Vehicles'], ['events', 'Events'], ['network', 'Network']] as const).map(([key, label]) => <button type="button" key={key} aria-pressed={layers[key]} onClick={() => setLayers((current) => ({ ...current, [key]: !current[key] }))} className={`flex h-7 items-center gap-1.5 px-2 text-[10px] focus-visible:outline-2 focus-visible:outline-primary ${layers[key] ? 'bg-primary/15 text-primary' : 'text-textSecondary hover:bg-surfaceHover'}`}>{layers[key] ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}{label}</button>)}</div></div><label className="flex h-9 items-center gap-2 border border-border bg-surface/95 px-3 text-[10px] text-textSecondary shadow-lg"><span>Region</span><select aria-label="Region" value={region} onChange={(event) => setRegion(event.target.value)} className="bg-transparent text-textPrimary outline-none"><option value="all">All regions</option>{regions.map((item) => <option key={item} value={item}>{item}</option>)}</select><ChevronDown className="h-3 w-3" /></label></div></div>;
const ControlButton = ({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) => <button type="button" title={label} aria-label={label} onClick={onClick} className="flex h-8 w-8 items-center justify-center text-textSecondary hover:bg-surfaceHover hover:text-white focus-visible:outline-2 focus-visible:outline-primary [&>svg]:h-4 [&>svg]:w-4">{children}</button>;

const InspectionPanel = ({ selectedSegment, selectedState, selectedEvent, selectedVehicle, timeline, predictionCounts, snapshot, onClose }: any) => <aside className="flex min-h-0 flex-col border border-border bg-surface xl:max-h-[620px]"><div className="flex items-center justify-between border-b border-border px-4 py-3"><div><div className="text-[10px] font-semibold uppercase tracking-wider text-textSecondary">Live inspection</div><div className="mt-0.5 text-xs text-textPrimary">Authoritative backend state</div></div>{(selectedSegment || selectedVehicle) && <button type="button" aria-label="Clear selection" onClick={onClose} className="text-textSecondary hover:text-white focus-visible:outline-2 focus-visible:outline-primary"><X className="h-4 w-4" /></button>}</div><div className="min-h-0 flex-1 overflow-y-auto p-4">{selectedVehicle ? <VehiclePanel vehicle={selectedVehicle} /> : selectedSegment ? <SegmentPopup segment={selectedSegment} state={selectedState} event={selectedEvent} /> : <Overview predictionCounts={predictionCounts} snapshot={snapshot} />}{selectedSegment && timeline.length > 0 && <Timeline entries={timeline} />}</div></aside>;
const Overview = ({ predictionCounts, snapshot }: { predictionCounts: [string, number][]; snapshot?: LiveMapSnapshot }) => <div><div className="text-sm text-textSecondary">Select a road or vehicle to inspect live backend values. Prediction and scenario layers remain independent.</div><div className="mt-5 text-[10px] font-semibold uppercase text-textSecondary">Prediction activity</div><div className="mt-2 space-y-2">{predictionCounts.length ? predictionCounts.map(([label, count]) => { const color = segmentStyles[label as keyof typeof segmentStyles]?.color ?? segmentStyles.unknown.color; return <div key={label} className="flex items-center gap-2"><span className="h-2 w-2" style={{ backgroundColor: color }} /><span className="flex-1 text-xs capitalize text-textPrimary">{label.replaceAll('_', ' ')}</span><span className="text-xs font-semibold text-white">{count}</span></div>; }) : <div className="text-xs text-textSecondary">No model predictions in the current snapshot.</div>}</div>{snapshot && <div className="mt-5 border-t border-border pt-4 text-[10px] leading-5 text-textSecondary"><div>Geo V2 federated model</div><div>23 causal features · 3 prior ticks</div><div>{snapshot.network_source} · {snapshot.network_version}</div><div>Backend tick interval represented by snapshot metadata</div></div>}</div>;
const VehiclePanel = ({ vehicle }: { vehicle: LiveVehicle }) => <div><div className="text-[10px] font-semibold uppercase text-textSecondary">{vehicle.vehicle_id}</div><div className="mt-1 text-lg font-semibold text-white">Vehicle telemetry</div><div className="mt-4 grid grid-cols-2 gap-3"><PanelValue label="State" value={vehicleTone(vehicle)} /><PanelValue label="Speed" value={`${vehicle.speed_kmph.toFixed(1)} km/h`} /><PanelValue label="Segment" value={vehicle.segment_id} /><PanelValue label="Region" value={vehicle.region_id} /><PanelValue label="Heading" value={`${vehicle.heading_deg.toFixed(0)}°`} /><PanelValue label="Updated" value={new Date(vehicle.timestamp).toLocaleTimeString()} /></div><div className="mt-4 text-[10px] text-textSecondary">Marker motion is interpolated visually between authoritative backend coordinates. No intermediate GPS points are invented.</div></div>;
const PanelValue = ({ label, value }: { label: string; value: string }) => <div className="border-l-2 border-border pl-2"><div className="text-[9px] uppercase text-textSecondary">{label}</div><div className="mt-0.5 truncate text-xs font-medium capitalize text-textPrimary" title={value}>{value}</div></div>;
const Timeline = ({ entries }: { entries: TimelineEntry[] }) => <section className="mt-5 border-t border-border pt-4"><div className="text-[10px] font-semibold uppercase text-textSecondary">Live history</div><div className="mt-2 space-y-2">{entries.map((entry) => <div key={entry.tick} className="grid grid-cols-[48px_1fr_auto] items-center gap-2 text-[10px]"><span className="text-textSecondary">{new Date(entry.observedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span><span className="capitalize text-textPrimary">{entry.prediction?.replaceAll('_', ' ') ?? 'No prediction'}</span><span className="text-textSecondary">{entry.speed?.toFixed(1) ?? '—'} km/h</span></div>)}</div></section>;
const MapLoading = ({ label, error = false }: { label: string; error?: boolean }) => <PageContainer className="max-w-[1800px]"><div className={`flex min-h-[70vh] items-center justify-center border border-border bg-surface text-sm ${error ? 'text-danger' : 'text-textSecondary'}`}>{label}</div></PageContainer>;

export default TrafficMap;
