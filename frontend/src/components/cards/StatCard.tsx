import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: string;
  trendUp?: boolean;
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({ title, value, icon: Icon, trend, trendUp, className }) => {
  return (
    <div className={twMerge(clsx('bg-surface border border-border rounded-lg p-5 flex flex-col', className))}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-textSecondary">{title}</h3>
        <div className="p-2 bg-surfaceHover rounded-md text-textPrimary">
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <div className="mt-auto">
        <div className="text-2xl font-bold text-white">{value}</div>
        {trend && (
          <div className="mt-2 text-xs">
            <span className={clsx('font-medium', trendUp ? 'text-success' : 'text-danger')}>
              {trend}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
