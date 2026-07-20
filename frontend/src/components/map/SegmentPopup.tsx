import React from 'react';
import { ShieldCheck, AlertCircle } from 'lucide-react';


export interface SegmentData {
  segment_id: string;
  region_id: string;
  type?: 'Normal' | 'Construction' | 'Flood' | 'Accident' | 'Diversion';
  base_speed?: number;
  base_density?: number;
  start_lat: number;
  start_lon: number;
  end_lat: number;
  end_lon: number;
  max_speed_kmph?: number;
}

interface SegmentPopupProps {
  segment: SegmentData;
}

export const SegmentPopup: React.FC<SegmentPopupProps> = ({ segment }) => {
  const isEvent = segment.type && segment.type !== 'Normal';
  
  return (
    <div className="w-48 text-textPrimary">
      <div className="font-semibold mb-2 text-white border-b border-border pb-1">
        Segment {segment.segment_id}
      </div>
      <div className="space-y-1 text-sm">
        <div className="flex justify-between">
          <span className="text-textSecondary">Region:</span>
          <span className="font-medium">{segment.region_id}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-textSecondary">Base Speed:</span>
          <span className="font-medium">{segment.base_speed || 40} km/h</span>
        </div>
        <div className="flex justify-between items-center mt-2 pt-2 border-t border-border">
          <span className="text-textSecondary">Status:</span>
          {isEvent ? (
            <span className="flex items-center gap-1 text-danger font-medium text-xs">
              <AlertCircle className="w-3 h-3" /> {segment.type}
            </span>
          ) : (
            <span className="flex items-center gap-1 text-success font-medium text-xs">
              <ShieldCheck className="w-3 h-3" /> Normal
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
