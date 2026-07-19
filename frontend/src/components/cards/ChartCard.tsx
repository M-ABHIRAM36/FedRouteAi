import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface ChartCardProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export const ChartCard: React.FC<ChartCardProps> = ({ title, description, children, className }) => {
  return (
    <div className={twMerge(clsx('bg-surface border border-border rounded-lg p-5 flex flex-col', className))}>
      <div className="mb-4">
        <h3 className="text-sm font-medium text-textPrimary">{title}</h3>
        {description && <p className="text-xs text-textSecondary mt-1">{description}</p>}
      </div>
      <div className="flex-1 min-h-[300px] w-full relative">
        {children}
      </div>
    </div>
  );
};
