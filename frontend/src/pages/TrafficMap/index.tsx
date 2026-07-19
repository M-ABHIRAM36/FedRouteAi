import React, { useEffect, useState } from 'react';
import { MapContainer, Polyline, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { MapLegend } from '../../components/map/MapLegend';
import { SegmentPopup, type SegmentData } from '../../components/map/SegmentPopup';
import { fetchSegments } from '../../services/api/segmentApi';

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
  const [segments, setSegments] = useState<SegmentData[]>([]);

  useEffect(() => {
    const loadData = async () => {
      const data = await fetchSegments();
      setSegments(data);
    };
    loadData();
  }, []);

  // For visual placeholder purposes, we map abstract segments into a grid network on CRS.Simple
  const renderMockGrid = () => {
    return segments.map((seg, idx) => {
      // Create a deterministic pseudo-coordinate based on the string ID or index
      // E.g. MOCK_2_3 -> x:200, y:300
      let x = (idx % 5) * 100;
      let y = Math.floor(idx / 5) * 100;
      
      const positions: [number, number][] = [
        [y, x],
        [y, x + 80]
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
        <MapContainer 
          center={[200, 200]} 
          zoom={1} 
          crs={L.CRS.Simple}
          className="w-full h-full bg-[#0d1117]"
          zoomControl={false}
        >
          {/* We do NOT use a tile layer since this is a synthetic CRS.Simple plane */}
          {renderMockGrid()}
          
          <div className="absolute top-4 right-4 z-[400]">
            <MapLegend />
          </div>
        </MapContainer>
      </div>
    </PageContainer>
  );
};

export default TrafficMap;
