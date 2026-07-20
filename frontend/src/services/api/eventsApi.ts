import axios from 'axios';

export interface EventOut {
  id: number;
  segment_id: string;
  event_type: string;
  confidence: number;
  start_time: string;
  end_time: string | null;
  is_active: boolean;
}

export const fetchActiveEvents = async (): Promise<EventOut[]> => {
  const response = await axios.get('http://localhost:8000/api/v1/events');
  return response.data;
};
