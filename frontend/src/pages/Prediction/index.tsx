import React, { useState } from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { PredictionForm, type PredictionFormData } from '../../components/prediction/PredictionForm';
import { PredictionResult } from '../../components/prediction/PredictionResult';
import { predictTrafficEvent, type PredictionResponse } from '../../services/api/predictionApi';

const Prediction: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handlePredict = async (data: PredictionFormData) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await predictTrafficEvent(data);
      setResult(response);
    } catch (err: any) {
      setError(err.message || "Failed to run prediction. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <PageContainer>
      <PageHeader 
        title="Event Prediction" 
        description="Run live inference against the global Federated Learning model" 
      />

      <div className="space-y-6 max-w-4xl">
        <PredictionForm onSubmit={handlePredict} isLoading={isLoading} />
        
        {error && (
          <div className="bg-danger/10 border border-danger/20 text-danger p-4 rounded-lg text-sm font-medium">
            {error}
          </div>
        )}

        {result && (
          <PredictionResult result={result} />
        )}
      </div>
    </PageContainer>
  );
};

export default Prediction;
