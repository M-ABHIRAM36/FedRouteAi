import React from 'react';
import { AlertOctagon, RefreshCw } from 'lucide-react';
import { twMerge } from 'tailwind-merge';
import { clsx } from 'clsx';

export const ErrorScreen: React.FC<{ 
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}> = ({ 
  title = "Something went wrong", 
  message = "An error occurred while loading this component.", 
  onRetry,
  className 
}) => {
  return (
    <div className={twMerge(clsx('flex flex-col items-center justify-center p-8 text-center bg-danger/5 border border-danger/20 rounded-lg', className))}>
      <div className="w-12 h-12 bg-danger/10 rounded-full flex items-center justify-center mb-4 text-danger">
        <AlertOctagon className="w-6 h-6" />
      </div>
      <h3 className="text-sm font-semibold text-danger mb-1">{title}</h3>
      <p className="text-xs text-danger/80 max-w-sm mb-4">{message}</p>
      
      {onRetry && (
        <button 
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 bg-danger/10 hover:bg-danger/20 text-danger rounded-md text-xs font-medium border border-danger/20 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </button>
      )}
    </div>
  );
};
