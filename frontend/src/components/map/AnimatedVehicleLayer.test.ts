import { describe, expect, it } from 'vitest';
import type { LiveVehicle } from '../../services/api/liveMapApi';
import { deduplicateVehicles, interpolateVehiclePosition, vehicleTone } from './vehicleAnimation';

const vehicle = (vehicleId: string, speedKmph = 30): LiveVehicle => ({
  vehicle_id: vehicleId,
  vehicle_type: 'car',
  segment_id: 'SEG_1',
  region_id: 'REGION_01',
  lat: 17.38,
  lon: 78.48,
  speed_kmph: speedKmph,
  heading_deg: 90,
  timestamp: '2026-08-17T10:00:00Z',
});

describe('vehicle animation helpers', () => {
  it('interpolates between authoritative endpoints and clamps elapsed time', () => {
    const transition = { fromLat: 10, fromLon: 20, toLat: 14, toLon: 28, startedAt: 1000, durationMs: 1000 };

    expect(interpolateVehiclePosition(transition, 500)).toEqual([10, 20]);
    expect(interpolateVehiclePosition(transition, 1500)).toEqual([13.5, 27]);
    expect(interpolateVehiclePosition(transition, 2500)).toEqual([14, 28]);
  });

  it('keeps only the latest observation for each vehicle ID', () => {
    const original = vehicle('VEH_1', 10);
    const latest = { ...original, speed_kmph: 40 };

    expect(deduplicateVehicles([original, vehicle('VEH_2'), latest])).toEqual([latest, vehicle('VEH_2')]);
  });

  it('classifies vehicle markers from physical speed telemetry', () => {
    expect(vehicleTone(vehicle('VEH_1', 7))).toBe('dense');
    expect(vehicleTone(vehicle('VEH_2', 21))).toBe('slow');
    expect(vehicleTone(vehicle('VEH_3', 22))).toBe('flowing');
  });
});
