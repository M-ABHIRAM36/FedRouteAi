import React, { useEffect, useState } from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ClientCard } from '../../components/cards/ClientCard';
import { ChartCard } from '../../components/cards/ChartCard';
import { LineChartComponent, type ChartDataSeries } from '../../components/charts/LineChartComponent';
import { parseCSV } from '../../services/parsers/csvParser';

const Federated: React.FC = () => {
  const [weightData, setWeightData] = useState<any[]>([]);
  
  useEffect(() => {
    // In a real app, this points to the backend /results endpoint
    // For now, we mock the load if it fails, or try to load from a public static path
    const loadData = async () => {
      try {
        const data = await parseCSV('http://localhost:8000/results/adaptive/adaptive_weights.csv');
        setWeightData(data);
      } catch (err) {
        console.warn("Failed to load adaptive_weights.csv. Ensure backend static mount is running.");
      }
    };
    loadData();
  }, []);

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
          {weightData.length > 0 ? (
            <LineChartComponent data={weightData} xAxisKey="Round" series={weightSeries} />
          ) : (
            <div className="flex items-center justify-center h-full text-textSecondary text-sm">
              Waiting for data...
            </div>
          )}
        </ChartCard>
        
        <ChartCard title="Reliability Gate" description="Client gating activations across rounds">
          {/* Placeholder for Gate chart */}
          <div className="flex items-center justify-center h-full text-textSecondary text-sm">
            Gate tracking visualization
          </div>
        </ChartCard>
      </div>

      <h3 className="text-lg font-medium text-white mt-8 mb-4 border-b border-border pb-2">Latest Client Status</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* Mocking the latest state for 8 regions for UI completion of Milestone 3 */}
        {[1,2,3,4,5,6,7,8].map(i => (
          <ClientCard 
            key={i}
            region={`REGION_0${i}`}
            quality={0.8 + (Math.random() * 0.1)}
            ema={0.85 + (Math.random() * 0.1)}
            weight={0.125}
            samples={1200 + Math.floor(Math.random() * 500)}
            gatePassed={Math.random() > 0.1}
          />
        ))}
      </div>
    </PageContainer>
  );
};

export default Federated;
