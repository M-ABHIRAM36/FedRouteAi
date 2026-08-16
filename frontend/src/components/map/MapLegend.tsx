import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { segmentLegend } from './segmentStyles';

export const MapLegend: React.FC<{ className?: string }> = ({ className }) => {
  return (
    <div className={twMerge(clsx('bg-surface/90 backdrop-blur-sm border border-border rounded-lg p-4 shadow-lg pointer-events-auto', className))}>
      <h4 className="text-xs font-semibold text-textPrimary mb-3 uppercase tracking-wider">Map Legend</h4>
      <div className="space-y-2">
        {segmentLegend.map((item) => (
          <div key={item.label} className="flex items-center gap-3">
            <span className={clsx('h-1.5 w-7 rounded-full border', item.status === 'unknown' && 'border-dashed')} style={{ backgroundColor: item.color, borderColor: item.color }} />
            <span className="text-sm text-textSecondary font-medium">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
