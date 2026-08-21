import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PredictionResult } from './PredictionResult';

describe('PredictionResult', () => {
  it('renders real API probabilities in descending order', () => {
    render(<PredictionResult result={{
      prediction: 'road_block',
      confidence: 0.72,
      probabilities: { normal: 0.18, road_block: 0.72, flood: 0.1 },
      inference_time_ms: 4.2,
    }} />);

    expect(screen.getAllByText('road block').length).toBeGreaterThan(0);
    expect(screen.getAllByText('72.0%').length).toBeGreaterThan(0);
    expect(screen.getByText('18.0%')).toBeInTheDocument();
    expect(screen.getByText('10.0%')).toBeInTheDocument();
    expect(screen.getByText('API probabilities')).toBeInTheDocument();
  });

  it('treats lowercase normal as the non-event class', () => {
    const { container } = render(<PredictionResult result={{ prediction: 'normal', confidence: 0.9, probabilities: {}, inference_time_ms: 2 }} />);
    expect(screen.getByText('normal')).toBeInTheDocument();
    expect(container.querySelector('.lucide-shield-check')).toBeInTheDocument();
    expect(screen.getByText(/no class probabilities/i)).toBeInTheDocument();
  });
});
