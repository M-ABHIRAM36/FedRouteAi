import { memo, useEffect, useMemo, useRef } from 'react';
import type { CircleMarker as LeafletCircleMarker } from 'leaflet';
import { CircleMarker, Popup } from 'react-leaflet';
import type { LiveVehicle } from '../../services/api/liveMapApi';
import { deduplicateVehicles, interpolateVehiclePosition, vehicleTone, type VehicleTransition } from './vehicleAnimation';

const INTERPOLATION_MS = 1800;
const MAX_INTERPOLATION_DISTANCE_DEGREES = 0.02;

interface AnimatedVehicleLayerProps {
  vehicles: LiveVehicle[];
  selectedVehicleId?: string;
  paused?: boolean;
  onSelect: (vehicleId: string) => void;
}

export const AnimatedVehicleLayer = ({ vehicles, selectedVehicleId, paused = false, onSelect }: AnimatedVehicleLayerProps) => {
  const uniqueVehicles = useMemo(() => deduplicateVehicles(vehicles), [vehicles]);
  const markerRefs = useRef(new Map<string, LeafletCircleMarker>());
  const transitions = useRef(new Map<string, VehicleTransition>());
  const previousTargets = useRef(new Map<string, [number, number]>());
  const frame = useRef<number | undefined>(undefined);

  useEffect(() => {
    const now = performance.now();
    const active = new Set(uniqueVehicles.map((vehicle) => vehicle.vehicle_id));
    for (const key of previousTargets.current.keys()) {
      if (!active.has(key)) {
        previousTargets.current.delete(key);
        transitions.current.delete(key);
        markerRefs.current.delete(key);
      }
    }
    for (const vehicle of uniqueVehicles) {
      const target: [number, number] = [vehicle.lat, vehicle.lon];
      const previous = previousTargets.current.get(vehicle.vehicle_id);
      if (previous && (previous[0] !== target[0] || previous[1] !== target[1])) {
        const markerPosition = markerRefs.current.get(vehicle.vehicle_id)?.getLatLng();
        const from: [number, number] = markerPosition ? [markerPosition.lat, markerPosition.lng] : previous;
        const distance = Math.hypot(target[0] - from[0], target[1] - from[1]);
        transitions.current.set(vehicle.vehicle_id, {
          fromLat: from[0], fromLon: from[1], toLat: target[0], toLon: target[1], startedAt: now,
          durationMs: distance > MAX_INTERPOLATION_DISTANCE_DEGREES ? 1 : INTERPOLATION_MS,
        });
      }
      previousTargets.current.set(vehicle.vehicle_id, target);
    }
  }, [uniqueVehicles]);

  useEffect(() => {
    const animate = (now: number) => {
      for (const [vehicleId, transition] of transitions.current) {
        markerRefs.current.get(vehicleId)?.setLatLng(interpolateVehiclePosition(transition, now));
        if (now >= transition.startedAt + transition.durationMs) transitions.current.delete(vehicleId);
      }
      frame.current = requestAnimationFrame(animate);
    };
    const updateLoop = () => {
      if (frame.current != null) cancelAnimationFrame(frame.current);
      frame.current = undefined;
      if (!paused && document.visibilityState !== 'hidden') frame.current = requestAnimationFrame(animate);
    };
    document.addEventListener('visibilitychange', updateLoop);
    updateLoop();
    return () => {
      document.removeEventListener('visibilitychange', updateLoop);
      if (frame.current != null) cancelAnimationFrame(frame.current);
    };
  }, [paused]);

  return uniqueVehicles.map((vehicle) => <VehicleMarker
    key={vehicle.vehicle_id}
    vehicle={vehicle}
    selected={selectedVehicleId === vehicle.vehicle_id}
    setMarker={(marker) => { if (marker) markerRefs.current.set(vehicle.vehicle_id, marker); else markerRefs.current.delete(vehicle.vehicle_id); }}
    onSelect={onSelect}
  />);
};

const VehicleMarker = memo(({ vehicle, selected, setMarker, onSelect }: {
  vehicle: LiveVehicle;
  selected: boolean;
  setMarker: (marker: LeafletCircleMarker | null) => void;
  onSelect: (vehicleId: string) => void;
}) => {
  const initialCenter = useRef<[number, number]>([vehicle.lat, vehicle.lon]);
  const tone = vehicleTone(vehicle);
  const color = tone === 'dense' ? '#fb7185' : tone === 'slow' ? '#fbbf24' : '#67e8f9';
  return <CircleMarker
      key={vehicle.vehicle_id}
      ref={setMarker}
      center={initialCenter.current}
      radius={selected ? 5 : 3}
      pathOptions={{ color, fillColor: color, fillOpacity: 0.8, weight: selected ? 2 : 1 }}
      eventHandlers={{ click: () => onSelect(vehicle.vehicle_id) }}
    ><Popup><VehicleDetails vehicle={vehicle} tone={tone} /></Popup></CircleMarker>;
});

const VehicleDetails = ({ vehicle, tone }: { vehicle: LiveVehicle; tone: string }) => <div className="w-48 text-xs text-textPrimary"><div className="mb-2 border-b border-border pb-2 font-semibold text-white">{vehicle.vehicle_id}</div><div className="space-y-1"><div className="flex justify-between"><span className="text-textSecondary">Telemetry</span><span className="capitalize">{tone}</span></div><div className="flex justify-between"><span className="text-textSecondary">Speed</span><span>{vehicle.speed_kmph.toFixed(1)} km/h</span></div><div className="flex justify-between"><span className="text-textSecondary">Segment</span><span>{vehicle.segment_id}</span></div><div className="flex justify-between"><span className="text-textSecondary">Updated</span><span>{new Date(vehicle.timestamp).toLocaleTimeString()}</span></div></div></div>;
