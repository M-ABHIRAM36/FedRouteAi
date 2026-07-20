import axios from 'axios';

export interface ArtifactFile {
  title: string;
  filename: string;
  url: string;
}

const ARTIFACTS_BASE = 'http://localhost:8000/artifacts';

const KNOWN_ARTIFACTS = [
  { title: 'Global Model Weights', filename: 'best_global_model.pt' },
  { title: 'Global Metrics', filename: 'metrics.json' },
  { title: 'Experiment Config', filename: 'config.json' },
  { title: 'Classification Report', filename: 'classification_report.txt' },
  { title: 'Training History', filename: 'adaptive_history.csv' },
  { title: 'Adaptive Weights Log', filename: 'adaptive_weights.csv' },
  { title: 'Per-Client Metrics', filename: 'client_metrics.csv' },
  { title: 'Confusion Matrix', filename: 'confusion_matrix.csv' },
  { title: 'ROC AUC Scores', filename: 'roc_auc.json' },
];

export const fetchAvailableArtifacts = async (): Promise<ArtifactFile[]> => {
  const available: ArtifactFile[] = [];

  await Promise.all(
    KNOWN_ARTIFACTS.map(async (artifact) => {
      const url = `${ARTIFACTS_BASE}/${artifact.filename}`;
      try {
        await axios.head(url);
        available.push({ ...artifact, url });
      } catch (err) {
        // Artifact not found, do not include
      }
    })
  );

  if (available.length === 0) {
    throw new Error('No artifacts found. Ensure backend is running and training is complete.');
  }

  // Preserve ordering based on known list
  return available.sort((a, b) => {
    const idxA = KNOWN_ARTIFACTS.findIndex(c => c.filename === a.filename);
    const idxB = KNOWN_ARTIFACTS.findIndex(c => c.filename === b.filename);
    return idxA - idxB;
  });
};
