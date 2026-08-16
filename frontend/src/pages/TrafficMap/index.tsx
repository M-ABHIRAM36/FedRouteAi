import { useEffect, useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import type { LatLngBoundsExpression, Map as LeafletMap } from 'leaflet';
import { Activity, Car, ChevronDown, Clock3, EyeOff, Layers3, LocateFixed, Pause, Play, Radio, RotateCcw, TriangleAlert, Wifi, WifiOff, X } from 'lucide-react';
import 'leaflet/dist/leaflet.css';
import { useQuery } from '@tanstack/react-query';
import { PageContainer } from '../../components/common/PageContainer';
import { fetchLiveSnapshot, fetchSegments, type LiveMapSnapshot, type LiveVehicle } from '../../services/api/liveMapApi';
import { MapLegend } from '../../components/map/MapLegend';
import { SegmentPopup } from '../../components/map/SegmentPopup';
import { getSegmentStyle } from '../../components/map/segmentStyles';

type ConnectionStatus = 'CONNECTING' | 'LIVE' | 'STALE' | 'DISCONNECTED' | 'ERROR';

const statusColors: Record<ConnectionStatus, string> = {
  CONNECTING: 'text-warning bg-warning/10 border-warning/25',
  LIVE: 'text-success bg-success/10 border-success/25',
  STALE: 'text-warning bg-warning/10 border-warning/25',
  DISCONNECTED: 'text-textSecondary bg-surfaceHover border-border',
  ERROR: 'text-danger bg-danger/10 border-danger/25',
};

const eventLabels: Record<string, string> = {
  road_block: 'Road block', construction: 'Construction', accident: 'Accident', flood: 'Flood',
  diversion: 'Diversion', road_damage: 'Road damage', congestion: 'Congestion', normal: 'Normal',
};

const ageSeconds = (snapshot: LiveMapSnapshot | undefined, now: number) => {
  if (!snapshot) return Infinity;
  return Math.max(0, (now - Date.parse(snapshot.received_at)) / 1000);
};

const FitNetwork = ({ bounds, resetKey }: { bounds: LatLngBoundsExpression; resetKey: number }) => {
  const map = useMap();
  useEffect(() => { map.fitBounds(bounds, { padding: [24, 24], maxZoom: 14 }); }, [bounds, map, resetKey]);
  return null;
};

const ViewportTracker = ({ onChange }: { onChange: (map: LeafletMap) => void }) => {
  useMapEvents({ moveend: (event) => onChange(event.target), zoomend: (event) => onChange(event.target) });
  return null;
};

const MapToolbar = ({ onFit, showRoads, setShowRoads, showVehicles, setShowVehicles, showEvents, setShowEvents, regions, region, setRegion }: {
  onFit: () => void; showRoads: boolean; setShowRoads: (value: boolean) => void; showVehicles: boolean;
  setShowVehicles: (value: boolean) => void; showEvents: boolean; setShowEvents: (value: boolean) => void;
  regions: string[]; region: string; setRegion: (value: string) => void;
}) => (
  <div className="absolute left-3 right-3 top-3 z-[500] flex flex-wrap items-center gap-2 pointer-events-none">
    <div className="pointer-events-auto flex items-center gap-1 border border-border bg-surface/95 p-1 shadow-lg backdrop-blur-sm">
      <MapToolButton label="Fit network" onClick={onFit}><LocateFixed className="h-4 w-4" /></MapToolButton>
      <MapToolButton label="Reset view" onClick={onFit}><RotateCcw className="h-4 w-4" /></MapToolButton>
      <MapToolButton label={showRoads ? 'Hide road states' : 'Show road states'} onClick={() => setShowRoads(!showRoads)}>{showRoads ? <Layers3 className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}</MapToolButton>
      <MapToolButton label={showVehicles ? 'Hide vehicles' : 'Show vehicles'} onClick={() => setShowVehicles(!showVehicles)}>{showVehicles ? <Car className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}</MapToolButton>
      <MapToolButton label={showEvents ? 'Hide events' : 'Show events'} onClick={() => setShowEvents(!showEvents)}>{showEvents ? <TriangleAlert className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}</MapToolButton>
    </div>
    <label className="pointer-events-auto flex h-9 items-center gap-2 border border-border bg-surface/95 px-3 text-xs text-textSecondary shadow-lg backdrop-blur-sm">
      <span>Region</span><select value={region} onChange={(event) => setRegion(event.target.value)} className="bg-transparent text-textPrimary outline-none"><option value="all">All regions</option>{regions.map((item) => <option key={item} value={item}>{item}</option>)}</select><ChevronDown className="h-3.5 w-3.5" />
    </label>
  </div>
);

const MapToolButton = ({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) => (
  <button type="button" title={label} aria-label={label} onClick={onClick} className="flex h-8 w-8 items-center justify-center text-textSecondary transition-colors hover:bg-surfaceHover hover:text-textPrimary">{children}</button>
);

const StatusPill = ({ status }: { status: ConnectionStatus }) => (
  <div className={`flex items-center gap-2 border px-2.5 py-1.5 text-[11px] font-semibold tracking-wide ${statusColors[status]}`} aria-live="polite">
    <span className={`h-2 w-2 rounded-full ${status === 'LIVE' ? 'animate-pulse bg-success' : status === 'ERROR' ? 'bg-danger' : 'bg-current'}`} />{status}
  </div>
);

const Metric = ({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) => (
  <div className="flex min-w-[108px] items-center gap-2 border-l border-border pl-3 first:border-l-0 first:pl-0"><span className="text-textSecondary">{icon}</span><div><div className="text-[10px] uppercase tracking-wider text-textSecondary">{label}</div><div className="text-sm font-semibold text-textPrimary">{value}</div></div></div>
);

const VehiclePopup = ({ vehicle }: { vehicle: LiveVehicle }) => (
  <div className="w-48 text-xs text-textPrimary"><div className="mb-2 border-b border-border pb-2 font-semibold text-white">{vehicle.vehicle_id}</div><div className="space-y-1"><Row label="Type" value={vehicle.vehicle_type} /><Row label="Segment" value={vehicle.segment_id} /><Row label="Region" value={vehicle.region_id} /><Row label="Speed" value={`${vehicle.speed_kmph.toFixed(1)} km/h`} /><Row label="Heading" value={`${vehicle.heading_deg.toFixed(0)}°`} /><Row label="Timestamp" value={new Date(vehicle.timestamp).toLocaleTimeString()} /></div></div>
);

const Row = ({ label, value }: { label: string; value: string }) => <div className="flex justify-between gap-3"><span className="text-textSecondary">{label}</span><span className="text-right font-medium">{value}</span></div>;

const TrafficMap = () => {
  const [liveMode, setLiveMode] = useState(false);
  const [showRoads, setShowRoads] = useState(true);
  const [showVehicles, setShowVehicles] = useState(true);
  const [showEvents, setShowEvents] = useState(true);
  const [region, setRegion] = useState('all');
  const [selectedSegmentId, setSelectedSegmentId] = useState<string>();
  const [selectedVehicleId, setSelectedVehicleId] = useState<string>();
  const [fitKey, setFitKey] = useState(0);
  const [visibleVehicleCount, setVisibleVehicleCount] = useState(0);
  const [lastError, setLastError] = useState<string>();
  const [now, setNow] = useState(() => Date.now());

  const staticQuery = useQuery({ queryKey: ['live-map', 'segments'], queryFn: fetchSegments, staleTime: Infinity, retry: 1 });
  const liveQuery = useQuery({
    queryKey: ['live-map', 'snapshot'], queryFn: fetchLiveSnapshot, enabled: liveMode,
    refetchInterval: liveMode ? (query) => (query.state.data?.poll_interval_seconds ?? 4) * 1000 : false,
    retry: false, refetchOnWindowFocus: false,
  });
  const snapshot = liveQuery.data;
  const segments = useMemo(() => staticQuery.data ?? [], [staticQuery.data]);
  const states = useMemo(() => new Map((snapshot?.segments ?? []).map((state) => [state.segment_id, state])), [snapshot]);
  const events = snapshot?.events ?? [];
  const regions = useMemo(() => [...new Set(segments.map((segment) => segment.region_id))].sort(), [segments]);
  const filteredSegments = useMemo(() => segments.filter((segment) => region === 'all' || segment.region_id === region), [segments, region]);
  const filteredVehicles = useMemo(() => (snapshot?.vehicles ?? []).filter((vehicle) => region === 'all' || vehicle.region_id === region), [snapshot, region]);
  const selectedSegment = segments.find((segment) => segment.segment_id === selectedSegmentId);
  const selectedState = selectedSegmentId ? states.get(selectedSegmentId) : undefined;
  const selectedVehicle = filteredVehicles.find((vehicle) => vehicle.vehicle_id === selectedVehicleId);
  const bounds = useMemo<LatLngBoundsExpression | undefined>(() => {
    if (!segments.length) return undefined;
    return segments.flatMap((segment) => [[segment.start_lat, segment.start_lon], [segment.end_lat, segment.end_lon]] as [number, number][]);
  }, [segments]);
  const status: ConnectionStatus = !liveMode ? 'DISCONNECTED' : lastError && !snapshot ? 'ERROR' : liveQuery.isFetching && !snapshot ? 'CONNECTING' : ageSeconds(snapshot, now) > (snapshot?.stale_after_seconds ?? 12) ? 'STALE' : 'LIVE';

  useEffect(() => { if (liveQuery.error) setLastError(liveQuery.error instanceof Error ? liveQuery.error.message : 'Live snapshot unavailable'); }, [liveQuery.error]);
  useEffect(() => { if (snapshot) setLastError(undefined); }, [snapshot]);
  useEffect(() => { if (!showVehicles || !snapshot) { setVisibleVehicleCount(0); } }, [showVehicles, snapshot]);
  useEffect(() => {
    if (!liveMode) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [liveMode]);

  const handleViewport = (map: LeafletMap) => {
    if (!showVehicles) return setVisibleVehicleCount(0);
    setVisibleVehicleCount(filteredVehicles.filter((vehicle) => map.getBounds().contains([vehicle.lat, vehicle.lon])).length);
  };
  const focusSegment = (segmentId: string) => {
    setSelectedSegmentId(segmentId);
    setSelectedVehicleId(undefined);
  };

  if (staticQuery.isLoading) return <PageContainer><div className="flex min-h-[70vh] items-center justify-center text-textSecondary">Loading canonical road network...</div></PageContainer>;
  if (staticQuery.isError) return <PageContainer><div className="flex min-h-[70vh] items-center justify-center border border-danger/30 bg-danger/5 text-danger">Road network unavailable. Start the backend and reload.</div></PageContainer>;
  if (!bounds) return <PageContainer><div className="flex min-h-[70vh] items-center justify-center text-textSecondary">No road geometry available.</div></PageContainer>;

  return (
    <PageContainer className="flex min-h-full flex-col gap-4">
      <header className="flex flex-col gap-3 border-b border-border pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div><div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary"><Activity className="h-3.5 w-3.5" />Traffic intelligence</div><h1 className="text-2xl font-semibold text-white">Live traffic map</h1><p className="mt-1 text-sm text-textSecondary">Canonical Hyderabad network · {segments.length} segments · backend state only</p></div>
        <div className="flex flex-wrap items-center gap-2"><StatusPill status={status} /><button type="button" onClick={() => setLiveMode(!liveMode)} className={`flex items-center gap-2 px-3 py-2 text-xs font-semibold ${liveMode ? 'border border-danger/40 bg-danger/10 text-danger' : 'bg-primary text-white hover:bg-primaryHover'}`}>{liveMode ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}{liveMode ? 'Stop live' : 'Start live'}</button></div>
      </header>
      <section className="flex flex-wrap items-center gap-x-5 gap-y-3 border border-border bg-surface px-4 py-3"><Metric label="Vehicles" value={snapshot ? snapshot.summary.vehicle_count.toLocaleString() : '—'} icon={<Car className="h-4 w-4" />} /><Metric label="Active segments" value={snapshot ? snapshot.summary.active_segments.toString() : '—'} icon={<Layers3 className="h-4 w-4" />} /><Metric label="Events" value={snapshot ? snapshot.summary.active_events.toString() : '—'} icon={<TriangleAlert className="h-4 w-4" />} /><Metric label="Average speed" value={snapshot ? `${snapshot.summary.average_speed_kmph.toFixed(1)} km/h` : '—'} icon={<Radio className="h-4 w-4" />} /><Metric label="Last update" value={snapshot ? new Date(snapshot.summary.latest_update).toLocaleTimeString() : '—'} icon={<Clock3 className="h-4 w-4" />} /><div className="ml-auto text-xs text-textSecondary" aria-live="polite">{lastError ?? (snapshot ? `Tick ${snapshot.tick_number} · ${snapshot.source_id}` : 'Live updates paused')}</div></section>
      <div className="grid min-h-[660px] flex-1 gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="relative min-h-[560px] overflow-hidden border border-border bg-[#15202b]">
          <MapContainer bounds={bounds} className="h-full min-h-[560px] w-full" zoomControl={true} preferCanvas>
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" errorTileUrl="" />
            <FitNetwork bounds={bounds} resetKey={fitKey} />
            <ViewportTracker onChange={handleViewport} />
            <MapToolbar onFit={() => setFitKey((key) => key + 1)} showRoads={showRoads} setShowRoads={setShowRoads} showVehicles={showVehicles} setShowVehicles={setShowVehicles} showEvents={showEvents} setShowEvents={setShowEvents} regions={regions} region={region} setRegion={setRegion} />
            {showRoads && filteredSegments.map((segment) => { const state = states.get(segment.segment_id); const style = getSegmentStyle(state); return <Polyline key={segment.segment_id} positions={[[segment.start_lat, segment.start_lon], [segment.end_lat, segment.end_lon]]} pathOptions={style} eventHandlers={{ click: () => focusSegment(segment.segment_id) }}><Popup><SegmentPopup segment={segment} state={state} /></Popup></Polyline>; })}
            {showVehicles && filteredVehicles.map((vehicle) => <CircleMarker key={vehicle.vehicle_id} center={[vehicle.lat, vehicle.lon]} radius={selectedVehicleId === vehicle.vehicle_id ? 7 : 4} pathOptions={{ color: selectedVehicleId === vehicle.vehicle_id ? '#ffffff' : '#38bdf8', fillColor: '#0ea5e9', fillOpacity: 0.95, weight: 1.5 }} eventHandlers={{ click: () => { setSelectedVehicleId(vehicle.vehicle_id); setSelectedSegmentId(undefined); } }}><Popup><VehiclePopup vehicle={vehicle} /></Popup></CircleMarker>)}
            {showEvents && events.filter((event) => region === 'all' || event.region_id === region).map((event) => { const segment = segments.find((item) => item.segment_id === event.segment_id); return segment ? <CircleMarker key={`event-${event.event_id}`} center={[(segment.start_lat + segment.end_lat) / 2, (segment.start_lon + segment.end_lon) / 2]} radius={9} pathOptions={{ color: '#fff', fillColor: '#ef4444', fillOpacity: 0.85, weight: 2 }} eventHandlers={{ click: () => focusSegment(event.segment_id) }} /> : null; })}
          </MapContainer>
          <div className="absolute bottom-3 left-3 z-[500]"><MapLegend /></div>
          {showVehicles && snapshot && <div className="absolute bottom-3 right-3 z-[500] border border-border bg-surface/95 px-3 py-2 text-[11px] text-textSecondary shadow-lg">Visible vehicles <span className="font-semibold text-textPrimary">{visibleVehicleCount}</span> / backend <span className="font-semibold text-textPrimary">{snapshot.summary.vehicle_count}</span></div>}
        </div>
        <aside className="flex min-h-[560px] flex-col border border-border bg-surface">
          <div className="flex items-center justify-between border-b border-border px-4 py-3"><div className="text-xs font-semibold uppercase tracking-wider text-textSecondary">Live inspection</div>{(selectedSegment || selectedVehicle) && <button type="button" aria-label="Clear selection" title="Clear selection" onClick={() => { setSelectedSegmentId(undefined); setSelectedVehicleId(undefined); }} className="text-textSecondary hover:text-textPrimary"><X className="h-4 w-4" /></button>}</div>
          <div className="border-b border-border p-4">{selectedVehicle ? <VehiclePopup vehicle={selectedVehicle} /> : selectedSegment ? <SegmentPopup segment={selectedSegment} state={selectedState} /> : <div className="text-sm text-textSecondary">Select a road segment or vehicle to inspect backend values.</div>}</div>
          <div className="min-h-0 flex-1 overflow-y-auto p-4"><div className="mb-3 flex items-center justify-between"><h2 className="text-xs font-semibold uppercase tracking-wider text-textSecondary">Active events</h2><span className="text-xs text-textSecondary">{events.length}</span></div>{events.length ? <div className="space-y-2">{events.filter((event) => region === 'all' || event.region_id === region).map((event) => <button type="button" key={event.event_id} onClick={() => focusSegment(event.segment_id)} className="w-full border border-border bg-background p-3 text-left transition-colors hover:border-danger/50 hover:bg-surfaceHover"><div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold uppercase text-danger">{eventLabels[event.event_type] ?? event.event_type}</span><span className="text-[10px] text-textSecondary">{new Date(event.timestamp).toLocaleTimeString()}</span></div><div className="mt-1 text-xs text-textPrimary">{event.segment_id} · {event.region_id}</div></button>)}</div> : <div className="text-sm text-textSecondary">No event-labelled telemetry in the latest snapshot.</div>}</div>
          <div className="border-t border-border p-4 text-xs text-textSecondary"><div className="flex items-center gap-2">{status === 'LIVE' ? <Wifi className="h-3.5 w-3.5 text-success" /> : <WifiOff className="h-3.5 w-3.5" />}<span>{status === 'LIVE' ? 'Receiving backend updates' : status === 'DISCONNECTED' ? 'Live mode is paused' : status === 'STALE' ? 'Backend data is stale' : 'Waiting for backend'}</span></div>{snapshot && <div className="mt-1">Stale after {snapshot.stale_after_seconds.toFixed(0)}s · source {snapshot.source_id}</div>}</div>
        </aside>
      </div>
    </PageContainer>
  );
};

export default TrafficMap;
