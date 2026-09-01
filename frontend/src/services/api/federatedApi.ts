import axios from 'axios';
import Papa from 'papaparse';
import { ModelId } from './modelsApi';

export interface AdaptiveWeight {
  round: number;
  region_id: string;
  dataset_size: number;
  val_macro_f1: number;
  ema_f1: number;
  quality: number;
  rare_fraction: number;
  rarity_bonus: number;
  gate: number;
  raw_weight: number;
  normalized_weight: number;
}

export interface ChartDataPoint {
  Round: number;
  w_k: number;
  q_k: number;
  rho_k: number;
}

export interface ClientMetric {
  region_id: string;
  quality: number;
  ema_f1: number;
  weight: number;
  samples: number;
  gatePassed: boolean;
}

export interface FederatedSummary {
  chartData: ChartDataPoint[];
  latestClients: ClientMetric[];
}

export const fetchFederatedSummary = async (modelId: ModelId = 'adaptive_federated'): Promise<FederatedSummary> => {
  const targetFolder = modelId === 'geo_v2' ? 'geo_v2' : 'adaptive_federated';
  const response = await axios.get(`http://localhost:8000/artifacts/${targetFolder}/adaptive_weights.csv`);
  
  return new Promise((resolve, reject) => {
    Papa.parse<AdaptiveWeight>(response.data, {
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (results) => {
        const data = results.data;
        if (!data || data.length === 0) {
          reject(new Error("No data in CSV"));
          return;
        }

        const roundMap = new Map<number, { w_k: number, q_k: number, rho_k: number, count: number }>();
        
        data.forEach(row => {
          const r = row.round;
          if (!roundMap.has(r)) {
            roundMap.set(r, { w_k: 0, q_k: 0, rho_k: 0, count: 0 });
          }
          const curr = roundMap.get(r)!;
          curr.w_k += row.normalized_weight || 0;
          curr.q_k += row.quality || 0;
          curr.rho_k += row.ema_f1 || 0;
          curr.count += 1;
        });

        const chartData: ChartDataPoint[] = Array.from(roundMap.entries()).map(([round, stats]) => ({
          Round: round,
          w_k: stats.w_k / (stats.count || 1),
          q_k: stats.q_k / (stats.count || 1),
          rho_k: stats.rho_k / (stats.count || 1),
        })).sort((a, b) => a.Round - b.Round);

        const maxRound = Math.max(...data.map(d => d.round || 0));
        const latestData = data.filter(d => d.round === maxRound);
        
        const latestClients: ClientMetric[] = latestData.map(d => ({
          region_id: String(d.region_id),
          quality: d.quality || 0,
          ema_f1: d.ema_f1 || 0,
          weight: d.normalized_weight || 0,
          samples: d.dataset_size || 0,
          gatePassed: d.gate === 1.0,
        })).sort((a, b) => a.region_id.localeCompare(b.region_id));

        resolve({ chartData, latestClients });
      },
      error: (error: Error) => {
        reject(error);
      }
    });
  });
};
