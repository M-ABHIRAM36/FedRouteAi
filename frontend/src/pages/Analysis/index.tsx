import React, { useEffect, useState } from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { MarkdownViewer } from '../../components/common/MarkdownViewer';
import { FigureViewer } from '../../components/common/FigureViewer';

const mockMarkdown = `
## Research Observations
*   **Performance:** AdaptiveFedAvg stabilized the global model faster than FedAvg.
*   **Gate Activation:** The reliability gate effectively isolated anomalous updates from Region 3 during rounds 12-15.
*   **Rare Classes:** The \`beta\` factor successfully boosted macro F1 by preserving rare event patterns (e.g., Flood).
`;

const Analysis: React.FC = () => {
  const [report] = useState(mockMarkdown);

  useEffect(() => {
    // In real app, fetch from http://localhost:8000/results/adaptive/analysis_report.md
    // Using mock for now until backend static serving is confirmed working.
  }, []);

  return (
    <PageContainer>
      <PageHeader 
        title="Analysis Report" 
        description="Automated insights and generated research figures" 
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Main Text Report */}
        <div className="xl:col-span-2 bg-surface border border-border rounded-lg p-6">
          <MarkdownViewer content={report} />
        </div>

        {/* Generated Figures Column */}
        <div className="xl:col-span-1 space-y-6">
          <FigureViewer 
            src="http://localhost:8000/results/figures/quality_vs_weight.png"
            alt="Quality vs Weight"
            caption="Quality vs. Adaptive Weight"
            observation="Strong linear correlation post-gate filtering."
          />
          <FigureViewer 
            src="http://localhost:8000/results/figures/gate_distribution.png"
            alt="Gate Distribution"
            caption="Reliability Gate Actions"
            observation="Most drops occurred in regions with sparse trajectories."
          />
        </div>
        
      </div>
    </PageContainer>
  );
};

export default Analysis;
