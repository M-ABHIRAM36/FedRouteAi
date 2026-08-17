import type { LiveVehicle } from '../../services/api/liveMapApi';

export interface VehicleTransition {
  fromLat: number;
  fromLon: number;
  toLat: number;
  toLon: number;
  startedAt: number;
  durationMs: number;
}

export const interpolateVehiclePosition = (transition: VehicleTransition, now: number): [number, number] => {
  const progress = Math.min(1, Math.max(0, (now - transition.startedAt) / transition.durationMs));
  const eased = 1 - Math.pow(1 - progress, 3);
  return [
    transition.fromLat + (transition.toLat - transition.fromLat) * eased,
    transition.fromLon + (transition.toLon - transition.fromLon) * eased,
  ];
};

export const deduplicateVehicles = (vehicles: LiveVehicle[]): LiveVehicle[] =>
  [...new Map(vehicles.map((vehicle) => [vehicle.vehicle_id, vehicle])).values()];

export const vehicleTone = (vehicle: LiveVehicle): 'flowing' | 'slow' | 'dense' =>
  vehicle.speed_kmph < 8 ? 'dense' : vehicle.speed_kmph < 22 ? 'slow' : 'flowing';
