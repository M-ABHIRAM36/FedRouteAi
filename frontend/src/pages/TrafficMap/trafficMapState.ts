import type { LiveMapSnapshot } from '../../services/api/liveMapApi';

export type ConnectionStatus = 'CONNECTING' | 'LIVE' | 'DELAYED' | 'STALE' | 'PAUSED' | 'OFFLINE';

export const snapshotAgeSeconds = (snapshot: LiveMapSnapshot | undefined, now: number): number => {
  if (!snapshot) return Infinity;
  const serverOffset = Date.parse(snapshot.server_time) - Date.parse(snapshot.received_at);
  return Math.max(0, (now - Date.parse(snapshot.received_at) + serverOffset) / 1000);
};

export const connectionStatus = (liveMode: boolean, snapshot: LiveMapSnapshot | undefined, fetching: boolean, hasError: boolean, now: number): ConnectionStatus => {
  if (!liveMode) return 'PAUSED';
  if (!snapshot) return hasError ? 'OFFLINE' : 'CONNECTING';
  const age = snapshotAgeSeconds(snapshot, now);
  const expected = Math.max(snapshot.poll_interval_seconds, 1);
  if (hasError || age > snapshot.stale_after_seconds) return 'STALE';
  if (age > expected * 1.5) return 'DELAYED';
  return fetching && age > expected ? 'DELAYED' : 'LIVE';
};
