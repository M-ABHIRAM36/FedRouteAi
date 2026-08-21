import { apiClient } from './client';

export type DemoScenario = 'normal' | 'congestion' | 'accident';

export interface DemoRun {
  source_id: string;
  run_id: string;
  scenario: DemoScenario;
  status: string;
  simulation_time: string;
  tick_number: number;
  vehicle_count: number;
  network_source: string;
  network_version: string;
  corridor_segment_ids: string[];
  route_distance_m: number;
  disturbance_segment_id?: string | null;
  model_feature_count: number;
  history_ticks: number;
  cadence_seconds: number;
  accepted_observations?: number;
  observed_segments?: number;
  predictions_available?: number;
  ingestion_ms?: number;
  inference_ms?: number;
  labels_in_telemetry?: number;
  event_ids_in_telemetry?: number;
}

export const createDemoRun = async (scenario: DemoScenario, vehicleCount: number, orderedRouteSegmentIds: string[], routeDistanceM: number): Promise<DemoRun> =>
  (await apiClient.post<DemoRun>('/api/v1/demo/geo-v2/runs', { scenario, vehicle_count: vehicleCount, random_seed: 42, ordered_route_segment_ids: orderedRouteSegmentIds, route_distance_m: routeDistanceM })).data;

export const stepDemoRun = async (runId: string): Promise<DemoRun> =>
  (await apiClient.post<DemoRun>(`/api/v1/demo/geo-v2/runs/${runId}/step`)).data;

export const stopDemoRun = async (runId: string): Promise<void> => {
  await apiClient.delete(`/api/v1/demo/geo-v2/runs/${runId}`);
};
