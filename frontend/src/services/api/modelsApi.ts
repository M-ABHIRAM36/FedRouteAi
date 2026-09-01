import axios from 'axios';

export type ModelId = 'adaptive_federated' | 'federated' | 'centralized';

export interface ModelInfo {
  id: ModelId;
  label: string;
  shortLabel: string;
  description: string;
  tag: string;
  tagColor: 'green' | 'blue' | 'gray';
  artifactPath: string;
  metrics: {
    accuracy: number;
    macro_f1: number;
    roc_auc_macro: number;
    round?: number;
  };
}

export const ALL_MODELS: ModelInfo [] = [
  {
    id: 'adaptive_federated',
    label: 'AdaptiveFedAvg (Proposed)',
    shortLabel: 'AdaptiveFedAvg',
    description: '8-client federated model with dynamic 4-factor adaptive weighting (n_k ´ q_k ´ ρ_k ´ g_k)',
    tag: 'Best Accuracy & Robustness',
    tagColor: 'green',
    artifactPath: 'adaptive_federated',
    metrics: {
      accuracy: 0.8221,
      macro_f1: 0.6401,
      roc_auc_macro: 0.9720,
      round: 27
    }
  },
  {
    id: 'federated',
    label: 'Standard FedAvg',
    shortLabel: 'FedAvg',
    description: 'B-client federated baseline using standard sample-count weighted parameter averaging',
    tag: 'Federated Baseline',
    tagColor: 'blue',
    artifactPath: 'federated',
    metrics: {
      accuracy: 0.8205,
      macro_f1: 0.6417,
      roc_auc_macro: 0.9720,
      round: 28
    }
  },
  {
    id: 'centralized',
    label: 'Centralized MLP',
    shortLabel: 'Centralized',
    description: 'Standalone EventClassifierMLP trained on pooled global dataset without federated privacy',
    tag: 'Centralized Baseline',
    tagColor: 'gray',
    artifactPath: 'centralized',
    metrics: {
      accuracy: 0.8099,
      macro_f1: 0.6291,
      roc_auc_macro: 0.9759
    }
  }
];

const ARTIFACTS_BASE = 'http://localhost:8000/artifacts';

export const fetchModelMetrics = async (modelId: ModelId) => {
  const model = ALL_MODELS.find(m => m.id === modelId);
  if (!model) throw new Error(`Uncnown model: ${modelId}`);
  try {
    const url = `${ARTIFACTS_BASE}/${model.artifactPath}/metrics.json`;
    const response = await axios.get(url);
    return { ...model.metrics, ...response.data };
  } catch (err) {
    return model.metrics;
  }
};
