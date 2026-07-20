import React from 'react';
import { MapContainer, Polyline, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { MapLegend } from '../../components/map/MapLegend';
import { SegmentPopup } from '../../components/map/SegmentPopup';
import { fetchSegments } from '../../services/api/segmentApi';
import { useQuery } from '@tanstack/react-query';

// Fix leafet marker icon issue in React
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const getEventColorCode = (type?: string) => {
  switch (type) {
    case 'Construction': return '#d29922'; // warning
    case 'Flood': return '#2f81f7';        // primary
    case 'Accident': return '#f85149';     // danger
    case 'Diversion': return '#8957e5';    // accent
    default: return '#238636';             // success
  }
};

const TrafficMap: React.FC = () => {
  const { data: segments, isLoading, isError } = useQuery({
    queryKey: ['segments'],
    queryFn: fetchSegments
  });

  const renderRealSegments = () => {
    if (!segments) return null;
    return segments.map((seg) => {
      const positions: [number, number][] = [
        [seg.start_lat, seg.start_lon],
        [seg.end_lat, seg.end_lon]
      ];

      return (
        <Polyline 
          key={seg.segment_id}
          positions={positions} 
          pathOptions={{ 
            color: getEventColorCode(seg.type), 
            weight: 6,
            opacity: 0.8 
          }}
        >
          <Popup className="bg-surface border-border">
            <SegmentPopup segment={seg} />
          </Popup>
        </Polyline>
      );
    });
  };

  return (
    <PageContainer className="h-[calc(100vh-100px)] flex flex-col">
      <PageHeader 
        title="Traffic Map" 
        description="Synthetic Road Network & Vehicle Trajectory Playback" 
      />

      <div className="flex-1 rounded-lg overflow-hidden border border-border relative bg-[#0d1117]">
        {isLoading ? (
          <div className="absolute inset-0 flex items-center justify-center bg-surface/50 text-textSecondary z-50">
            Loading road network...
          </div>
        ) : isError ? (
          <div className="absolute inset-0 flex items-center justify-center bg-danger/10 text-danger z-50 font-medium">
            Failed to load road network. Backend may be offline.
          </div>
        ) : segments && segments.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center bg-surface/50 text-textSecondary z-50">
            No road network available.
          </div>
        ) : (() => {
          const centerLat = segments!.reduce((sum, seg) => sum + seg.start_lat, 0) / segments!.length;
          const centerLon = segments!.reduce((sum, seg) => sum + seg.start_lon, 0) / segments!.length;
          
          return (
            <MapContainer 
              center={[centerLat, centerLon]} 
              zoom={12} 
              className="w-full h-full bg-[#0d1117]"
              zoomControl={false}
            >
              {/* The project uses real OSM coordinates, so we drop CRS.Simple */}
              {renderRealSegments()}
              
              <div className="absolute top-4 right-4 z-[400]">
                <MapLegend />
              </div>
            </MapContainer>
          );
        })()}
      </div>
    </PageContainer>
  );
};

export default TrafficMap;
