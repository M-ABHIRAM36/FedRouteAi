import React, { useState } from 'react';
import { Map, Target, Layers, Cpu, ShieldCheck, Sparkles } from 'lucide-react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { PipelineDiagram } from '../../components/common/PipelineDiagram';
import { StatCard } from '../../components/cards/StatCard';
import { EventCard } from '../../components/cards/EventCard';
import { ModelComparisonCard } from '../../components/cards/ModelComparisonCard';
import { ALL_MODELS, type ModelId } from '../../services/api/modelsApi';

import { useQuery } from '@tanstack/react-query';
import { fetchDashboardMetrics } from '../../services/api/metricsApi';
import { fetchActiveEvents } from '../../services/api/eventsApi';

const Dashboard: React.FC = () => {
  const [selectedModelId, setSelectedModelId] = useState<ModelId>('adaptive_federated');

  const { data: metrics, isLoading: isMetricsLoading, isError: isMetricsError } = useQuery({
    queryKey: ['metrics'],
    queryFn: fetchDashboardMetrics
  });

  const { data: events, isLoading: isEventsLoading, isError: isEventsError } = useQuery({
    queryKey: ['events'],
    queryFn: fetchActiveEvents
  });

  const activeModel = ALL_MODELS.find(m => m.id === selectedModelId) || ALL_MODELS[0];

  return (
    <PageContainer>
      <PageHeader 
        title="Research Overview" 
        description="FedRouteAI Complete Lifecycle & Multi-Model Telemetry" 
      />

      {/* 1. Animated Research Workflow */}
      <PipelineDiagram />

      {/* 2. Model Overview Banner & Selection */}
      <div className="bg-surface border border-border rounded-lg p-5 mb-6 bg-gradient-to-r from-surface via-surface to-primary/5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/60 pb-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-primary/10 text-primary rounded-lg border border-primary/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                Active Architecture: <span className="text-primary">{activeModel.label}</span>
              </h2>
              <p className="text-xs text-textSecondary">{activeModel.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {ALL_MODELS.map(m => (
              <button
                key={m.id}
                onClick={() => setSelectedModelId(m.id)}
                className={px-3 py-1.5 rounded-md text-xs font-semibold transition-all border }
              >
                {m.shortLabel}
              </button>
            ))}
          </div>
        </div>

        {/* Model Metrics Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-surface/80 p-3 rounded-md border border-border">
            <div className="text-[11px] text-textSecondary font-mono uppercase">Global Accuracy</div>
            <div className="text-lg font-bold text-white">{(activeModel.metrics.accuracy * 100).toFixed(2)}%</div>
          </div>
          <div className="bg-surface/80 p-3 rounded-md border border-border">
            <div className="text-[11px] text-textSecondary font-mono uppercase">Macro F1 Score</div>
            <div className="text-lg font-bold text-white">{activeModel.metrics.macro_f1.toFixed(4)}</div>
          </div>
          <div className="bg-surface/80 p-3 rounded-md border border-border">
            <div className="text-[11px] text-textSecondary font-mono uppercase">ROC AUC Macro</div>
            <div className="text-lg font-bold text-success">{activeModel.metrics.roc_auc_macro.toFixed(4)}</div>
          </div>
          <div className="bg-surface/80 p-3 rounded-md border border-border">
            <div className="text-[11px] text-textSecondary font-mono uppercase">Total Models</div>
            <div className="text-lg font-bold text-textPrimary">{ALL_MODELS.length} Evaluated</div>
          </div>
        </div>
      </div>

      {/* 3. Statistics Cards Grid */}
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
            <StatCard title="System Health" value={metrics.system_health} icon={ShieldCheck} />
            <StatCard title="Training Rounds" value={30} icon={Cpu} />
          </>
        ) : null}
      </div>

      {/* 4. Lower Section: Comparison, Events, Map Placeholder (Map remains untouched) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Model Comparison */}
        <div className="lg:col-span-1 space-y-6">
          <ModelComparisonCard
            selectedModelId={selectedModelId}
            onSelectModel={(id) => setSelectedModelId(id)}
          />
          
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

        {/* Right Column: Live Traffic Map (Untouched Map Placeholder) */}
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