import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TrafficMap from './index';
import { fetchLiveSnapshot, fetchSegments, type LiveMapSnapshot, type SegmentData } from '../../services/api/liveMapApi';
import { calculateShortestRoute, type ShortestRouteResponse } from '../../services/api/routeApi';
import { createDemoRun, stepDemoRun, stopDemoRun, type DemoRun } from '../../services/api/demoApi';

let mapClick: ((event: { latlng: { lat: number; lng: number } }) => void) | undefined;

vi.mock('../../services/api/liveMapApi', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../services/api/liveMapApi')>();
  return { ...original, fetchSegments: vi.fn(), fetchLiveSnapshot: vi.fn() };
});
vi.mock('../../services/api/routeApi', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../services/api/routeApi')>();
  return { ...original, calculateShortestRoute: vi.fn() };
});
vi.mock('../../services/api/demoApi', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../services/api/demoApi')>();
  return { ...original, createDemoRun: vi.fn(), stepDemoRun: vi.fn(), stopDemoRun: vi.fn() };
});

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: () => <div data-testid="tiles" />,
  Polyline: ({ children, eventHandlers, positions, ...props }: { children: ReactNode; eventHandlers?: { click?: () => void }; positions: unknown; 'data-testid'?: string }) => <button data-testid={props['data-testid'] ?? 'road'} data-positions={JSON.stringify(positions)} onClick={eventHandlers?.click}>{children}</button>,
  CircleMarker: ({ children, eventHandlers, center }: { children?: ReactNode; eventHandlers?: { click?: () => void }; center: unknown }) => <button data-testid="marker" data-center={JSON.stringify(center)} onClick={eventHandlers?.click}>{children}</button>,
  Popup: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  useMap: () => ({ fitBounds: vi.fn() }),
  useMapEvents: (handlers: { click?: (event: { latlng: { lat: number; lng: number } }) => void }) => { if (handlers.click) mapClick = handlers.click; return undefined; },
}));

const segments: SegmentData[] = Array.from({ length: 3 }, (_, index) => ({
  segment_id: `SEG_${index + 1}`, road_name: `Road ${index + 1}`, road_type: 'arterial',
  region_id: index < 2 ? 'REGION_01' : 'REGION_02', pincode: 500001,
  start_lat: 17.38 + index * 0.001, start_lon: 78.48, end_lat: 17.381 + index * 0.001,
  end_lon: 78.481, segment_length_m: 500, number_of_lanes: 2, road_width_m: 8,
  max_speed_kmph: 50, road_direction: 'bidirectional', flood_prone: false, neighbor_segments: [],
}));

const snapshot = (receivedAt = new Date().toISOString(), observedAt = receivedAt): LiveMapSnapshot => ({
  source_id: 'test-source', run_id: 'test-run', batch_id: 'tick-1', tick_number: 1,
  observed_at: observedAt, received_at: receivedAt, server_time: receivedAt,
  poll_interval_seconds: 0.02, stale_after_seconds: 12, network_source: 'osm_geo_v2', network_version: 'beeramguda-test',
  segments: segments.map((segment, index) => ({
    segment_id: segment.segment_id, region_id: segment.region_id, latest_timestamp: receivedAt,
    vehicle_count: index + 1, average_speed_kmph: 25, density: index + 1,
    current_event: index === 0 ? 'accident' : 'normal', available: true, last_updated: receivedAt,
  })),
  vehicles: [{ vehicle_id: 'VEH_1', vehicle_type: 'car', segment_id: 'SEG_1', region_id: 'REGION_01', lat: 17.3805, lon: 78.4805, speed_kmph: 22, heading_deg: 90, timestamp: receivedAt }],
  events: [{ event_id: 'EVT_1', segment_id: 'SEG_1', region_id: 'REGION_01', event_type: 'accident', timestamp: receivedAt }],
  summary: { vehicle_count: 1, active_segments: 3, active_events: 1, average_speed_kmph: 22, latest_update: receivedAt },
});

