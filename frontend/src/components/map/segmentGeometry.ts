import type { SegmentData } from '../../services/api/liveMapApi';

type LatLngTuple = [number, number];

export const getSegmentPositions = (segment: SegmentData): LatLngTuple[] => {
  if (segment.geometry?.type === 'LineString' && segment.geometry.coordinates.length >= 2) {
    return segment.geometry.coordinates.map(([lon, lat]) => [lat, lon] as [number, number]);
  }
  return [[segment.start_lat, segment.start_lon], [segment.end_lat, segment.end_lon]];
};

export const getSegmentMidpoint = (segment: SegmentData): LatLngTuple => {
  const positions = getSegmentPositions(segment);
  const lengths = positions.slice(1).map(([lat, lon], index) => {
    const [previousLat, previousLon] = positions[index];
    return Math.hypot(lat - previousLat, lon - previousLon);
  });
  const totalLength = lengths.reduce((sum, length) => sum + length, 0);
  if (totalLength === 0) return positions[Math.floor(positions.length / 2)];

  const target = totalLength / 2;
  let traversed = 0;
  for (let index = 0; index < lengths.length; index += 1) {
    if (traversed + lengths[index] >= target) {
      const ratio = (target - traversed) / lengths[index];
      const [startLat, startLon] = positions[index];
      const [endLat, endLon] = positions[index + 1];
      return [startLat + (endLat - startLat) * ratio, startLon + (endLon - startLon) * ratio];
    }
    traversed += lengths[index];
  }
  return positions[positions.length - 1];
};
