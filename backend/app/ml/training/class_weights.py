"""
Class Weight Computation
--------------------------
Inverse-frequency weighting to address the severe label imbalance in the
FedRouteAI dataset (normal >> construction_neighbor >> ... >> diversion).

Used by:
  train_baseline_xgboost.py  — via sample_weight in XGBoost
  mlp_model.py               — via torch.nn.CrossEntropyLoss(weight=...)
  flower_client.py           — computed per region before each local training round
"""
from __future__ import annotations

import numpy as np
from sklearn.utils.class_weight import compute_class_weight


def compute_class_weights(
    labels: np.ndarray,
    n_classes: int,
    normalize: bool = True,
) -> np.ndarray:
    """Compute inverse-frequency class weights.

    Args:
        labels:    1D array of integer class indices (0-based).
        n_classes: Total number of classes (including any that may be absent
                   in this particular sample — e.g. per-region subsets may
                   lack some rare events).
        normalize: If True (default), rescale so that mean weight = 1.0.
                   This keeps the learning rate stable regardless of imbalance.

    Returns:
        (n_classes,) float32 array. Classes absent in `labels` receive
        weight 1.0 (not 0.0) — we don't penalize classes we've never seen,
        we just don't have signal for them.

    Example:
        >>> weights = compute_class_weights(y_train, n_classes=8)
        >>> # XGBoost: sample_weight = weights[y_train]
        >>> # PyTorch:  loss_fn = nn.CrossEntropyLoss(weight=torch.tensor(weights))
    """
    present_classes = np.unique(labels)
    weights = np.ones(n_classes, dtype=np.float32)

    if len(present_classes) < 2:
        # Only one class present (degenerate case, e.g. tiny region) — uniform
        return weights

    sklearn_weights = compute_class_weight(
        class_weight="balanced",
        classes=present_classes,
        y=labels,
    )
    for cls_idx, w in zip(present_classes, sklearn_weights):
        weights[int(cls_idx)] = float(w)

    if normalize:
        mean_w = weights[present_classes].mean()
        if mean_w > 0:
            weights = weights / mean_w

    return weights.astype(np.float32)


def sample_weights_from_class_weights(
    labels: np.ndarray,
    class_weights: np.ndarray,
) -> np.ndarray:
    """Map per-class weights to per-sample weights for XGBoost's sample_weight."""
    return class_weights[labels].astype(np.float32)
