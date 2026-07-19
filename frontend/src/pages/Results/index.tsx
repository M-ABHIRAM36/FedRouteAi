import React from 'react';
import { Download, FileText, BarChart2, CheckCircle, Database } from 'lucide-react';
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

const Results: React.FC = () => {
  const artifacts = [
    { title: 'Global Model Weights', filename: 'best_global_model.pt', icon: Database, url: 'http://localhost:8000/results/adaptive/best_global_model.pt' },
    { title: 'Global Metrics', filename: 'metrics.json', icon: CheckCircle, url: 'http://localhost:8000/results/adaptive/metrics.json' },
    { title: 'Classification Report', filename: 'classification_report.txt', icon: FileText, url: 'http://localhost:8000/results/adaptive/classification_report.txt' },
    { title: 'Training History', filename: 'adaptive_history.csv', icon: BarChart2, url: 'http://localhost:8000/results/adaptive/adaptive_history.csv' },
    { title: 'Adaptive Weights Log', filename: 'adaptive_weights.csv', icon: FileText, url: 'http://localhost:8000/results/adaptive/adaptive_weights.csv' },
    { title: 'Per-Client Metrics', filename: 'client_metrics.csv', icon: BarChart2, url: 'http://localhost:8000/results/adaptive/client_metrics.csv' },
  ];

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
        <div className="flex flex-col">
          {artifacts.map((artifact, i) => (
            <ArtifactRow key={i} {...artifact} />
          ))}
        </div>
      </div>
    </PageContainer>
  );
};

export default Results;
