import React from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { MarkdownViewer } from '../../components/common/MarkdownViewer';
import { FigureViewer } from '../../components/common/FigureViewer';

import { useQuery } from '@tanstack/react-query';
import { fetchAnalysisData } from '../../services/api/analysisApi';

const Analysis: React.FC = () => {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['analysis_data'],
    queryFn: fetchAnalysisData
  });

  return (
    <PageContainer>
      <PageHeader 
        title="Analysis Report" 
        description="Automated insights and generated research figures" 
      />

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
              No figures found.
            </div>
          ) : null}
        </div>
        
      </div>
    </PageContainer>
  );
};

export default Analysis;
