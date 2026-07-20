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
  inference_time_ms: number;
  status: 'success' | 'error';
  message?: string;
  demo_mode?: boolean;
}

export const predictTrafficEvent = async (data: PredictionRequest): Promise<PredictionResponse> => {
  try {
    const response = await axios.post('http://localhost:8000/api/v1/predict', data, {
      timeout: 5000, // 5s timeout
    });
    return response.data;
  } catch (error) {
    console.warn("Backend prediction failed or unavailable. Falling back to Demo Mode.");
    
    // Simulate Demo Mode inference
    await new Promise(resolve => setTimeout(resolve, 800)); // Simulate network/inference latency
    
    const randomSeed = Math.random();
    let mockPrediction = 'Normal';
    if (data.speed < 20 && data.density > 60) {
      mockPrediction = randomSeed > 0.5 ? 'Construction' : 'Accident';
    } else if (data.speed < 40 && data.density > 40) {
      mockPrediction = randomSeed > 0.5 ? 'Normal' : 'Diversion';
    }

    return {
      prediction: mockPrediction,
      confidence: 0.75 + (Math.random() * 0.2), // Random confidence between 75% and 95%
      inference_time_ms: 12 + Math.floor(Math.random() * 20),
      status: 'success',
      demo_mode: true,
    };
  }
};
