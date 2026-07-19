import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface StatusBadgeProps {
  status: 'active' | 'stable' | 'error' | 'warning' | 'neutral';
  text: string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, text, className }) => {
  const getStatusStyles = () => {
    switch (status) {
      case 'active':
        return 'bg-primary/10 text-primary border-primary/20';
      case 'stable':
        return 'bg-success/10 text-success border-success/20';
      case 'error':
        return 'bg-danger/10 text-danger border-danger/20';
      case 'warning':
        return 'bg-warning/10 text-warning border-warning/20';
      case 'neutral':
      default:
        return 'bg-surfaceHover text-textSecondary border-border';
    }
  };

  return (
    <span className={twMerge(clsx('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border', getStatusStyles(), className))}>
      {text}
    </span>
  );
};
