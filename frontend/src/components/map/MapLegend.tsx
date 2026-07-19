import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface LegendItem {
  label: string;
  colorClass: string;
}

const legendItems: LegendItem[] = [
  { label: 'Normal', colorClass: 'bg-success border-success/30' },
  { label: 'Construction', colorClass: 'bg-warning border-warning/30' },
  { label: 'Flood', colorClass: 'bg-primary border-primary/30' },
  { label: 'Accident', colorClass: 'bg-danger border-danger/30' },
  { label: 'Diversion', colorClass: 'bg-accent border-accent/30' },
];

export const MapLegend: React.FC<{ className?: string }> = ({ className }) => {
  return (
    <div className={twMerge(clsx('bg-surface/90 backdrop-blur-sm border border-border rounded-lg p-4 shadow-lg pointer-events-auto', className))}>
      <h4 className="text-xs font-semibold text-textPrimary mb-3 uppercase tracking-wider">Map Legend</h4>
      <div className="space-y-2">
        {legendItems.map((item) => (
          <div key={item.label} className="flex items-center gap-3">
            <span className={clsx('w-3 h-3 rounded-full border', item.colorClass)}></span>
            <span className="text-sm text-textSecondary font-medium">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
