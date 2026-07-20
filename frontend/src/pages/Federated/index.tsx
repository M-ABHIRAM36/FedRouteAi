import React from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ClientCard } from '../../components/cards/ClientCard';
import { ChartCard } from '../../components/cards/ChartCard';
import { LineChartComponent, type ChartDataSeries } from '../../components/charts/LineChartComponent';
import { useQuery } from '@tanstack/react-query';
import { fetchFederatedSummary } from '../../services/api/federatedApi';

const Federated: React.FC = () => {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['federated_summary'],
    queryFn: fetchFederatedSummary
  });

  const weightSeries: ChartDataSeries[] = [
    { key: 'w_k', name: 'Adaptive Weight', color: '#2f81f7' },
    { key: 'q_k', name: 'Quality', color: '#238636' },
    { key: 'rho_k', name: 'EMA', color: '#8957e5' },
  ];

  return (
    <PageContainer>
      <PageHeader 
        title="Federated Learning" 
        description="AdaptiveFedAvg Telemetry & Client Weight Evolution" 
      />

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
        
        <ChartCard title="Global Weight Evolution" description="AdaptiveFedAvg weight adjustments across rounds">
          <div className="flex items-center justify-center h-full text-textSecondary text-sm">
            Gate tracking visualization
          </div>
        </ChartCard>
      </div>

      <h3 className="text-lg font-medium text-white mt-8 mb-4 border-b border-border pb-2">Latest Client Status</h3>
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
