import type { LiveVehicle } from '../../services/api/liveMapApi';

export interface VehicleTransition {
  fromLat: number;
  fromLon: number;
  toLat: number;
  toLon: number;
  startedAt: number;
  durationMs: number;
}

export interface VehicleTarget {
  lat: number;
  lon: number;
  timestampMs: number;
}

export const interpolateVehiclePosition = (transition: VehicleTransition, now: number): [number, number] => {
  const progress = Math.min(1, Math.max(0, (now - transition.startedAt) / transition.durationMs));
  const eased = 1 - Math.pow(1 - progress, 3);
  return [
    transition.fromLat + (transition.toLat - transition.fromLat) * eased,
    transition.fromLon + (transition.toLon - transition.fromLon) * eased,
  ];
};

export const deduplicateVehicles = (vehicles: LiveVehicle[]): LiveVehicle[] => {
  const latest = new Map<string, LiveVehicle>();
  for (const vehicle of vehicles) {
    const current = latest.get(vehicle.vehicle_id);
    if (!current || Date.parse(vehicle.timestamp) >= Date.parse(current.timestamp)) latest.set(vehicle.vehicle_id, vehicle);
  }
  return [...latest.values()];
};

export const vehicleTone = (vehicle: LiveVehicle): 'flowing' | 'slow' | 'dense' =>
  vehicle.speed_kmph < 8 ? 'dense' : vehicle.speed_kmph < 22 ? 'slow' : 'flowing';
