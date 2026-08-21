import { describe, expect, it } from 'vitest';
import type { SegmentData } from '../../services/api/liveMapApi';
import { getSegmentMidpoint, getSegmentPositions } from './segmentGeometry';

const segment: SegmentData = {
  segment_id: 'SEG_1', road_name: 'Curved Road', road_type: 'arterial', region_id: 'REGION_01',
  pincode: 500001, start_lat: 17.38, start_lon: 78.48, end_lat: 17.39, end_lon: 78.49,
  segment_length_m: 500, number_of_lanes: 2, road_width_m: 8, max_speed_kmph: 50,
  road_direction: 'bidirectional', flood_prone: false, neighbor_segments: [],
};

describe('segment geometry', () => {
  it('converts every GeoJSON longitude/latitude coordinate for curved roads', () => {
    expect(getSegmentPositions({
      ...segment,
      geometry: { type: 'LineString', coordinates: [[78.48, 17.38], [78.485, 17.388], [78.49, 17.39]] },
    })).toEqual([[17.38, 78.48], [17.388, 78.485], [17.39, 78.49]]);
  });

  it('falls back to V1 start and end coordinates', () => {
    expect(getSegmentPositions(segment)).toEqual([[17.38, 78.48], [17.39, 78.49]]);
  });

  it('places event markers halfway along the full geometry', () => {
    expect(getSegmentMidpoint({
      ...segment,
      geometry: { type: 'LineString', coordinates: [[78.48, 17.38], [78.48, 17.4], [78.5, 17.4]] },
    })).toEqual([17.4, 78.48]);
  });
});
