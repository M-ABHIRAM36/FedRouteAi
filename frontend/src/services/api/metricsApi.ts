import axios from 'axios';

export interface DashboardMetrics {
  active_regions: number;
  total_events: number;
  total_segments: number;
  system_health: string;
}

export const fetchDashboardMetrics = async (): Promise<DashboardMetrics> => {
  const response = await axios.get('http://localhost:8000/api/v1/metrics');
  return response.data;
};
