import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface ClientCardProps {
  region: string;
  quality: number;
  ema: number;
  weight: number;
  samples: number;
  gatePassed: boolean;
  className?: string;
}

export const ClientCard: React.FC<ClientCardProps> = ({ 
  region, quality, ema, weight, samples, gatePassed, className 
}) => {
  return (
    <div className={twMerge(clsx('bg-surfaceHover border border-border rounded-lg p-5 flex flex-col', className))}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">{region}</h3>
        <span className={clsx('px-2 py-0.5 rounded text-xs font-medium border', 
          gatePassed ? 'bg-success/10 text-success border-success/20' : 'bg-danger/10 text-danger border-danger/20'
        )}>
          {gatePassed ? 'Gate: PASS' : 'Gate: FAIL'}
        </span>
      </div>
      
      <div className="grid grid-cols-2 gap-y-4 gap-x-2">
        <div>
          <div className="text-xs text-textSecondary mb-1">Quality (q_k)</div>
          <div className="text-sm font-medium text-textPrimary">{quality.toFixed(4)}</div>
        </div>
        <div>
          <div className="text-xs text-textSecondary mb-1">EMA (ρ_k)</div>
          <div className="text-sm font-medium text-textPrimary">{ema.toFixed(4)}</div>
        </div>
        <div>
          <div className="text-xs text-textSecondary mb-1">Adaptive Wt (w_k)</div>
          <div className="text-sm font-medium text-primary">{weight.toFixed(4)}</div>
        </div>
        <div>
          <div className="text-xs text-textSecondary mb-1">Samples (n_k)</div>
          <div className="text-sm font-medium text-textPrimary">{samples}</div>
        </div>
      </div>
    </div>
  );
};
