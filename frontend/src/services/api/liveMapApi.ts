import { apiClient } from './client';

export interface SegmentData {
  segment_id: string;
  road_name: string;
  road_type: string;
  region_id: string;
  pincode: number;
  start_lat: number;
  start_lon: number;
  end_lat: number;
  end_lon: number;
  segment_length_m: number;
  number_of_lanes: number;
  road_width_m: number;
  max_speed_kmph: number;
  road_direction: string;
  flood_prone: boolean;
  neighbor_segments: string[];
}

export interface LiveVehicle {
  vehicle_id: string;
  vehicle_type: string;
  segment_id: string;
  region_id: string;
  lat: number;
  lon: number;
  speed_kmph: number;
  heading_deg: number;
  timestamp: string;
}

export interface LiveSegmentState {
  segment_id: string;
  region_id: string;
  latest_timestamp: string;
  vehicle_count: number;
  average_speed_kmph: number;
  density: number;
  current_event: string;
  available: boolean;
  last_updated: string;
}

export interface LiveEvent {
  event_id: string;
  segment_id: string;
  region_id: string;
  event_type: string;
  timestamp: string;
}

export interface LiveMapSnapshot {
  source_id: string;
  run_id: string;
  batch_id: string;
  tick_number: number;
  observed_at: string;
  received_at: string;
  server_time: string;
  poll_interval_seconds: number;
  stale_after_seconds: number;
  segments: LiveSegmentState[];
  vehicles: LiveVehicle[];
  events: LiveEvent[];
  summary: {
    vehicle_count: number;
    active_segments: number;
    active_events: number;
    average_speed_kmph: number;
    latest_update: string;
  };
}

export const fetchSegments = async (): Promise<SegmentData[]> =>
  (await apiClient.get<SegmentData[]>('/api/v1/segments')).data;

export const fetchLiveSnapshot = async (): Promise<LiveMapSnapshot> =>
  (await apiClient.get<LiveMapSnapshot>('/api/v1/live-map/snapshot')).data;
