import axios from 'axios';
import { ModelId } from './modelsApi';

export interface FigureData {
  src: string;
  title: string;
  caption?: string;
  observation?: string;
}

export interface AnalysisData {
  reportMarkdown: string;
  figures: FigureData[];
}

const ARTIFACTS_BASE = 'http://localhost:8000/artifacts';

const CANDIDATE_FIGURES = [
  { filename: 'weight_evolution.png', title: 'Weight Evolution', caption: 'Evolution of adaptive weights across training rounds' },
  { filename: 'quality_vs_weight.png', title: 'Quality vs Weight', caption: 'Scatter plot of client quality vs assigned weights' },
  { filename: 'heatmap_weights.png', title: 'Weight Heatmap', caption: 'Heatmap of client weights across all rounds' },
  { filename: 'rarity_bonus_distribution.png', title: 'Rarity Bonus Distribution', caption: 'Distribution of class rarity multipliers' },
  { filename: 'gate_distribution.png', title: 'Gate Distribution', caption: 'Activations of the reliability gate' },
];

export const fetchAnalysisData = async (modelId: ModelId = 'adaptive_federated'): Promise<AnalysisData> => {
  let reportMarkdown = '';
  try {
    const reportRes = await axios.get(`${ARTIFACTS_BASE}/${modelId}/analysis/analysis_report.md`);
    reportMarkdown = reportRes.data;
  } catch (error) {
    try {
      const fallbackRes = await axios.get(`${ARTIFACTS_BASE}/adaptive_federated/analysis/analysis_report.md`);
      reportMarkdown = fallbackRes.data;
    } catch (e) {
      reportMarkdown = `# ${modelId} Analysis Report\n\nReport generated for ${modelId}.`;
    }
  }

  const figures: FigureData[] = [];
  
  await Promise.all(CANDIDATE_FIGURES.map(async (candidate) => {
    const url = `${ARTIFACTS_BASE}/${modelId}/analysis/${candidate.filename}`;
    try {
      await axios.head(url);
      figures.push({
        src: url,
        title: candidate.title,
        caption: candidate.caption
      });
    } catch (e) {
      try {
        const fallbackUrl = `${ARTIFACTS_BASE}/adaptive_federated/analysis/${candidate.filename}`;
        await axios.head(fallbackUrl);
        figures.push({
          src: fallbackUrl,
          title: candidate.title,
          caption: candidate.caption
        });
      } catch (err) {}
    }
  }));

  const sortedFigures = figures.sort((a, b) => {
    const idxA = CANDIDATE_FIGURES.findIndex(c => a.src.includes(c.filename));
    const idxB = CANDIDATE_FIGURES.findIndex(c => b.src.includes(c.filename));
    return idxA - idxB;
  });

  return {
    reportMarkdown,
    figures: sortedFigures
  };
};
