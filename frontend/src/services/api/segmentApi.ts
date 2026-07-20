import axios from 'axios';
import type { SegmentData } from '../../components/map/SegmentPopup';

export const fetchSegments = async (): Promise<SegmentData[]> => {
  const response = await axios.get('http://localhost:8000/api/v1/segments');
  return response.data;
};
