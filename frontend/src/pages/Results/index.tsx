import React from 'react';
import { Download, FileText } from 'lucide-react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';

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

import { useQuery } from '@tanstack/react-query';
import { fetchAvailableArtifacts } from '../../services/api/resultsApi';

const Results: React.FC = () => {
  const { data: artifacts, isLoading, isError, error } = useQuery({
    queryKey: ['results_artifacts'],
    queryFn: fetchAvailableArtifacts
  });

  return (
    <PageContainer>
      <PageHeader 
        title="Experiment Artifacts" 
        description="Browse and download all outputs from the latest training run" 
      />

      <div className="bg-surface border border-border rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-border bg-surfaceHover">
          <h3 className="text-sm font-semibold text-white">AdaptiveFedAvg Run Outputs</h3>
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
              No artifacts have been generated yet.
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
};

export default Results;
