import React, { useState } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { ChevronDown, Radio, WifiOff } from 'lucide-react';
import { predictionLegend, telemetryLegend } from './segmentStyles';

export const MapLegend: React.FC<{ className?: string }> = ({ className }) => {
  const [expanded, setExpanded] = useState(true);
  return (
    <div className={twMerge(clsx('pointer-events-auto w-52 border border-border bg-surface/95 shadow-xl', className))}>
      <button type="button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded} className="flex w-full items-center justify-between px-3 py-2 text-xs font-semibold uppercase text-textPrimary focus-visible:outline-2 focus-visible:outline-primary">
        Map legend <ChevronDown className={clsx('h-3.5 w-3.5 transition-transform', expanded && 'rotate-180')} />
      </button>
      {expanded && <div className="max-h-[52vh] space-y-3 overflow-y-auto border-t border-border p-3">
        <LegendSection title="Model prediction" items={predictionLegend} />
        <LegendSection title="Telemetry" items={telemetryLegend} />
        <div><LegendTitle>Status</LegendTitle><div className="space-y-1.5"><StatusItem icon={<Radio className="h-3 w-3 text-success" />} label="Live" /><StatusItem icon={<Radio className="h-3 w-3 text-warning" />} label="Stale" /><StatusItem icon={<WifiOff className="h-3 w-3 text-textSecondary" />} label="No data" /></div></div>
        <div className="border-t border-border pt-2 text-[10px] leading-4 text-textSecondary">Road colors show model output when available. Telemetry is a separate optional layer.</div>
      </div>}
    </div>
  );
};

const LegendTitle = ({ children }: { children: React.ReactNode }) => <div className="mb-1.5 text-[10px] font-semibold uppercase text-textSecondary">{children}</div>;

const LegendSection = ({ title, items }: { title: string; items: typeof predictionLegend }) => <div><LegendTitle>{title}</LegendTitle><div className="space-y-1.5">{items.map((item) => <div key={item.status} className="flex items-center gap-2"><span className="h-1.5 w-6" style={{ backgroundColor: item.color }} /><span className="text-xs text-textPrimary">{item.label}</span></div>)}</div></div>;

const StatusItem = ({ icon, label }: { icon: React.ReactNode; label: string }) => <div className="flex items-center gap-2 text-xs text-textPrimary">{icon}{label}</div>;
