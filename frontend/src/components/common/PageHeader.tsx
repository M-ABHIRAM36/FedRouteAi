import React from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({ title, description, action }) => {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">{title}</h1>
        {description && <p className="text-sm text-textSecondary mt-1">{description}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
};
