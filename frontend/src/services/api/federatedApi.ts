import axios from 'axios';
import Papa from 'papaparse';

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

export const fetchFederatedSummary = async (): Promise<FederatedSummary> => {
  const response = await axios.get('http://localhost:8000/artifacts/adaptive_weights.csv');
  
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

        // 1. Group by Round for average w_k, q_k, rho_k (Chart Data)
        const roundMap = new Map<number, { w_k: number, q_k: number, rho_k: number, count: number }>();
        
        data.forEach(row => {
          const r = row.round;
          if (!roundMap.has(r)) {
            roundMap.set(r, { w_k: 0, q_k: 0, rho_k: 0, count: 0 });
          }
          const curr = roundMap.get(r)!;
          curr.w_k += row.normalized_weight;
          curr.q_k += row.quality;
          curr.rho_k += row.ema_f1;
          curr.count += 1;
        });

        const chartData: ChartDataPoint[] = Array.from(roundMap.entries()).map(([round, stats]) => ({
          Round: round,
          w_k: stats.w_k / stats.count,
          q_k: stats.q_k / stats.count,
          rho_k: stats.rho_k / stats.count,
        })).sort((a, b) => a.Round - b.Round);

        // 2. Latest Client Status
        const maxRound = Math.max(...data.map(d => d.round));
        const latestData = data.filter(d => d.round === maxRound);
        
        const latestClients: ClientMetric[] = latestData.map(d => ({
          region_id: d.region_id,
          quality: d.quality,
          ema_f1: d.ema_f1,
          weight: d.normalized_weight,
          samples: d.dataset_size,
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
