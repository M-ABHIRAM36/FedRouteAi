import React, { useState } from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { MarkdownViewer } from '../../components/common/MarkdownViewer';
import { FigureViewer } from '../../components/common/FigureViewer';
import { useQuery } from '@tanstack/react-query';
import { fetchAnalysisData } from '../../services/api/analysisApi';
import { ALL_MODELS, type ModelId } from '../../services/api/modelsApi';
import { Sparkles } from 'lucide-react';

const Analysis: React.FC = () => {
  const [selectedModelId, setSelectedModelId] = useState<ModelId>('adaptive_federated');

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['analysis_data', selectedModelId],
    queryFn: () => fetchAnalysisData(selectedModelId)
  });

  const activeModel = ALL_MODELS.find(m => m.id === selectedModelId) || ALL_MODELS[0];

  return (
    <PageContainer>
      <PageHeader 
        title="Analysis Report" 
        description="Automated insights and generated research figures across evaluated models" 
      />

      {/* Model Selector Header */}
      <div className="bg-surface border border-border rounded-lg p-4 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 text-primary rounded-lg border border-primary/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">Active Report: <span className="text-primary">{activeModel.label}</span></h3>
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

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Main Text Report */}
        <div className="xl:col-span-2 bg-surface border border-border rounded-lg p-6 min-h-[500px]">
          {isLoading ? (
            <div className="flex items-center justify-center h-full text-textSecondary">
              Loading analysis...
            </div>
          ) : isError ? (
            <div className="flex items-center justify-center h-full text-danger font-medium">
              {error instanceof Error ? error.message : "Analysis report unavailable."}
            </div>
          ) : data && data.reportMarkdown ? (
            <MarkdownViewer content={data.reportMarkdown} />
          ) : (
            <div className="flex items-center justify-center h-full text-textSecondary">
              No analysis report found.
            </div>
          )}
        </div>

        {/* Generated Figures Column */}
        <div className="xl:col-span-1 space-y-6">
          {isLoading ? (
            <div className="flex items-center justify-center h-32 bg-surface border border-border rounded-lg text-textSecondary">
              Discovering figures...
            </div>
          ) : data && data.figures.length > 0 ? (
            data.figures.map((fig, idx) => (
              <FigureViewer 
                key={idx}
                src={fig.src}
                alt={fig.title}
                caption={fig.caption}
                observation={fig.observation}
              />
            ))
          ) : !isLoading && !isError ? (
            <div className="flex items-center justify-center h-32 bg-surface border border-border rounded-lg text-textSecondary">
              No additional figures found for this model.
            </div>
          ) : null}
        </div>
      </div>
    </PageContainer>
  );
};

export default Analysis;