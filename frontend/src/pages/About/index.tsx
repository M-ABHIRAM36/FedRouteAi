import React from 'react';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { MarkdownViewer } from '../../components/common/MarkdownViewer';

const aboutContent = `
## Motivation
Urban traffic congestion and road events lead to significant economic and environmental losses. Existing routing systems rely on centralized data collection, which raises severe privacy concerns. **FedRouteAI** introduces a privacy-preserving alternative for traffic analysis using Federated Learning.

## Problem Statement
Traditional traffic prediction models require centralizing sensitive GPS trajectories from user vehicles. This creates privacy risks. Additionally, rare road events (like Floods or Construction) are often washed out by the majority class (Normal traffic) during model training, leading to poor predictions in critical scenarios.

## Proposed Solution: AdaptiveFedAvg
FedRouteAI solves this using a novel algorithm called **AdaptiveFedAvg**.
1. **Federated Learning:** Vehicles (or regional edge servers) train models locally and only share model weights, not raw GPS data.
2. **Quality EMA:** The global server tracks an Exponential Moving Average (EMA) of each region's model quality.
3. **Reliability Gate:** Regions submitting degraded or anomalous updates are temporarily gated (filtered out).
4. **Rare Event Bonus (\`beta\`):** Regions experiencing rare events (e.g., Accidents) receive a weight boost to ensure the global model learns these critical patterns.

## Architecture
- **Backend:** FastAPI, Flower (Federated Learning framework), PyTorch.
- **Frontend:** React 18, Vite, Tailwind CSS, Recharts, React-Leaflet.
- **Dataset:** Synthetic 1,000,000+ trajectory GPS points over a simulated Hyderabad road network.

## Limitations & Future Scope
- **Current Limitation:** The dataset is synthetically generated using SUMO-like logic, which may not perfectly capture complex human driving psychology.
- **Future Scope:** Integration with live edge-devices (smartphones) for real-world federated deployment; support for asynchronous federated learning.
`;

const About: React.FC = () => {
  return (
    <PageContainer>
      <PageHeader 
        title="About FedRouteAI" 
        description="Project Documentation & Research Methodology" 
      />

      <div className="bg-surface border border-border rounded-lg p-6 max-w-4xl">
        <MarkdownViewer content={aboutContent} />
      </div>
    </PageContainer>
  );
};

export default About;
