import React from 'react';
import { motion } from 'framer-motion';
import { Database, Cpu, Network, RefreshCw, Globe, Target, BarChart2, ArrowRight } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

const pipelineSteps = [
  { id: 'dataset', label: 'Dataset', icon: Database, color: 'text-primary border-primary/30 bg-primary/10' },
  { id: 'feature-eng', label: 'Feature Engineering', icon: Cpu, color: 'text-primary border-primary/30 bg-primary/10' },
  { id: 'flower', label: 'Federated Learning', icon: Network, color: 'text-accent border-accent/30 bg-accent/10' },
  { id: 'adaptive', label: 'AdaptiveFedAvg', icon: RefreshCw, color: 'text-accent border-accent/30 bg-accent/10' },
  { id: 'global', label: 'Global Model', icon: Globe, color: 'text-success border-success/30 bg-success/10' },
  { id: 'predict', label: 'Prediction', icon: Target, color: 'text-warning border-warning/30 bg-warning/10' },
  { id: 'analysis', label: 'Analysis', icon: BarChart2, color: 'text-textPrimary border-border bg-surfaceHover' },
];

export const PipelineDiagram: React.FC<{ className?: string }> = ({ className }) => {
  return (
    <div className={twMerge(clsx('bg-surface border border-border rounded-lg p-6 overflow-x-auto', className))}>
      <h3 className="text-sm font-medium text-textSecondary mb-6">Research Workflow</h3>
      <div className="flex items-center min-w-max pb-4">
        {pipelineSteps.map((step, index) => (
          <React.Fragment key={step.id}>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className={clsx(
                'flex flex-col items-center justify-center p-4 rounded-xl border w-32 shrink-0 text-center gap-3 relative',
                step.color
              )}
            >
              <step.icon className="w-6 h-6" />
              <span className="text-xs font-semibold">{step.label}</span>
              
              {/* Pulse effect for active data flow */}
              <motion.div 
                className="absolute inset-0 rounded-xl border-2 border-current opacity-0"
                animate={{ opacity: [0, 0.5, 0] }}
                transition={{ duration: 2, repeat: Infinity, delay: index * 0.2 }}
              />
            </motion.div>
            
            {index < pipelineSteps.length - 1 && (
              <div className="px-3 text-border flex items-center justify-center">
                <ArrowRight className="w-5 h-5" />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
