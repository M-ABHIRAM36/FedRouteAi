import axios from 'axios';
import type { SegmentData } from '../../components/map/SegmentPopup';

// Simple mock data for initial map render since real API integration isn't fully required for UI preview
export const fetchSegments = async (): Promise<SegmentData[]> => {
  // Try fetching from the actual API if backend is running, otherwise fallback to mock data
  try {
    const response = await axios.get('http://localhost:8000/api/v1/segments');
    return response.data;
  } catch (error) {
    console.warn("Backend not reachable. Using mock segments.");
    // Return a small grid of mock segments for CRS.Simple plane
    const mock: SegmentData[] = [];
    for(let i = 0; i < 5; i++) {
      for(let j = 0; j < 5; j++) {
        mock.push({
          segment_id: `MOCK_${i}_${j}`,
          region_id: `REGION_0${(i % 8) + 1}`,
          type: (i === 2 && j === 2) ? 'Construction' : 'Normal',
          base_speed: 40,
        });
      }
    }
    return mock;
  }
};
