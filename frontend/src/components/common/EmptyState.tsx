import React from 'react';
import { Database } from 'lucide-react';
import { twMerge } from 'tailwind-merge';
import { clsx } from 'clsx';

export const EmptyState: React.FC<{ 
  title?: string; 
  description?: string; 
  icon?: React.ElementType;
  className?: string; 
}> = ({ 
  title = "No Data Available", 
  description = "There is currently no data to display here.", 
  icon: Icon = Database,
  className 
}) => {
  return (
    <div className={twMerge(clsx('flex flex-col items-center justify-center p-8 text-center bg-surface border border-border rounded-lg', className))}>
      <div className="w-12 h-12 bg-surfaceHover rounded-full flex items-center justify-center mb-4 text-textSecondary">
        <Icon className="w-6 h-6 opacity-80" />
      </div>
      <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
      <p className="text-xs text-textSecondary max-w-sm">{description}</p>
    </div>
  );
};
