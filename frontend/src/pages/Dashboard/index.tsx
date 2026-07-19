import React from 'react';
import { Map, Target, Layers } from 'lucide-react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { PipelineDiagram } from '../../components/common/PipelineDiagram';
import { StatCard } from '../../components/cards/StatCard';
import { EventCard, type EventLog } from '../../components/cards/EventCard';
import { ModelComparisonCard } from '../../components/cards/ModelComparisonCard';

const mockRecentEvents: EventLog[] = [
  { id: '1', roadId: 'R12', type: 'Construction', timeAgo: '2 mins ago' },
  { id: '2', roadId: 'R45', type: 'Accident', timeAgo: '15 mins ago' },
  { id: '3', roadId: 'R08', type: 'Flood', timeAgo: '1 hour ago' },
  { id: '4', roadId: 'R22', type: 'Diversion', timeAgo: '2 hours ago' },
];

const Dashboard: React.FC = () => {
  return (
    <PageContainer>
      <PageHeader 
        title="Research Overview" 
        description="FedRouteAI Complete Lifecycle & Telemetry" 
      />

      {/* 1. Animated Research Workflow */}
      <PipelineDiagram />

      {/* 2. Statistics Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <StatCard title="Road Segments" value={352} icon={Map} />
        <StatCard title="Regions" value={8} icon={Layers} />
        <StatCard title="Training Rounds" value={30} icon={Target} />
        <StatCard title="Accuracy" value="81.67%" icon={Target} trend="+0.67% vs Baseline" trendUp={true} />
        <StatCard title="Macro F1" value="0.639" icon={Target} trend="+0.010 vs Baseline" trendUp={true} />
      </div>

      {/* 3. Lower Section: Comparison, Events, Map Placeholder */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Model Comparison */}
        <div className="lg:col-span-1 space-y-6">
          <ModelComparisonCard />
          
          {/* Recent Events Panel */}
          <div className="bg-surface border border-border rounded-lg p-5">
            <h3 className="text-sm font-medium text-textSecondary mb-4">Recent Network Events</h3>
            <div className="space-y-3 flex flex-col">
              {mockRecentEvents.map(event => (
                <EventCard key={event.id} event={event} />
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Mini Traffic Map (Placeholder for now until Leaflet integration in Milestone 4) */}
        <div className="lg:col-span-2 bg-surface border border-border rounded-lg p-5 flex flex-col">
          <h3 className="text-sm font-medium text-textSecondary mb-4">Live Traffic Preview</h3>
          <div className="flex-1 bg-surfaceHover rounded-md border border-border flex items-center justify-center min-h-[300px]">
            <div className="text-center text-textSecondary">
              <Map className="w-10 h-10 mx-auto mb-3 opacity-50" />
              <p className="text-sm">Interactive Traffic Map (Loading in Milestone 4)</p>
            </div>
          </div>
        </div>

      </div>
    </PageContainer>
  );
};

export default Dashboard;
