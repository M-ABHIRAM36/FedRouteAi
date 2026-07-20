import React from 'react';
import { Trophy, TrendingUp } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

import type { TrainingMetrics } from '../../services/api/trainingApi';

export const ModelComparisonCard: React.FC<{ className?: string; metrics?: TrainingMetrics }> = ({ className, metrics }) => {
  return (
    <div className={twMerge(clsx('bg-surface border border-border rounded-lg p-6', className))}>
      <div className="flex items-center gap-3 mb-6">
        <Trophy className="w-5 h-5 text-warning" />
        <h3 className="text-sm font-medium text-textPrimary">Model Performance Summary</h3>
      </div>
      
      <div className="space-y-4">
        {/* AdaptiveFedAvg */}
        <div className="bg-primary/5 border border-primary/20 rounded-md p-4 relative overflow-hidden">
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary"></div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-bold text-white">AdaptiveFedAvg</span>
            <span className="text-xs font-medium text-success bg-success/10 px-2 py-0.5 rounded border border-success/20 flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              Best Overall
            </span>
          </div>
          <div className="grid grid-cols-3 gap-4 mt-3">
            <div>
              <div className="text-xs text-textSecondary mb-1">Accuracy</div>
              <div className="text-sm font-semibold text-textPrimary">
                {metrics ? `${(metrics.accuracy * 100).toFixed(2)}%` : '---'}
              </div>
            </div>
            <div>
              <div className="text-xs text-textSecondary mb-1">Macro F1</div>
              <div className="text-sm font-semibold text-textPrimary">
                {metrics ? metrics.macro_f1.toFixed(3) : '---'}
              </div>
            </div>
            <div>
              <div className="text-xs text-textSecondary mb-1">ROC AUC</div>
              <div className="text-sm font-semibold text-textPrimary text-success flex items-center gap-1">
                {metrics ? metrics.roc_auc_macro.toFixed(3) : '---'}
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
