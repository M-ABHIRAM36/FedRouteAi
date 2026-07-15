"""
Local Model (per region)
---------------------------
What each Flower client trains. Deliberately simple for Phase 1: rather
than a neural net, the "model" is just a mean/std vector per behavioral
feature (speed_ratio, density_ratio, uturn_ratio, variance_ratio) — i.e.
a learned Gaussian baseline of "what normal looks like" for this
region. This is enough to make deviation scoring work end-to-end AND
it's trivially expressible as the flat numpy arrays Flower's
`get_parameters`/`set_parameters` expect.

TODO: once Phase 1 is working end-to-end, this is the natural place to
swap in something with more capacity (small MLP / gradient-boosted
model per segment cluster) — the NumPyClient wrapper in flower_client.py
shouldn't need to change, only what's inside this class.
"""
import numpy as np
from dataclasses import dataclass


N_FEATURES = 4  # speed_ratio, density_ratio, uturn_ratio, variance_ratio


@dataclass
class LocalModel:
    mean: np.ndarray
    std: np.ndarray
    n_samples: int = 0

    @classmethod
    def initial(cls) -> "LocalModel":
        return cls(mean=np.ones(N_FEATURES, dtype=np.float32),
                    std=np.ones(N_FEATURES, dtype=np.float32) * 0.2,
                    n_samples=0)

    def get_parameters(self) -> list[np.ndarray]:
        return [self.mean, self.std]

    def set_parameters(self, params: list[np.ndarray]) -> None:
        self.mean, self.std = params[0], params[1]

    def fit(self, X: np.ndarray) -> float:
        """X: (n_samples, N_FEATURES) matrix of behavioral signature
        ratios observed on THIS region's segments during "normal" hours.
        Returns a loss proxy (mean negative log-likelihood under the
        fitted Gaussian) so Flower has something to log/aggregate."""
        self.mean = X.mean(axis=0).astype(np.float32)
        self.std = (X.std(axis=0) + 1e-3).astype(np.float32)
        self.n_samples = len(X)
        z = (X - self.mean) / self.std
        loss = float(np.mean(0.5 * z ** 2))
        return loss

    def deviation_score(self, x: np.ndarray) -> float:
        """How many (weighted) standard deviations `x` is from this
        model's learned normal — this feeds signature_extractor-style
        anomaly scoring at inference time."""
        z = (x - self.mean) / self.std
        return float(np.sqrt(np.mean(z ** 2)))
