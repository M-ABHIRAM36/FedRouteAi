import React, { useState } from 'react';
import { Trophy, TrendingUp, CheckCircle2, ShieldCheck, Cpu, Layers } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { ALL_MODELS, type ModelId, type ModelInfo } from '../../services/api/modelsApi';

interface ModelComparisonCardProps {
  className?: string;
  selectedModelId?: ModelId;
  onSelectModel?: (modelId: ModelId) => void;
}

export const ModelComparisonCard: React.FC<ModelComparisonCardProps> = ({
  className,
  selectedModelId = 'adaptive_federated',
  onSelectModel
}) => {
  const [activeId, setActiveId] = useState<ModelId>(selectedModelId);

  const handleSelect = (id: ModelId) => {
    setActiveId(id);
    if (onSelectModel) {
      onSelectModel(id);
    }
  };

  const getTagBadge = (model: ModelInfo) => {
    if (model.tagColor === 'green') {
      return (
        <span className="text-xs font-semibold text-success bg-success/10 px-2.5 py-0.5 rounded border border-success/30 flex items-center gap-1">
          <TrendingUp className="w-3 h-3" />
          {model.tag}
        </span>
      );
    }
    if (model.tagColor === 'purple') {
      return (
        <span className="text-xs font-semibold text-purple-400 bg-purple-500/10 px-2.5 py-0.5 rounded border border-purple-500/30 flex items-center gap-1">
          <Layers className="w-3 h-3" />
          {model.tag}
        </span>
      );
    }
    if (model.tagColor === 'blue') {
      return (
        <span className="text-xs font-medium text-primary bg-primary/10 px-2.5 py-0.5 rounded border border-primary/30 flex items-center gap-1">
          <ShieldCheck className="w-3 h-3" />
          {model.tag}
        </span>
      );
    }
    return (
      <span className="text-xs font-medium text-textSecondary bg-surfaceHover px-2.5 py-0.5 rounded border border-border flex items-center gap-1">
        <Cpu className="w-3 h-3" />
        {model.tag}
      </span>
    );
  };

  return (
    <div className={twMerge(clsx('bg-surface border border-border rounded-lg p-6 space-y-5', className))}>
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-warning/10 text-warning rounded-md border border-warning/20">
            <Trophy className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-textPrimary">Evaluated Models ({ALL_MODELS.length})</h3>
            <p className="text-xs text-textSecondary">Compare FedRouteAI model architectures & metrics</p>
          </div>
        </div>
        <span className="text-xs font-mono text-textSecondary bg-surfaceHover px-2 py-1 rounded border border-border">
          {ALL_MODELS.length} Models
        </span>
      </div>

      <div className="space-y-3">
        {ALL_MODELS.map((model) => {
          const isSelected = activeId === model.id;
          return (
            <div
              key={model.id}
              onClick={() => handleSelect(model.id)}
              className={clsx(
                'cursor-pointer rounded-lg p-4 transition-all duration-200 border relative overflow-hidden',
                isSelected
                  ? 'bg-primary/10 border-primary shadow-sm ring-1 ring-primary/40'
                  : 'bg-surfaceHover/50 border-border hover:bg-surfaceHover hover:border-textSecondary/40'
              )}
            >
              {isSelected && (
                <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary"></div>
              )}

              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white">{model.label}</span>
                  {isSelected && <CheckCircle2 className="w-4 h-4 text-primary" />}
                </div>
                {getTagBadge(model)}
              </div>

              <p className="text-xs text-textSecondary mb-3 leading-relaxed">
                {model.description}
              </p>

              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-border/50 text-center">
                <div className="bg-surface/60 p-2 rounded border border-border/40">
                  <div className="text-[10px] uppercase tracking-wider text-textSecondary font-mono">Accuracy</div>
                  <div className="text-sm font-bold text-textPrimary">
                    {(model.metrics.accuracy * 100).toFixed(2)}%
                  </div>
                </div>
                <div className="bg-surface/60 p-2 rounded border border-border/40">
                  <div className="text-[10px] uppercase tracking-wider text-textSecondary font-mono">Macro F1</div>
                  <div className="text-sm font-bold text-textPrimary">
                    {model.metrics.macro_f1.toFixed(4)}
                  </div>
                </div>
                <div className="bg-surface/60 p-2 rounded border border-border/40">
                  <div className="text-[10px] uppercase tracking-wider text-textSecondary font-mono">ROC AUC</div>
                  <div className="text-sm font-bold text-success">
                    {model.metrics.roc_auc_macro.toFixed(4)}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};