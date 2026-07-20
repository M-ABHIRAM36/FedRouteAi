import React from 'react';
import { Map, Target, Layers } from 'lucide-react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { PipelineDiagram } from '../../components/common/PipelineDiagram';
import { StatCard } from '../../components/cards/StatCard';
import { EventCard } from '../../components/cards/EventCard';
import { ModelComparisonCard } from '../../components/cards/ModelComparisonCard';

import { useQuery } from '@tanstack/react-query';
import { fetchDashboardMetrics } from '../../services/api/metricsApi';
import { fetchActiveEvents } from '../../services/api/eventsApi';

const Dashboard: React.FC = () => {
  const { data: metrics, isLoading: isMetricsLoading, isError: isMetricsError } = useQuery({
    queryKey: ['metrics'],
    queryFn: fetchDashboardMetrics
  });

  const { data: events, isLoading: isEventsLoading, isError: isEventsError } = useQuery({
    queryKey: ['events'],
    queryFn: fetchActiveEvents
  });
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
        {isMetricsLoading ? (
          <div className="col-span-5 p-4 text-center text-textSecondary">Loading telemetry...</div>
        ) : isMetricsError ? (
          <div className="col-span-5 p-4 text-center text-danger">Failed to load metrics. Backend may be offline.</div>
        ) : metrics ? (
          <>
            <StatCard title="Road Segments" value={metrics.total_segments} icon={Map} />
            <StatCard title="Regions" value={metrics.active_regions} icon={Layers} />
            <StatCard title="Active Events" value={metrics.total_events} icon={Target} />
            <StatCard title="System Health" value={metrics.system_health} icon={Target} />
            <StatCard title="Training Rounds" value={30} icon={Target} />
          </>
        ) : null}
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
              {isEventsLoading ? (
                <div className="text-sm text-textSecondary text-center py-4">Loading events...</div>
              ) : isEventsError ? (
                <div className="text-sm text-danger text-center py-4">Failed to load events.</div>
              ) : events && events.length > 0 ? (
                events.slice(0, 5).map(event => (
                  <EventCard key={event.id} event={{ id: String(event.id), roadId: event.segment_id, type: event.event_type, timeAgo: new Date(event.start_time).toLocaleTimeString() }} />
                ))
              ) : (
                <div className="text-sm text-textSecondary text-center py-8">
                  <Target className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  No active events in the network.
                </div>
              )}
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
