import React from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { MarkdownViewer } from '../../components/common/MarkdownViewer';

const aboutContent = `
## Motivation
Urban traffic congestion and spatial routing events lead to severe economic losses and high carbon emissions. Traditional traffic navigation relies on centralized data collection, which exposes sensitive user GPS trajectories to privacy risks. **FedRouteAI** introduces a privacy-preserving dynamic federated framework for real-time traffic classification and optimal route guidance.

## Problem Statement
1. **Privacy Concerns:** Centralizing raw user GPS trajectories risks severe user tracking and privacy leaks.
2. **Extreme Class Imbalance:** Severe road incidents (Floods, Accidents, Blockades) are rare (~0.1% of data) compared to Normal traffic (>99%), causing standard models to miss critical events.
3. **Non-IID Regional Data:** Traffic patterns differ drastically across urban zones (commercial vs residential), degrading standard parameter-averaging federated models.

## Evaluated Model Architectures

FedRouteAI comprehensively evaluates **4 key model configurations**:

1. **AdaptiveFedAvg (Proposed)**
   - Dynamic 4-factor adaptive weighting ($w_k \propto n_k \cdot q_k \cdot \rho_k \cdot g_k$)
   - 8-client federated training over 30 communication rounds
   - Achieves **82.21% Global Accuracy**, **0.6401 Macro F1**, and **0.9720 ROC AUC** with zero raw data sharing.

2. **Geo V2 Enhanced Model (OSM Real Topology)**
   - Real OpenStreetMap (OSM) road network topology with 10-feature spatial contract & temporal sliding windows.
   - Evaluated on **332,416 real-world test samples**.
   - Achieves **83.50% Global Accuracy**, **0.6580 Macro F1**, and **0.9785 ROC AUC** (Weighted F1: 0.9958).

3. **Standard FedAvg (Federated Baseline)**
   - Standard sample-count proportional parameter averaging ($w_k = n_k / N$).
   - Achieves **82.05% Global Accuracy** and **0.6417 Macro F1**.

4. **Centralized MLP (Centralized Baseline)**
   - Standalone EventClassifierMLP trained on full pooled global dataset without privacy protection.
   - Achieves **80.99% Global Accuracy** and **0.6291 Macro F1**.

## Technology Stack
- **Backend Framework:** FastAPI, PyTorch, Flower (Federated Framework), NetworkX, OpenStreetMap (OSM).
- **Frontend Dashboard:** React 18, Vite, TypeScript, Tailwind CSS, Recharts, React-Query.
- **Payload & Efficiency:** Compact MLP architecture (3,240 parameters, 12.96 KB per round).
`;

const About: React.FC = () => {
  return (
    <PageContainer>
      <PageHeader 
        title="About FedRouteAI" 
        description="Project Documentation, Multi-Model Methodology & System Architecture" 
      />

      <div className="bg-surface border border-border rounded-lg p-6 max-w-4xl">
        <MarkdownViewer content={aboutContent} />
      </div>
    </PageContainer>
  );
};

export default About;