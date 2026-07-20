import React from 'react';
import { twMerge } from 'tailwind-merge';
import { clsx } from 'clsx';

export const SkeletonLoader: React.FC<{ className?: string }> = ({ className }) => {
  return (
    <div className={twMerge(clsx('animate-pulse bg-surfaceHover rounded-md', className))}></div>
  );
};

export const CardSkeleton: React.FC = () => {
  return (
    <div className="bg-surface border border-border rounded-lg p-5 w-full">
      <SkeletonLoader className="h-4 w-1/3 mb-6" />
      <div className="space-y-3">
        <SkeletonLoader className="h-10 w-full" />
        <SkeletonLoader className="h-10 w-full" />
        <SkeletonLoader className="h-10 w-3/4" />
      </div>
    </div>
  );
};
