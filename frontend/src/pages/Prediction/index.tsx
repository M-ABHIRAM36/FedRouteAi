import React from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { useMutation } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { PredictionForm, type PredictionFormData } from '../../components/prediction/PredictionForm';
import { PredictionResult } from '../../components/prediction/PredictionResult';
import { predictTrafficEvent } from '../../services/api/predictionApi';

const Prediction: React.FC = () => {
  const predictMutation = useMutation({
    mutationFn: (data: PredictionFormData) => {
      const requestData = {
        road_id: data.road_id,
        speed: Number(data.speed) || 0,
        density: Number(data.density) || 0,
        travel_time: Number(data.travel_time) || 0,
        heading: Number(data.heading) || 0,
      };
      return predictTrafficEvent(requestData);
    }
  });

  const handlePredict = (data: PredictionFormData) => {
    predictMutation.mutate(data);
  };

  return (
    <PageContainer>
      <PageHeader 
        title="Event Prediction" 
        description="Run live inference against the global Federated Learning model" 
      />

      <div className="max-w-5xl space-y-4">
        <PredictionForm onSubmit={handlePredict} isLoading={predictMutation.isPending} />
        
        {predictMutation.isError && (
          <div role="alert" className="border border-danger/30 bg-danger/10 p-4 text-sm font-medium text-danger">
            {predictMutation.error instanceof Error ? predictMutation.error.message : "Failed to run prediction. Backend may be offline."}
          </div>
        )}

        {predictMutation.isSuccess && predictMutation.data && (
          <PredictionResult result={predictMutation.data} />
        )}
      </div>
    </PageContainer>
  );
};

export default Prediction;
