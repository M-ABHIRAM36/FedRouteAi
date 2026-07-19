import React from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ModelComparisonCard } from '../../components/cards/ModelComparisonCard';
import { ChartCard } from '../../components/cards/ChartCard';

const Training: React.FC = () => {
  return (
    <PageContainer>
      <PageHeader 
        title="Training History" 
        description="Global Model Convergence & Performance Metrics" 
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-1">
          <ModelComparisonCard />
        </div>
        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-6">
          <ChartCard title="Accuracy Progression" description="Global Accuracy over 30 rounds">
            <div className="flex items-center justify-center h-full text-textSecondary text-sm">
              Accuracy Chart Placeholder
            </div>
          </ChartCard>
          <ChartCard title="Loss Convergence" description="Global Loss over 30 rounds">
            <div className="flex items-center justify-center h-full text-textSecondary text-sm">
              Loss Chart Placeholder
            </div>
          </ChartCard>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Confusion Matrix" description="Final Global Model Performance per Class">
           <div className="flex items-center justify-center h-full text-textSecondary text-sm">
              Confusion Matrix Heatmap
            </div>
        </ChartCard>
        <ChartCard title="ROC Curve" description="Receiver Operating Characteristic">
           <div className="flex items-center justify-center h-full text-textSecondary text-sm">
              ROC Curve
            </div>
        </ChartCard>
      </div>

    </PageContainer>
  );
};

export default Training;
