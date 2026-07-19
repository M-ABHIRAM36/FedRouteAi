import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface FigureViewerProps {
  src: string;
  alt: string;
  caption?: string;
  observation?: string;
  className?: string;
}

export const FigureViewer: React.FC<FigureViewerProps> = ({ src, alt, caption, observation, className }) => {
  return (
    <div className={twMerge(clsx('bg-surface border border-border rounded-lg overflow-hidden flex flex-col', className))}>
      <div className="bg-white/5 p-4 flex justify-center items-center border-b border-border">
        {/* Placeholder image rendering logic since we are assuming local static files /results */}
        <img src={src} alt={alt} className="max-w-full h-auto max-h-[400px] object-contain rounded" />
      </div>
      <div className="p-4">
        {caption && <h4 className="text-sm font-semibold text-white mb-2">{caption}</h4>}
        {observation && <p className="text-sm text-textSecondary">{observation}</p>}
      </div>
    </div>
  );
};
