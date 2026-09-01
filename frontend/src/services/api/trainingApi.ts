import axios from 'axios';
import Papa from 'papaparse';
import { type ModelId } from './modelsApi';

export interface TrainingHistoryPoint {
  Round: number;
  Loss: number;
  Accuracy: number;
  MacroF1: number;
}

export interface TrainingMetrics {
  round: number;
  accuracy: number;
  macro_f1: number;
  roc_auc_macro: number;
}

export interface TrainingData {
  history: TrainingHistoryPoint[];
  metrics: TrainingMetrics;
  reportText: string;
}

const ARTIFACTS_BASE = 'http://localhost:8000/artifacts';

export const fetchTrainingData = async (modelId: ModelId = 'adaptive_federated'): Promise<TrainingData> => {
  try {
    const historyFile = modelId === 'centralized' ? 'training_history.csv' : 'adaptive_history.csv';
    const [historyRes, metricsRes, reportRes] = await Promise.all([
      axios.get(`${ARTIFACTS_BASE}/${modelId}/${historyFile}`).catch(() => axios.get(`${ARTIFACTS_BASE}/adaptive_federated/adaptive_history.csv`)),
      axios.get(`${ARTIFACTS_BASE}/${modelId}/metrics.json`).catch(() => axios.get(`${ARTIFACTS_BASE}/adaptive_federated/metrics.json`)),
      axios.get(`${ARTIFACTS_BASE}/${modelId}/classification_report.txt`).catch(() => axios.get(`${ARTIFACTS_BASE}/adaptive_federated/classification_report.txt`))
    ]);

    const history = await new Promise<TrainingHistoryPoint[]>((resolve, reject) => {
      Papa.parse<any>(historyRes.data, {
        header: true,
        dynamicTyping: true,
        skipEmptyLines: true,
        complete: (results) => {
          if (!results.data || results.data.length === 0) {
            reject(new Error("No history data"));
            return;
          }
          const parsed = results.data.map((row: any) => ({
            Round: row.Round || row.Epoch || 0,
            Loss: row['Global Loss'] ?? row['Loss'] ?? row['Train Loss'] ?? 0,
            Accuracy: row['Global Accuracy'] ?? row['Accuracy'] ?? row['Train Accuracy'] ?? 0,
            MacroF1: row['Global Macro F1'] ?? row['Macro F1'] ?? row['MacroF1'] ?? 0
          }));
          resolve(parsed);
        },
        error: (err: Error) => reject(err)
      });
    });

    return {
      history,
      metrics: metricsRes.data,
      reportText: reportRes.data
    };
  } catch (error) {
    throw new Error('Failed to load training artifacts from the backend.');
  }
};
