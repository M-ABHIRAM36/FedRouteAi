import { describe, expect, it } from 'vitest';
import { getSegmentStyle } from './segmentStyles';
import type { LiveSegmentState } from '../../services/api/liveMapApi';

const state = (current_event: string, available = true): LiveSegmentState => ({
  segment_id: 'SEG_1', region_id: 'REGION_01', latest_timestamp: '2026-08-17T10:00:00',
  vehicle_count: 4, average_speed_kmph: 25, density: 4, current_event, available,
  last_updated: '2026-08-17T10:00:01',
});

describe('getSegmentStyle', () => {
  it('shows missing backend state as unknown, not normal', () => {
    expect(getSegmentStyle().status).toBe('unknown');
  });

  it.each(['congestion', 'construction', 'accident', 'flood', 'diversion', 'road_damage', 'road_block'])('maps %s model output to its semantic style', (event) => {
    expect(getSegmentStyle({ ...state('normal'), predicted_event: event }).status).toBe(event);
  });

  it('keeps model prediction precedence over separate availability telemetry', () => {
    expect(getSegmentStyle({ ...state('normal', false), predicted_event: 'accident' }).status).toBe('accident');
  });

  it('prefers a model prediction over the scenario telemetry label', () => {
    expect(getSegmentStyle({ ...state('accident'), predicted_event: 'construction' }).status).toBe('construction');
  });

  it('styles unclassified physical telemetry without using the scenario label', () => {
    expect(getSegmentStyle(state('accident'), 60).status).toBe('telemetry_slow');
    expect(getSegmentStyle({ ...state('flood'), density: 25 }, 60).status).toBe('telemetry_dense');
    expect(getSegmentStyle({ ...state('construction'), average_speed_kmph: 50 }, 60).status).toBe('telemetry_clear');
  });
});
