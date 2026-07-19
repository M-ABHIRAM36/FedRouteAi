import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
}

export const PageContainer: React.FC<PageContainerProps> = ({ children, className }) => {
  return (
    <div className={twMerge(clsx('max-w-7xl mx-auto space-y-6', className))}>
      {children}
    </div>
  );
};
