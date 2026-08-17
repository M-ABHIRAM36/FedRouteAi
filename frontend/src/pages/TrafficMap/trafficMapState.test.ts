import { describe, expect, it } from 'vitest';
import { connectionStatus, snapshotAgeSeconds } from './trafficMapState';

describe('live receipt freshness', () => {
  it('ignores historical simulation time when a snapshot was just received', () => {
    const now = Date.parse('2026-08-17T19:27:00Z');
    const receivedAt = Date.parse('2026-08-17T19:27:00Z');

    expect(snapshotAgeSeconds(receivedAt, now)).toBe(0);
    expect(connectionStatus(true, receivedAt, false, now)).toBe('LIVE');
  });

  it('keeps a snapshot received 20 seconds ago delayed rather than stale', () => {
    const now = 1_000_000;
    expect(snapshotAgeSeconds(now - 20_000, now)).toBe(20);
    expect(connectionStatus(true, now - 20_000, false, now)).toBe('DELAYED');
  });

  it('marks a session stale only after the client receipt threshold', () => {
    const now = 1_000_000;
    expect(connectionStatus(true, now - 150_001, false, now)).toBe('STALE');
    expect(connectionStatus(true, now - 150_001, true, now)).toBe('STALE');
  });

  it('keeps pause distinct from stale and represents startup correctly', () => {
    const now = 1_000_000;
    expect(connectionStatus(false, undefined, false, now)).toBe('PAUSED');
    expect(connectionStatus(true, undefined, false, now)).toBe('CONNECTING');
    expect(connectionStatus(true, undefined, true, now)).toBe('OFFLINE');
  });
});
