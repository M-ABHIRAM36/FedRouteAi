import axios from 'axios';

export interface PredictionRequest {
  road_id: string;
  speed: number;
  density: number;
  travel_time: number;
  heading: number;
}

export interface PredictionResponse {
  prediction: string;
  confidence: number;
  probabilities: Record<string, number>;
  inference_time_ms: number;
}

export const predictTrafficEvent = async (data: PredictionRequest): Promise<PredictionResponse> => {
  const response = await axios.post('http://localhost:8000/api/v1/predict', data);
  return response.data;
};
