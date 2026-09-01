import React, { useState } from 'react';
import { Download, FileText, Sparkles } from 'lucide-react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { useQuery } from '@tanstack/react-query';
import { fetchAvailableArtifacts } from '../../services/api/resultsApi';
import { ALL_MODELS, type ModelId } from '../../services/api/modelsApi';

interface ArtifactProps {
  title: string;
  filename: string;
  icon: React.ElementType;
  url: string;
}

const ArtifactRow: React.FC<ArtifactProps> = ({ title, filename, icon: Icon, url }) => (
  <div className="flex items-center justify-between p-4 bg-surfaceHover border-b border-border last:border-b-0 hover:bg-surfaceHover/80 transition-colors">
    <div className="flex items-center gap-4">
      <div className="p-2 bg-surface rounded-md border border-border">
        <Icon className="w-5 h-5 text-primary" />
      </div>
      <div>
        <h4 className="text-sm font-medium text-white">{title}</h4>
        <p className="text-xs text-textSecondary">{filename}</p>
      </div>
    </div>
    <a 
      href={url} 
      download 
      className="flex items-center gap-2 px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary rounded-md text-sm font-medium border border-primary/20 transition-colors"
    >
      <Download className="w-4 h-4" />
      Download
    </a>
  </div>
);

const Results: React.FC = () => {
  const [selectedModelId, setSelectedModelId] = useState<ModelId>('adaptive_federated');

  const { data: artifacts, isLoading, isError, error } = useQuery({
    queryKey: ['results_artifacts', selectedModelId],
    queryFn: () => fetchAvailableArtifacts(selectedModelId)
  });

  const activeModel = ALL_MODELS.find(m => m.id === selectedModelId) || ALL_MODELS[0];

  return (
    <PageContainer>
      <PageHeader 
        title="Experiment Artifacts" 
        description="Browse and download outputs across all evaluated model architectures" 
      />

      {/* Model Selection Banner */}
      <div className="bg-surface border border-border rounded-lg p-4 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 text-primary rounded-lg border border-primary/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">Target Architecture: <span className="text-primary">{activeModel.label}</span></h3>
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

      <div className="bg-surface border border-border rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-border bg-surfaceHover flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">{activeModel.label} Artifact Directory</h3>
          <span className="text-xs font-mono text-textSecondary bg-surface px-2.5 py-1 rounded border border-border">
            Artifacts: {artifacts ? artifacts.length : 0}
          </span>
        </div>
        <div className="flex flex-col min-h-[300px]">
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center text-textSecondary text-sm p-8">
              Scanning for available artifacts...
            </div>
          ) : isError ? (
            <div className="flex-1 flex items-center justify-center text-danger text-sm font-medium p-8">
              {error instanceof Error ? error.message : "Failed to load artifacts."}
            </div>
          ) : artifacts && artifacts.length > 0 ? (
            artifacts.map((artifact, i) => (
              <ArtifactRow 
                key={i} 
                title={artifact.title} 
                filename={artifact.filename} 
                icon={FileText} 
                url={artifact.url} 
              />
            ))
          ) : (
            <div className="flex-1 flex items-center justify-center text-textSecondary text-sm p-8">
              No artifacts have been generated for this model yet.
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
};

export default Results;