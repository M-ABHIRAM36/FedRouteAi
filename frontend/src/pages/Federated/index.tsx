import React, { useState } from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ClientCard } from '../../components/cards/ClientCard';
import { ChartCard } from '../../components/cards/ChartCard';
import { LineChartComponent, type ChartDataSeries } from '../../components/charts/LineChartComponent';
import { useQuery } from '@tanstack/react-query';
import { fetchFederatedSummary } from '../../services/api/federatedApi';
import { ALL_MODELS, type ModelId } from '../../services/api/modelsApi';
import { Sparkles } from 'lucide-react';

const Federated: React.FC = () => {
  const [selectedModelId, setSelectedModelId] = useState<ModelId>('adaptive_federated');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['federated_summary', selectedModelId],
    queryFn: () => fetchFederatedSummary(selectedModelId)
  });

  const weightSeries: ChartDataSeries[] = [
    { key: 'w_k', name: 'Adaptive Weight', color: '#2f81f7' },
    { key: 'q_k', name: 'Quality', color: '#238636' },
    { key: 'rho_k', name: 'EMA F1', color: '#8957e5' },
  ];

  const activeModel = ALL_MODELS.find(m => m.id === selectedModelId) || ALL_MODELS[0];

  return (
    <PageContainer>
      <PageHeader 
        title="Federated Learning" 
        description="Multi-Model Adaptive Dynamic Weighting Telemetry & Client Weight Evolution" 
      />

      {/* Model Selector Header */}
      <div className="bg-surface border border-border rounded-lg p-4 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 text-primary rounded-md border border-primary/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">{activeModel.label}</h3>
            <p className="text-xs text-textSecondary">{activeModel.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {ALL_MODELS.filter(m => m.id === 'adaptive_federated' || m.id === 'geo_v2' || m.id === 'federated').map(m => (
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Weight Evolution Overview" description="Tracking w_k, q_k, and rho_k over communication rounds">
          {isLoading ? (
            <div className="flex items-center justify-center h-full text-textSecondary text-sm">
              Loading artifact telemetry...
            </div>
          ) : isError ? (
            <div className="flex items-center justify-center h-full text-danger text-sm font-medium">
              Failed to load weights artifact.
            </div>
          ) : data && data.chartData.length > 0 ? (
            <LineChartComponent data={data.chartData} xAxisKey="Round" series={weightSeries} />
          ) : (
            <div className="flex items-center justify-center h-full text-textSecondary text-sm">
              Waiting for data...
            </div>
          )}
        </ChartCard>
        
        <ChartCard title="Global Quality vs Weight Dynamics" description="Quality factor q_k and weight evolution">
          {data && data.chartData.length > 0 ? (
            <LineChartComponent 
              data={data.chartData} 
              xAxisKey="Round" 
              series={[
                { key: 'q_k', name: 'Quality (q_k)', color: '#e3b341' },
                { key: 'w_k', name: 'Normalized Weight (w_k)', color: '#2f81f7' }
              ]} 
            />
          ) : (
            <div className="flex items-center justify-center h-full text-textSecondary text-sm">
              Gate tracking visualization
            </div>
          )}
        </ChartCard>
      </div>

      <h3 className="text-lg font-medium text-white mt-8 mb-4 border-b border-border pb-2">Latest Client Status ({activeModel.shortLabel})</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {isLoading ? (
          <div className="col-span-full py-8 text-center text-textSecondary text-sm">
            Loading client metrics...
          </div>
        ) : isError ? (
          <div className="col-span-full py-8 text-center text-danger text-sm font-medium">
            Failed to load client metrics.
          </div>
        ) : data && data.latestClients.length > 0 ? (
          data.latestClients.map(client => (
            <ClientCard 
              key={client.region_id}
              region={client.region_id}
              quality={client.quality}
              ema={client.ema_f1}
              weight={client.weight}
              samples={client.samples}
              gatePassed={client.gatePassed}
            />
          ))
        ) : (
          <div className="col-span-full py-8 text-center text-textSecondary text-sm">
            No client records found.
          </div>
        )}
      </div>
    </PageContainer>
  );
};

export default Federated;