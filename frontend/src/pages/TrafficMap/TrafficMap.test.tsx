import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TrafficMap from './index';
import { fetchLiveSnapshot, fetchSegments, type LiveMapSnapshot, type SegmentData } from '../../services/api/liveMapApi';

vi.mock('../../services/api/liveMapApi', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../services/api/liveMapApi')>();
  return { ...original, fetchSegments: vi.fn(), fetchLiveSnapshot: vi.fn() };
});

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: () => <div data-testid="tiles" />,
  Polyline: ({ children, eventHandlers, positions }: { children: ReactNode; eventHandlers?: { click?: () => void }; positions: unknown }) => <button data-testid="road" data-positions={JSON.stringify(positions)} onClick={eventHandlers?.click}>{children}</button>,
  CircleMarker: ({ children, eventHandlers, center }: { children?: ReactNode; eventHandlers?: { click?: () => void }; center: unknown }) => <button data-testid="marker" data-center={JSON.stringify(center)} onClick={eventHandlers?.click}>{children}</button>,
  Popup: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  useMap: () => ({ fitBounds: vi.fn() }),
  useMapEvents: () => undefined,
}));

const segments: SegmentData[] = Array.from({ length: 3 }, (_, index) => ({
  segment_id: `SEG_${index + 1}`, road_name: `Road ${index + 1}`, road_type: 'arterial',
  region_id: index < 2 ? 'REGION_01' : 'REGION_02', pincode: 500001,
  start_lat: 17.38 + index * 0.001, start_lon: 78.48, end_lat: 17.381 + index * 0.001,
  end_lon: 78.481, segment_length_m: 500, number_of_lanes: 2, road_width_m: 8,
  max_speed_kmph: 50, road_direction: 'bidirectional', flood_prone: false, neighbor_segments: [],
}));

const snapshot = (receivedAt = new Date().toISOString()): LiveMapSnapshot => ({
  source_id: 'test-source', run_id: 'test-run', batch_id: 'tick-1', tick_number: 1,
  observed_at: receivedAt, received_at: receivedAt, server_time: receivedAt,
  poll_interval_seconds: 0.02, stale_after_seconds: 12,
  segments: segments.map((segment, index) => ({
    segment_id: segment.segment_id, region_id: segment.region_id, latest_timestamp: receivedAt,
    vehicle_count: index + 1, average_speed_kmph: 25, density: index + 1,
    current_event: index === 0 ? 'accident' : 'normal', available: true, last_updated: receivedAt,
  })),
  vehicles: [{ vehicle_id: 'VEH_1', vehicle_type: 'car', segment_id: 'SEG_1', region_id: 'REGION_01', lat: 17.3805, lon: 78.4805, speed_kmph: 22, heading_deg: 90, timestamp: receivedAt }],
  events: [{ event_id: 'EVT_1', segment_id: 'SEG_1', region_id: 'REGION_01', event_type: 'accident', timestamp: receivedAt }],
  summary: { vehicle_count: 1, active_segments: 3, active_events: 1, average_speed_kmph: 22, latest_update: receivedAt },
});

const renderMap = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><TrafficMap /></QueryClientProvider>);
};

describe('TrafficMap', () => {
  beforeEach(() => {
    vi.mocked(fetchSegments).mockResolvedValue(segments);
    vi.mocked(fetchLiveSnapshot).mockResolvedValue(snapshot());
  });
  afterEach(() => vi.clearAllMocks());

  it('loads static backend roads once and starts disconnected', async () => {
    renderMap();
    expect(await screen.findByTestId('map')).toBeInTheDocument();
    expect(screen.getAllByTestId('road')).toHaveLength(3);
    expect(screen.getAllByText('PAUSED').length).toBeGreaterThan(0);
    expect(fetchLiveSnapshot).not.toHaveBeenCalled();
  });

  it('starts live polling and renders backend vehicles, events, and counters', async () => {
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect(await screen.findByText('LIVE')).toBeInTheDocument();
    expect(await screen.findAllByText('VEH_1')).not.toHaveLength(0);
    expect(screen.getAllByText('Accident').length).toBeGreaterThan(0);
    expect(screen.getByText('Connected')).toBeInTheDocument();
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
    await screen.findByText('LIVE');
    fireEvent.click(screen.getByRole('button', { name: /pause live/i }));
    const calls = vi.mocked(fetchLiveSnapshot).mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 60));
    expect(fetchLiveSnapshot).toHaveBeenCalledTimes(calls);
    expect(screen.getAllByText('PAUSED').length).toBeGreaterThan(0);
  });

  it('shows error when the backend has no initial snapshot', async () => {
    vi.mocked(fetchLiveSnapshot).mockRejectedValue(new Error('Backend unavailable'));
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect((await screen.findAllByText('OFFLINE')).length).toBeGreaterThan(0);
    expect(screen.getByText('Backend unavailable')).toBeInTheDocument();
  });

  it('marks old backend data stale', async () => {
    vi.mocked(fetchLiveSnapshot).mockResolvedValue(snapshot(new Date(Date.now() - 60_000).toISOString()));
    renderMap();
    fireEvent.click(await screen.findByRole('button', { name: /start live/i }));
    expect((await screen.findAllByText('STALE')).length).toBeGreaterThan(0);
    expect(screen.getByText('Backend data is stale')).toBeInTheDocument();
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
    await screen.findByText('LIVE');
    fireEvent.click((await screen.findAllByTestId('road'))[0]);
    expect(screen.getAllByText('construction').length).toBeGreaterThan(0);
    expect(screen.getAllByText('91.0%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('federated-round-7').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/scenario ground truth/i).length).toBeGreaterThan(0);
  });
});
