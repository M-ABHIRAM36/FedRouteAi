import { apiClient } from './client';

export interface RouteCoordinate {
  lat: number;
  lon: number;
}

export interface ShortestRouteRequest {
  origin: RouteCoordinate;
  destination: RouteCoordinate;
  network_source: string;
  network_version: string;
  source_id?: string;
  run_id?: string;
  avoid_segment_ids?: string[];
}

export interface ShortestRouteResponse {
  network_source: string;
  network_version: string;
  algorithm: string;
  cost_basis: string;
  origin: RouteCoordinate;
  destination: RouteCoordinate;
  snapped_origin: RouteCoordinate & { segment_id: string; distance_to_road_m: number };
  snapped_destination: RouteCoordinate & { segment_id: string; distance_to_road_m: number };
  distance_m: number;
  estimated_duration_s: number;
  computation_time_ms: number;
  segment_count: number;
  ordered_segment_ids: string[];
  geometry: { type: 'LineString'; coordinates: [number, number][] };
  predictions: {
    available: boolean;
    source_id?: string | null;
    run_id?: string | null;
    counts: Record<string, number>;
    abnormal_segment_count: number;
    covered_segment_count: number;
    coverage_ratio: number;
    warnings: string[];
  };
}

export const calculateShortestRoute = async (request: ShortestRouteRequest): Promise<ShortestRouteResponse> =>
  (await apiClient.post<ShortestRouteResponse>('/api/v1/routes/shortest', request)).data;
