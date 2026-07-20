import React from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ModelComparisonCard } from '../../components/cards/ModelComparisonCard';
import { ChartCard } from '../../components/cards/ChartCard';
import { LineChartComponent } from '../../components/charts/LineChartComponent';
import { useQuery } from '@tanstack/react-query';
import { fetchTrainingData } from '../../services/api/trainingApi';

const Training: React.FC = () => {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['training_data'],
    queryFn: fetchTrainingData
  });
  return (
    <PageContainer>
      <PageHeader 
        title="Training History" 
        description="Global Model Convergence & Performance Metrics" 
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-1">
          {isLoading ? (
             <div className="h-64 bg-surface border border-border rounded-lg flex items-center justify-center text-textSecondary">Loading...</div>
          ) : isError ? (
             <div className="h-64 bg-surface border border-border rounded-lg flex items-center justify-center text-danger">Error loading metrics.</div>
          ) : (
            <ModelComparisonCard metrics={data?.metrics} />
          )}
        </div>
        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-6">
          <ChartCard title="Accuracy Progression" description="Global Accuracy over rounds">
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
          <ChartCard title="Loss Convergence" description="Global Loss over rounds">
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
          <h3 className="text-sm font-medium text-textPrimary mb-4">Classification Report</h3>
          <div className="bg-[#0d1117] p-4 rounded-md overflow-x-auto">
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
