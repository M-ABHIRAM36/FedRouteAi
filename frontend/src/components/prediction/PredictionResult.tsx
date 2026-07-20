import React from 'react';
import { ShieldCheck, AlertCircle, Clock, Zap } from 'lucide-react';
import { clsx } from 'clsx';
import type { PredictionResponse } from '../../services/api/predictionApi';

interface PredictionResultProps {
  result: PredictionResponse;
}

export const PredictionResult: React.FC<PredictionResultProps> = ({ result }) => {
  const isEvent = result.prediction !== 'Normal';

  const getEventColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'construction': return 'text-warning border-warning/20 bg-warning/10';
      case 'flood': return 'text-primary border-primary/20 bg-primary/10';
      case 'accident': return 'text-danger border-danger/20 bg-danger/10';
      case 'diversion': return 'text-accent border-accent/20 bg-accent/10';
      default: return 'text-success border-success/20 bg-success/10';
    }
  };

  const colorClass = getEventColor(result.prediction);

  return (
    <div className="bg-surface border border-border rounded-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-sm font-medium text-textPrimary flex items-center gap-2">
          <Zap className="w-4 h-4 text-warning" />
          Inference Result
        </h3>
      </div>

      <div className="flex flex-col md:flex-row gap-6">
        {/* Main Prediction Display */}
        <div className={clsx('flex-1 rounded-lg border p-6 flex flex-col items-center justify-center text-center', colorClass)}>
          {isEvent ? (
            <AlertCircle className="w-12 h-12 mb-3" />
          ) : (
            <ShieldCheck className="w-12 h-12 mb-3" />
          )}
          <div className="text-2xl font-bold tracking-tight">{result.prediction}</div>
          <div className="text-sm mt-1 opacity-80">Predicted Road Status</div>
        </div>

        {/* Inference Stats */}
        <div className="flex-1 flex flex-col justify-center gap-4">
          <div className="bg-background rounded-md p-4 border border-border">
            <div className="text-xs text-textSecondary mb-1 uppercase tracking-wider font-semibold">Confidence Score</div>
            <div className="flex items-end gap-2">
              <span className="text-2xl font-bold text-white">{(result.confidence * 100).toFixed(1)}%</span>
            </div>
            
            <div className="mt-2 h-1.5 w-full bg-surfaceHover rounded-full overflow-hidden">
              <div 
                className={clsx('h-full rounded-full transition-all duration-1000', 
                  result.confidence > 0.8 ? 'bg-success' : result.confidence > 0.6 ? 'bg-warning' : 'bg-danger'
                )} 
                style={{ width: `${result.confidence * 100}%` }} 
              />
            </div>
          </div>

          <div className="bg-background rounded-md p-4 border border-border flex items-center justify-between">
            <div>
              <div className="text-xs text-textSecondary mb-1 uppercase tracking-wider font-semibold">Inference Time</div>
              <div className="text-lg font-bold text-white">{result.inference_time_ms} ms</div>
            </div>
            <Clock className="w-6 h-6 text-textSecondary opacity-50" />
          </div>
        </div>
      </div>
    </div>
  );
};
