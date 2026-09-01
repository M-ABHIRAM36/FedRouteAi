import React, { useState } from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ModelComparisonCard } from '../../components/cards/ModelComparisonCard';
import { ChartCard } from '../../components/cards/ChartCard';
import { LineChartComponent } from '../../components/charts/LineChartComponent';
import { useQuery } from '@tanstack/react-query';
import { fetchTrainingData } from '../../services/api/trainingApi';
import { ALL_MODELS, type ModelId } from '../../services/api/modelsApi';
import { Sparkles } from 'lucide-react';

const Training: React.FC = () => {
  const [selectedModelId, setSelectedModelId] = useState<ModelId>('adaptive_federated');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['training_data', selectedModelId],
    queryFn: () => fetchTrainingData(selectedModelId)
  });

  const activeModel = ALL_MODELS.find(m => m.id === selectedModelId) || ALL_MODELS[0];

  return (
    <PageContainer>
      <PageHeader 
        title="Training History" 
        description="Global Model Convergence & Performance Metrics Across Evaluated Architectures" 
      />

      {/* Model Selection Header */}
      <div className="bg-surface border border-border rounded-lg p-4 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 text-primary rounded-md border border-primary/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">Viewing Architecture: <span className="text-primary">{activeModel.label}</span></h3>
            <p className="text-xs text-textSecondary">{activeModel.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {ALL_MODELS.map(m => (
            <button
              key={m.id}
              onClick={() => setSelectedModelId(m.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all border ${
                selectedModelId === m.id
                  ? 'bg-primary text-white border-primary shadow-sm'
                  : 'bg-surfaceHover text-textSecondary border-border hover:text-white hover:border-textSecondary'
              }`}
            >
              {m.shortLabel}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-1">
          <ModelComparisonCard
            selectedModelId={selectedModelId}
            onSelectModel={(id) => setSelectedModelId(id)}
          />
        </div>
        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-6">
          <ChartCard title={`${activeModel.shortLabel} Accuracy Progression`} description="Accuracy over rounds">
            {isLoading ? (
               <div className="flex items-center justify-center h-full text-textSecondary text-sm">Loading...</div>
            ) : isError ? (
               <div className="flex items-center justify-center h-full text-danger text-sm">Error</div>
            ) : data && data.history.length > 0 ? (
               <LineChartComponent 
                 data={data.history} 
                 xAxisKey="Round" 
                 series={[{ key: 'Accuracy', name: 'Accuracy', color: '#238636' }]} 
               />
            ) : (
               <div className="flex items-center justify-center h-full text-textSecondary text-sm">No data</div>
            )}
          </ChartCard>
          <ChartCard title={`${activeModel.shortLabel} Loss Convergence`} description="Loss over rounds">
            {isLoading ? (
               <div className="flex items-center justify-center h-full text-textSecondary text-sm">Loading...</div>
            ) : isError ? (
               <div className="flex items-center justify-center h-full text-danger text-sm">Error</div>
            ) : data && data.history.length > 0 ? (
               <LineChartComponent 
                 data={data.history} 
                 xAxisKey="Round" 
                 series={[{ key: 'Loss', name: 'Loss', color: '#f85149' }]} 
               />
            ) : (
               <div className="flex items-center justify-center h-full text-textSecondary text-sm">No data</div>
            )}
          </ChartCard>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6">
        <div className="bg-surface border border-border rounded-lg p-6">
          <h3 className="text-sm font-medium text-textPrimary mb-4">Classification Report ({activeModel.label})</h3>
          <div className="bg-[#0d1117] p-4 rounded-md overflow-x-auto border border-border">
            {isLoading ? (
               <div className="text-textSecondary text-sm">Loading report...</div>
            ) : isError ? (
               <div className="text-danger text-sm">Failed to load classification report.</div>
            ) : data && data.reportText ? (
               <pre className="text-sm text-textSecondary font-mono whitespace-pre-wrap">
                 {data.reportText}
               </pre>
            ) : (
               <div className="text-textSecondary text-sm">No report found.</div>
            )}
          </div>
        </div>
      </div>

    </PageContainer>
  );
};

export default Training;