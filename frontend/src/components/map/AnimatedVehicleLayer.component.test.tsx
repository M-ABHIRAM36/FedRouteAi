import { forwardRef, useImperativeHandle } from 'react';
import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LiveVehicle } from '../../services/api/liveMapApi';
import { AnimatedVehicleLayer } from './AnimatedVehicleLayer';

const setLatLng = vi.fn();

vi.mock('react-leaflet', () => ({
  CircleMarker: forwardRef(({ children }: { children?: React.ReactNode }, ref) => {
    useImperativeHandle(ref, () => ({ setLatLng, getLatLng: () => ({ lat: 17.38, lng: 78.48 }) }));
    return <div data-testid="vehicle-marker">{children}</div>;
  }),
  Popup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const vehicle = (vehicleId: string, lat = 17.38): LiveVehicle => ({
  vehicle_id: vehicleId,
  vehicle_type: 'car',
  segment_id: 'SEG_1',
  region_id: 'REGION_01',
  lat,
  lon: 78.48,
  speed_kmph: 30,
  heading_deg: 90,
  timestamp: '2026-08-17T10:00:00Z',
});

describe('AnimatedVehicleLayer', () => {
  let frameCallback: FrameRequestCallback | undefined;

  beforeEach(() => {
    frameCallback = undefined;
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
      frameCallback = callback;
      return 17;
    }));
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    setLatLng.mockClear();
  });

  afterEach(() => vi.unstubAllGlobals());

  it('deduplicates markers and removes IDs absent from the next snapshot', () => {
    const view = render(<AnimatedVehicleLayer vehicles={[vehicle('VEH_1'), vehicle('VEH_1'), vehicle('VEH_2')]} onSelect={vi.fn()} />);
    expect(screen.getAllByTestId('vehicle-marker')).toHaveLength(2);

    view.rerender(<AnimatedVehicleLayer vehicles={[vehicle('VEH_2')]} onSelect={vi.fn()} />);
    expect(screen.getAllByTestId('vehicle-marker')).toHaveLength(1);
    expect(screen.queryByText('VEH_1')).not.toBeInTheDocument();
  });

  it('moves markers in one shared frame loop and cancels it when paused', () => {
    const view = render(<AnimatedVehicleLayer vehicles={[vehicle('VEH_1')]} onSelect={vi.fn()} />);
    view.rerender(<AnimatedVehicleLayer vehicles={[vehicle('VEH_1', 17.381)]} onSelect={vi.fn()} />);

    act(() => frameCallback?.(performance.now() + 900));
    expect(setLatLng).toHaveBeenCalledTimes(1);

    view.rerender(<AnimatedVehicleLayer vehicles={[vehicle('VEH_1', 17.381)]} paused onSelect={vi.fn()} />);
    expect(cancelAnimationFrame).toHaveBeenCalledWith(17);
  });

  it('cancels animation frames on unmount', () => {
    const view = render(<AnimatedVehicleLayer vehicles={[vehicle('VEH_1')]} onSelect={vi.fn()} />);
    view.unmount();
    expect(cancelAnimationFrame).toHaveBeenCalledWith(17);
  });
});