const routeResult: ShortestRouteResponse = {
  network_source: 'osm_geo_v2', network_version: 'beeramguda-test', algorithm: 'Dijkstra', cost_basis: 'distance',
  origin: { lat: 17.38, lon: 78.48 }, destination: { lat: 17.382, lon: 78.482 },
  snapped_origin: { lat: 17.38, lon: 78.48, segment_id: 'SEG_1', distance_to_road_m: 2 },
  snapped_destination: { lat: 17.382, lon: 78.482, segment_id: 'SEG_3', distance_to_road_m: 3 },
  distance_m: 4820, estimated_duration_s: 600, computation_time_ms: 4.2, segment_count: 3,
  ordered_segment_ids: ['SEG_1', 'SEG_2', 'SEG_3'],
  geometry: { type: 'LineString', coordinates: [[78.48, 17.38], [78.481, 17.381], [78.482, 17.382]] },
  predictions: { available: true, counts: { normal: 2, congestion: 1 }, abnormal_segment_count: 1, covered_segment_count: 3, coverage_ratio: 1, warnings: ['This route contains predicted congestion.'] },
};

const demoRun: DemoRun = {
  source_id: 'geo-v2-demo', run_id: 'demo-test', scenario: 'congestion', status: 'ready',
  simulation_time: '2026-08-17T08:02:00', tick_number: 1, vehicle_count: 100,
  network_source: 'osm_geo_v2', network_version: 'beeramguda-test',
  corridor_segment_ids: ['SEG_1', 'SEG_2', 'SEG_3'], route_distance_m: 4820, disturbance_segment_id: 'SEG_2',
  model_feature_count: 23, history_ticks: 3, cadence_seconds: 120,
  accepted_observations: 100, observed_segments: 3, predictions_available: 3,
  ingestion_ms: 10, inference_ms: 5, labels_in_telemetry: 0, event_ids_in_telemetry: 0,
};

const renderMap = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><TrafficMap /></QueryClientProvider>);
};

