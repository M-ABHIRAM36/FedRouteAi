export type ConnectionStatus = 'CONNECTING' | 'LIVE' | 'DELAYED' | 'STALE' | 'PAUSED' | 'OFFLINE';

export const LIVE_RECEIPT_WINDOW_SECONDS = 15;
export const STALE_RECEIPT_WINDOW_SECONDS = 150;

export const snapshotAgeSeconds = (lastSnapshotReceivedAt: number | undefined, now: number): number =>
  lastSnapshotReceivedAt == null ? Infinity : Math.max(0, (now - lastSnapshotReceivedAt) / 1000);

export const connectionStatus = (liveMode: boolean, lastSnapshotReceivedAt: number | undefined, hasError: boolean, now: number): ConnectionStatus => {
  if (!liveMode) return 'PAUSED';
  if (lastSnapshotReceivedAt == null) return hasError ? 'OFFLINE' : 'CONNECTING';
  const age = snapshotAgeSeconds(lastSnapshotReceivedAt, now);
  if (age > STALE_RECEIPT_WINDOW_SECONDS) return 'STALE';
  if (age > LIVE_RECEIPT_WINDOW_SECONDS) return 'DELAYED';
  return 'LIVE';
};
