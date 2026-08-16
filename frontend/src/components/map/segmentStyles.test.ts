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

  it.each(['congestion', 'construction', 'accident', 'flood', 'diversion', 'road_damage'])('maps %s telemetry to its semantic style', (event) => {
    expect(getSegmentStyle(state(event)).status).toBe(event);
  });

  it('gives unavailable roads blocked precedence', () => {
    expect(getSegmentStyle(state('normal', false)).status).toBe('blocked');
  });
});