describe('TrafficMap', () => {
  beforeEach(() => {
    mapClick = undefined;
    vi.mocked(fetchSegments).mockResolvedValue(segments);
    vi.mocked(fetchLiveSnapshot).mockResolvedValue(snapshot());
    vi.mocked(calculateShortestRoute).mockResolvedValue(routeResult);
    vi.mocked(createDemoRun).mockResolvedValue(demoRun);
    vi.mocked(stepDemoRun).mockResolvedValue(demoRun);
    vi.mocked(stopDemoRun).mockResolvedValue(undefined);
  });

  it('selects route endpoints on the existing map, renders the route, summary, and clears it', async () => {
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect((await screen.findAllByText('LIVE')).length).toBeGreaterThan(0);
    expect((await screen.findAllByText('LIVE')).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /select origin on map/i }));
    act(() => mapClick?.({ latlng: { lat: 17.38, lng: 78.48 } }));
    act(() => mapClick?.({ latlng: { lat: 17.382, lng: 78.482 } }));
    fireEvent.click(screen.getByRole('button', { name: /calculate route/i }));

    expect(await screen.findByTestId('route-line')).toHaveAttribute('data-positions', '[[17.38,78.48],[17.381,78.481],[17.382,78.482]]');
    expect(screen.getByTestId('route-summary')).toHaveTextContent('4.82 km');
    expect(screen.getByTestId('route-summary')).toHaveTextContent('This route contains predicted congestion.');
    expect(calculateShortestRoute).toHaveBeenCalledWith(expect.objectContaining({
      network_source: 'osm_geo_v2', network_version: 'beeramguda-test', source_id: 'test-source', run_id: 'test-run',
    }));
    expect(screen.getAllByTestId('road')).toHaveLength(3);

    fireEvent.click(screen.getByRole('button', { name: /clear route/i }));
    expect(screen.queryByTestId('route-line')).not.toBeInTheDocument();
  });

  it('shows route backend errors without crashing the map', async () => {
    vi.mocked(calculateShortestRoute).mockRejectedValue({ response: { data: { detail: 'No directed route connects these locations.' } } });
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect((await screen.findAllByText('LIVE')).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /select origin on map/i }));
    act(() => mapClick?.({ latlng: { lat: 17.38, lng: 78.48 } }));
    act(() => mapClick?.({ latlng: { lat: 17.382, lng: 78.482 } }));
    fireEvent.click(screen.getByRole('button', { name: /calculate route/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No directed route connects these locations.');
    expect(screen.getByTestId('map')).toBeInTheDocument();
  });
  afterEach(() => vi.clearAllMocks());

  it('loads static backend roads once and starts disconnected', async () => {
    renderMap();
    expect(await screen.findByTestId('map')).toBeInTheDocument();
    expect(screen.getAllByTestId('road')).toHaveLength(3);
    expect(screen.getAllByText('PAUSED').length).toBeGreaterThan(0);
    expect(fetchLiveSnapshot).not.toHaveBeenCalled();
  });

  it('starts a controlled demo with a scoped snapshot and resets its run', async () => {
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect((await screen.findAllByText('LIVE')).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /select origin on map/i }));
    act(() => mapClick?.({ latlng: { lat: 17.38, lng: 78.48 } }));
    act(() => mapClick?.({ latlng: { lat: 17.382, lng: 78.482 } }));
    fireEvent.click(screen.getByRole('button', { name: /calculate route/i }));
    expect(await screen.findByTestId('route-summary')).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText(/demo vehicles/i), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: /start demo/i }));

    await waitFor(() => expect(createDemoRun).toHaveBeenCalledWith('congestion', 100, ['SEG_1', 'SEG_2', 'SEG_3'], 4820));
    expect(stepDemoRun).toHaveBeenCalledWith('demo-test');
    await waitFor(() => expect(fetchLiveSnapshot).toHaveBeenCalledWith('geo-v2-demo', 'demo-test'));
    expect(screen.getByText(/3\/3/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^reset$/i }));
    expect(stopDemoRun).toHaveBeenCalledWith('demo-test');
    expect(screen.getByTestId('route-summary')).toBeInTheDocument();
  });

  it('requires a calculated route before starting a demo', async () => {
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start demo/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Calculate a route before starting');
    expect(createDemoRun).not.toHaveBeenCalled();
  });

  it('starts live polling and renders backend vehicles, events, and counters', async () => {
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect((await screen.findAllByText('LIVE')).length).toBeGreaterThan(0);
    expect(await screen.findAllByText('VEH_1')).not.toHaveLength(0);
    expect(screen.getAllByText('Accident').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Received just now').length).toBeGreaterThan(0);
  });

  it('updates vehicle positions on subsequent backend snapshots', async () => {
    vi.mocked(fetchLiveSnapshot)
      .mockResolvedValueOnce(snapshot())
      .mockResolvedValue({ ...snapshot(), vehicles: [{ ...snapshot().vehicles[0], speed_kmph: 44 }] });
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    await waitFor(() => expect(fetchLiveSnapshot).toHaveBeenCalledTimes(2));
    expect(await screen.findAllByText('44.0 km/h')).not.toHaveLength(0);
  });

  it('stops polling and reports disconnected without discarding the last snapshot', async () => {
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect((await screen.findAllByText('LIVE')).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /pause live/i }));
    const calls = vi.mocked(fetchLiveSnapshot).mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 60));
    expect(fetchLiveSnapshot).toHaveBeenCalledTimes(calls);
    expect(screen.getAllByText('PAUSED').length).toBeGreaterThan(0);
  });

  it('restarts through connecting before a new successful receipt becomes live', async () => {
    let resolveRestart: ((value: LiveMapSnapshot) => void) | undefined;
    vi.mocked(fetchLiveSnapshot)
      .mockResolvedValueOnce(snapshot())
      .mockImplementationOnce(() => new Promise((resolve) => { resolveRestart = resolve; }));
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect((await screen.findAllByText('LIVE')).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /pause live/i }));
    expect(screen.getAllByText('PAUSED').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /start live/i }));
    expect(screen.getAllByText('CONNECTING').length).toBeGreaterThan(0);
    resolveRestart?.(snapshot());
    expect((await screen.findAllByText('LIVE')).length).toBeGreaterThan(0);
  });

  it('shows error when the backend has no initial snapshot', async () => {
    vi.mocked(fetchLiveSnapshot).mockRejectedValue(new Error('Backend unavailable'));
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect((await screen.findAllByText('OFFLINE')).length).toBeGreaterThan(0);
    expect(screen.getByText('Backend unavailable')).toBeInTheDocument();
  });

  it('keeps historical simulation telemetry live when the browser receives it now', async () => {
    vi.mocked(fetchLiveSnapshot).mockResolvedValue(snapshot(new Date().toISOString(), '2026-08-17T08:02:00.000Z'));
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect((await screen.findAllByText('LIVE')).length).toBeGreaterThan(0);
    expect(screen.getByText(new Date('2026-08-17T08:02:00.000Z').toLocaleTimeString())).toBeInTheDocument();
    expect(screen.getAllByText('Received just now').length).toBeGreaterThan(0);
  });

  it('filters roads and vehicles by backend region IDs', async () => {
    renderMap();
    fireEvent.change(await screen.findByLabelText(/region/i), { target: { value: 'REGION_02' } });
    expect(screen.getAllByTestId('road')).toHaveLength(1);
  });

  it('toggles prediction and telemetry road layers independently', async () => {
    renderMap();
    expect(await screen.findAllByTestId('road')).toHaveLength(3);

    fireEvent.click(screen.getByRole('button', { name: 'Telemetry' }));
    expect(screen.getAllByTestId('road')).toHaveLength(6);
    fireEvent.click(screen.getByRole('button', { name: 'Predictions' }));
    expect(screen.getAllByTestId('road')).toHaveLength(3);
  });

  it('shows selected segment backend details', async () => {
    renderMap();
    fireEvent.click((await screen.findAllByTestId('road'))[0]);
    expect(screen.getAllByText(/SEG_1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('No prediction available').length).toBeGreaterThan(0);
  });

  it('renders full curved GeoJSON geometry in Leaflet latitude/longitude order', async () => {
    vi.mocked(fetchSegments).mockResolvedValue([{ ...segments[0], geometry: { type: 'LineString', coordinates: [[78.48, 17.38], [78.482, 17.386], [78.481, 17.381]] } }]);
    renderMap();
    expect(await screen.findByTestId('road')).toHaveAttribute('data-positions', '[[17.38,78.48],[17.386,78.482],[17.381,78.481]]');
  });

  it('fetches and displays the segment set matching the live snapshot network', async () => {
    const geoSegment = { ...segments[0], segment_id: 'OSM_100', road_name: 'OSM Main Road', network_source: 'osm_geo_v2', network_version: '2026-08', osm_way_id: 100 };
    vi.mocked(fetchSegments).mockImplementation(async (source) => source ? [geoSegment] : segments);
    vi.mocked(fetchLiveSnapshot).mockResolvedValue({ ...snapshot(), network_source: 'osm_geo_v2', network_version: '2026-08' });
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    await waitFor(() => expect(fetchSegments).toHaveBeenCalledWith('osm_geo_v2'));
    expect(await screen.findByText(/osm_geo_v2 · 1 segments/i)).toBeInTheDocument();
  });

  it('shows prediction metadata and scenario provenance only when supplied', async () => {
    vi.mocked(fetchLiveSnapshot).mockResolvedValue({
      ...snapshot(),
      segments: [{
        ...snapshot().segments[0], predicted_event: 'construction', prediction_confidence: 0.91,
        prediction_model_version: 'federated-round-7', historical_baseline: { speed: 42 },
        current_deviation: { speed_ratio: 0.52 },
      }],
      events: [{ ...snapshot().events[0], source: 'scenario_ground_truth', severity: 0.8 }],
    });
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect((await screen.findAllByText('LIVE')).length).toBeGreaterThan(0);
    fireEvent.click((await screen.findAllByTestId('road'))[0]);
    expect(screen.getAllByText('construction').length).toBeGreaterThan(0);
    expect(screen.getAllByText('91.0%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('federated-round-7').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/scenario ground truth/i).length).toBeGreaterThan(0);
  });
});
