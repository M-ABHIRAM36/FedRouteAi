import React from 'react';
import { AlertCircle, Clock, ShieldCheck, Zap } from 'lucide-react';
import type { PredictionResponse } from '../../services/api/predictionApi';
import { segmentStyles, type SegmentTrafficStatus } from '../map/segmentStyles';

interface PredictionResultProps {
  result: PredictionResponse;
}

const classKey = (value: string) => value.toLowerCase().replaceAll(' ', '_') as SegmentTrafficStatus;
const displayName = (value: string) => value.replaceAll('_', ' ');
const classColor = (value: string) => segmentStyles[classKey(value)]?.color ?? segmentStyles.unknown.color;

export const PredictionResult: React.FC<PredictionResultProps> = ({ result }) => {
  const predictionKey = classKey(result.prediction);
  const isEvent = predictionKey !== 'normal';
  const probabilities = Object.entries(result.probabilities).sort(([, left], [, right]) => right - left);
  const predictionColor = classColor(result.prediction);

  return <section className="border border-border bg-surface" aria-labelledby="inference-result-title">
    <div className="flex items-center justify-between border-b border-border px-5 py-3">
      <h2 id="inference-result-title" className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-textPrimary"><Zap className="h-4 w-4 text-warning" />Inference result</h2>
      <div className="flex items-center gap-1.5 text-[10px] text-textSecondary"><Clock className="h-3.5 w-3.5" />{result.inference_time_ms} ms</div>
    </div>

    <div className="grid md:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
      <div className="flex min-h-52 flex-col justify-between border-b border-border p-5 md:border-b-0 md:border-r">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-textSecondary">Top model class</div>
          <div className="mt-5 flex items-center gap-3" style={{ color: predictionColor }}>
            {isEvent ? <AlertCircle className="h-8 w-8" /> : <ShieldCheck className="h-8 w-8" />}
            <div className="text-2xl font-semibold capitalize text-white">{displayName(result.prediction)}</div>
          </div>
        </div>
        <div className="mt-6 border-l-2 pl-3" style={{ borderColor: predictionColor }}>
          <div className="text-[10px] font-semibold uppercase text-textSecondary">Returned model score</div>
          <div className="mt-0.5 text-2xl font-semibold text-white">{(result.confidence * 100).toFixed(1)}%</div>
          <div className="mt-1 text-[10px] leading-4 text-textSecondary">Score for the selected class. Interpret it with the full class distribution.</div>
        </div>
      </div>

      <div className="p-5">
        <div className="flex items-baseline justify-between gap-4"><div className="text-[10px] font-semibold uppercase tracking-wider text-textSecondary">Class distribution</div><div className="text-[10px] text-textSecondary">API probabilities</div></div>
        {probabilities.length > 0 ? <div className="mt-4 space-y-3">{probabilities.map(([label, probability]) => <div key={label}>
          <div className="mb-1 flex items-center justify-between gap-3 text-xs"><div className="flex min-w-0 items-center gap-2"><span className="h-2 w-2 shrink-0" style={{ backgroundColor: classColor(label) }} /><span className="truncate capitalize text-textPrimary">{displayName(label)}</span></div><span className="font-mono text-textSecondary">{(probability * 100).toFixed(1)}%</span></div>
          <div className="h-1.5 overflow-hidden bg-surfaceHover"><div className="h-full transition-[width] duration-500" style={{ width: `${Math.max(0, Math.min(1, probability)) * 100}%`, backgroundColor: classColor(label) }} /></div>
        </div>)}</div> : <div className="mt-4 border border-border px-3 py-4 text-xs text-textSecondary">No class probabilities were returned by the prediction API.</div>}
      </div>
    </div>
  </section>;
};
