import React from 'react';
import { Network } from 'lucide-react';
import { twMerge } from 'tailwind-merge';
import { clsx } from 'clsx';

export const LoadingScreen: React.FC<{ fullScreen?: boolean, message?: string, className?: string }> = ({ 
  fullScreen = false, 
  message = "Loading...", 
  className 
}) => {
  return (
    <div className={twMerge(clsx(
      'flex flex-col items-center justify-center text-textSecondary',
      fullScreen ? 'fixed inset-0 bg-background z-50' : 'h-full min-h-[400px]',
      className
    ))}>
      <div className="relative">
        <Network className="w-12 h-12 text-primary opacity-50" />
        <div className="absolute inset-0 border-t-2 border-primary rounded-full animate-spin"></div>
      </div>
      <p className="mt-4 text-sm font-medium tracking-wide animate-pulse">{message}</p>
    </div>
  );
};
