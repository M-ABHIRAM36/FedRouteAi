import React from 'react';
import { AlertCircle, Clock } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface EventLog {
  id: string;
  roadId: string;
  type: string;
  timeAgo: string;
}

interface EventCardProps {
  event: EventLog;
  className?: string;
}

const getEventColor = (type: string) => {
  switch (type.toLowerCase()) {
    case 'construction': return 'text-warning border-warning/20 bg-warning/10';
    case 'flood': return 'text-primary border-primary/20 bg-primary/10';
    case 'accident': return 'text-danger border-danger/20 bg-danger/10';
    case 'diversion': return 'text-accent border-accent/20 bg-accent/10';
    default: return 'text-success border-success/20 bg-success/10';
  }
};

export const EventCard: React.FC<EventCardProps> = ({ event, className }) => {
  const colorClass = getEventColor(event.type);

  return (
    <div className={twMerge(clsx('flex items-center gap-4 p-3 rounded-md bg-surfaceHover border border-border', className))}>
      <div className={clsx('p-2 rounded-md border', colorClass)}>
        <AlertCircle className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white truncate">Road {event.roadId} — {event.type}</p>
        <div className="flex items-center gap-1 mt-1 text-xs text-textSecondary">
          <Clock className="w-3 h-3" />
          {event.timeAgo}
        </div>
      </div>
    </div>
  );
};
