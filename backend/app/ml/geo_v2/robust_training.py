"""Validation-only Geo V2 candidate training and one-time final evaluation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import time
import csv
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from torch import nn

from app.ml.geo_v2.dataset import DATASET_VERSION, LABEL_MAPPING
from app.ml.geo_v2.features import FEATURE_VARIANTS, reject_forbidden_columns
from app.ml.geo_v2.training import (
    EXPECTED_REGIONS, N_CLASSES, ArrayDataset, GeoV2EventClassifierMLP,
    RegionalClient, TrainingConfig, aggregate_client_updates, frame_to_arrays,
    load_dataset_metadata, load_ndarrays_into_model, predict_probabilities,
    seed_everything, state_dict_to_ndarrays,
)
from app.ml.training.adaptive_fedavg import AdaptiveFedAvg


LABELS = tuple(name for name, _ in sorted(LABEL_MAPPING.items(), key=lambda item: item[1]))
ROBUST_FEATURE_VARIANTS = {
    "history_current": FEATURE_VARIANTS["history_current"],
    "history_spatial_strong": [*FEATURE_VARIANTS["history_current"], "neighbor_speed_delta"],
    "history_spatial": FEATURE_VARIANTS["history_spatial"],
}
SELECTION_RULE = {
    "primary": "deployment_validation_macro_f1",
    "constraints": {
        "normal_false_positive_rate_max": 0.05,
        "anomaly_recall_min": 0.20,
        "event_balanced_macro_f1_min": 0.30,
    },
    "tie_breakers": ["event_balanced_macro_f1", "anomaly_recall", "normal_specificity"],
    "reason": "Macro F1 protects all classes; hard gates reject normal-only and event-heavy collapse.",
}


@dataclass(frozen=True)
class RobustTrainingConfig:
    seed: int = 42
    feature_variant: str = "history_current"
    target_local_anomaly_fraction: float = 0.02
    loss: str = "unweighted_nll"
    class_weight_power: float = 0.5
    class_weight_cap: float = 10.0
    hidden_size: int = 64
    dropout_rate: float = 0.2
    optimizer: str = "AdamW"
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 256
    rounds: int = 30
    local_epochs: int = 2
    patience: int = 6
    minimum_rounds: int = 12
    csv_chunk_size: int = 50_000
    alpha: float = 0.3
    beta: float = 0.3
    q_floor: float = 0.10
    g_threshold: float = 0.15
    g_min: float = 0.50
    rare_threshold: float = 0.05
    minimum_client_weight: float = 0.03
    maximum_client_weight: float = 0.22

    def validate(self) -> None:
        if self.feature_variant not in ROBUST_FEATURE_VARIANTS:
            raise ValueError(f"unknown feature variant: {self.feature_variant}")
        if not 0 < self.target_local_anomaly_fraction < 0.5:
            raise ValueError("target_local_anomaly_fraction must be between 0 and 0.5")
        if self.loss not in {"unweighted_nll", "power_weighted_nll"}:
            raise ValueError("loss must be unweighted_nll or power_weighted_nll")
        if self.rounds < 1 or self.local_epochs < 1 or self.batch_size < 2:
            raise ValueError("rounds, local_epochs, and batch_size must be positive")
        if self.minimum_rounds > self.rounds or self.patience < 1:
            raise ValueError("early-stopping configuration is invalid")
        if self.minimum_client_weight * len(EXPECTED_REGIONS) > 1 or self.maximum_client_weight * len(EXPECTED_REGIONS) < 1:
            raise ValueError("client weight bounds cannot form a normalized distribution")


def _rank(row_id: str, seed: int) -> int:
    return int.from_bytes(hashlib.blake2b(f"{seed}:{row_id}".encode(), digest_size=8).digest(), "big")


def read_split(path: Path, split: str, features: Sequence[str], chunk_size: int) -> pd.DataFrame:
    if path.name != f"{split}.csv" or split not in {"train", "validation", "test"}:
        raise ValueError("split path and declared split must match")
    columns = ["row_id", "split", "region_id", *features, "label", "label_idx"]
    parts = []
    for chunk in pd.read_csv(path, usecols=columns, chunksize=chunk_size):
        if set(chunk["split"].astype(str)) != {split}:
            raise ValueError(f"{split} table contains another split")
        expected = chunk["label"].map(LABEL_MAPPING)
        if expected.isna().any() or not np.array_equal(expected.to_numpy(), chunk["label_idx"].to_numpy()):
            raise ValueError("invalid labels")
        if chunk[list(features)].isna().any().any():
            raise ValueError("missing feature values")
        parts.append(chunk)
    frame = pd.concat(parts, ignore_index=True)
    if set(frame["region_id"].astype(str)) != set(EXPECTED_REGIONS):
        raise ValueError("all eight geographic clients are required")
    return frame


def sample_client_aware(
    frame: pd.DataFrame, *, target_anomaly_fraction: float, seed: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Keep physical events once and sample normals independently inside each region."""
    sampled = []
    clients: dict[str, Any] = {}
    for offset, region in enumerate(EXPECTED_REGIONS):
        local = frame.loc[frame["region_id"] == region]
        events = local.loc[local["label_idx"] != LABEL_MAPPING["normal"]]
        normals = local.loc[local["label_idx"] == LABEL_MAPPING["normal"]].copy()
        required = int(np.ceil(len(events) * (1 - target_anomaly_fraction) / target_anomaly_fraction))
        retained = min(required, len(normals))
        normals["_rank"] = normals["row_id"].astype(str).map(lambda value: _rank(value, seed + offset))
        normals = normals.nsmallest(retained, "_rank").drop(columns="_rank")
        local_sample = pd.concat([events, normals], ignore_index=True)
        if local_sample["row_id"].duplicated().any():
            raise ValueError("sampling duplicated physical rows")
        sampled.append(local_sample)
        counts = local_sample["label_idx"].value_counts().reindex(range(N_CLASSES), fill_value=0)
        clients[region] = {
            "physical_rows": int(len(local_sample)), "event_rows": int(len(events)),
            "normal_rows": int(len(normals)), "event_fraction": float(len(events) / len(local_sample)),
            "class_counts": {LABELS[index]: int(counts[index]) for index in range(N_CLASSES)},
        }
    result = pd.concat(sampled, ignore_index=True).sort_values("row_id", kind="stable").reset_index(drop=True)
    if result["row_id"].duplicated().any():
        raise ValueError("sampling introduced cross-client duplicates")
    original_events = set(frame.loc[frame["label_idx"] != 0, "row_id"])
    if set(result.loc[result["label_idx"] != 0, "row_id"]) != original_events:
        raise ValueError("sampling must preserve every event exactly once")
    return result, {
        "method": "all physical event rows once plus lowest blake2b-ranked normal rows per geographic region",
        "seed": seed, "target_local_anomaly_fraction": target_anomaly_fraction,
        "normal_rows": int((result["label_idx"] == 0).sum()),
        "event_rows": int((result["label_idx"] != 0).sum()), "total_rows": int(len(result)),
        "effective_anomaly_fraction": float((result["label_idx"] != 0).mean()), "clients": clients,
        "event_duplication": False, "geographic_rows_moved": False,
    }


def make_diagnostic_view(data: ArrayDataset, seed: int) -> ArrayDataset:
    event_indices = np.flatnonzero(data.labels != 0)
    normal_indices = np.flatnonzero(data.labels == 0)
    selected_normals = sorted(normal_indices, key=lambda index: _rank(data.row_ids[index], seed))[:len(event_indices)]
    chosen = np.sort(np.concatenate([event_indices, np.asarray(selected_normals)]))
    mask = np.zeros(len(data), dtype=bool)
    mask[chosen] = True
    return data.subset(mask)


def classification_metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    predictions = probabilities.argmax(axis=1)
    precision, recall, class_f1, support = precision_recall_fscore_support(
        labels, predictions, labels=np.arange(N_CLASSES), zero_division=0,
    )
    actual_anomaly = labels != 0
    predicted_anomaly = predictions != 0
    true_anomaly = int((actual_anomaly & predicted_anomaly).sum())
    false_anomaly = int((~actual_anomaly & predicted_anomaly).sum())
    missed_anomaly = int((actual_anomaly & ~predicted_anomaly).sum())
    true_normal = int((~actual_anomaly & ~predicted_anomaly).sum())
    anomaly_precision = true_anomaly / max(true_anomaly + false_anomaly, 1)
    anomaly_recall = true_anomaly / max(true_anomaly + missed_anomaly, 1)
    return {
        "rows": int(len(labels)), "accuracy": float(accuracy_score(labels, predictions)),
        "macro_precision": float(np.mean(precision)), "macro_recall": float(np.mean(recall)),
        "macro_f1": float(f1_score(labels, predictions, labels=np.arange(N_CLASSES), average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(labels, predictions, average="weighted", zero_division=0)),
        "normal": {"precision": float(precision[0]), "recall": float(recall[0]), "specificity": float(true_normal / max(true_normal + false_anomaly, 1)), "false_positive_rate": float(false_anomaly / max(true_normal + false_anomaly, 1)), "false_positives": false_anomaly, "false_positives_per_100000": float(false_anomaly / max((labels == 0).sum(), 1) * 100_000)},
        "anomaly": {"precision": float(anomaly_precision), "recall": float(anomaly_recall), "f1": float(2 * anomaly_precision * anomaly_recall / max(anomaly_precision + anomaly_recall, 1e-12))},
        "per_class": {LABELS[index]: {"precision": float(precision[index]), "recall": float(recall[index]), "f1": float(class_f1[index]), "support": int(support[index])} for index in range(N_CLASSES)},
        "confusion_matrix": confusion_matrix(labels, predictions, labels=np.arange(N_CLASSES)).tolist(),
        "prediction_counts": {LABELS[index]: int((predictions == index).sum()) for index in range(N_CLASSES)},
    }


def effective_class_weights(labels: np.ndarray, config: RobustTrainingConfig) -> np.ndarray:
    if config.loss == "unweighted_nll":
        return np.ones(N_CLASSES, dtype=np.float32)
    counts = np.bincount(labels, minlength=N_CLASSES).astype(float)
    present = counts > 0
    weights = np.ones(N_CLASSES, dtype=float)
    weights[present] = (counts[present].sum() / (present.sum() * counts[present])) ** config.class_weight_power
    weights[present] /= weights[present].mean()
    return np.minimum(weights, config.class_weight_cap).astype(np.float32)


def _training_config(config: RobustTrainingConfig) -> TrainingConfig:
    return TrainingConfig(
        seed=config.seed, hidden_size=config.hidden_size, dropout_rate=config.dropout_rate,
        optimizer=config.optimizer, learning_rate=config.learning_rate, weight_decay=config.weight_decay,
        batch_size=config.batch_size, rounds=config.rounds, local_epochs=config.local_epochs,
        alpha=config.alpha, beta=config.beta, q_floor=config.q_floor, g_threshold=config.g_threshold,
        g_min=config.g_min, rare_threshold=config.rare_threshold,
    )


def train_local(
    model: GeoV2EventClassifierMLP, data: ArrayDataset, config: RobustTrainingConfig,
    device: torch.device, *, seed: int,
) -> float:
    weights = torch.tensor(effective_class_weights(data.labels, config), device=device)
    criterion = nn.NLLLoss(weight=weights)
    optimizer_type = {"Adam": torch.optim.Adam, "AdamW": torch.optim.AdamW}[config.optimizer]
    optimizer = optimizer_type(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    generator = torch.Generator().manual_seed(seed)
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(torch.from_numpy(data.features), torch.from_numpy(data.labels)),
        batch_size=config.batch_size, shuffle=True, generator=generator,
    )
    model.to(device)
    total_loss = total_rows = 0
    for _ in range(config.local_epochs):
        model.train()
        for features, labels in loader:
            features, labels = features.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(features), labels)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * len(labels)
            total_rows += len(labels)
    return total_loss / max(total_rows, 1)


def bounded_weights(values: Sequence[float], minimum: float, maximum: float) -> np.ndarray:
    weights = np.asarray(values, dtype=float)
    weights = weights / weights.sum() if weights.sum() else np.full(len(weights), 1 / len(weights))
    fixed = np.zeros(len(weights), dtype=bool)
    result = weights.copy()
    for _ in range(len(weights) + 1):
        low = (~fixed) & (result < minimum)
        high = (~fixed) & (result > maximum)
        if not low.any() and not high.any():
            break
        result[low], result[high] = minimum, maximum
        fixed |= low | high
        remaining = ~fixed
        budget = 1.0 - result[fixed].sum()
        if remaining.any():
            source = weights[remaining]
            result[remaining] = budget * source / source.sum()
    result /= result.sum()
    if (result < minimum - 1e-12).any() or (result > maximum + 1e-12).any():
        raise ValueError("failed to project adaptive client weights into bounds")
    return result


def aggregate_stabilized_updates(
    strategy: AdaptiveFedAvg, round_number: int,
    updates: Sequence[tuple[str, Sequence[np.ndarray], int, Mapping[str, Any]]],
    *, minimum: float, maximum: float, log_path: Path,
) -> list[np.ndarray]:
    if len(updates) != len(EXPECTED_REGIONS) or {item[0] for item in updates} != set(EXPECTED_REGIONS):
        raise ValueError("stabilized aggregation requires all eight clients")
    records = []
    raw = []
    for region, _, size, metrics in updates:
        quality = strategy._compute_quality(float(metrics["val_macro_f1"]))
        rarity = strategy._compute_rarity_bonus(float(metrics["rare_class_fraction"]))
        ema = strategy._update_ema(region, float(metrics["val_macro_f1"]))
        gate = strategy._compute_gate(ema)
        value = size * quality * rarity * gate
        raw.append(value)
        records.append({
            "round": round_number, "region_id": region, "dataset_size": size,
            "val_macro_f1": metrics["val_macro_f1"], "ema_f1": ema, "quality": quality,
            "rare_fraction": metrics["rare_class_fraction"], "rarity_bonus": rarity,
            "gate": gate, "raw_weight": value,
        })
    adaptive = np.asarray(raw) / sum(raw)
    effective = bounded_weights(raw, minimum, maximum)
    aggregated = [np.zeros_like(array, dtype=np.result_type(array.dtype, np.float64)) for array in updates[0][1]]
    for weight, (_, arrays, _, _) in zip(effective, updates, strict=True):
        for index, array in enumerate(arrays):
            aggregated[index] += array * weight
    for record, original, weight in zip(records, adaptive, effective, strict=True):
        record["adaptive_weight"] = float(original)
        record["normalized_weight"] = float(weight)
        record["weight_was_bounded"] = bool(abs(original - weight) > 1e-12)
    with log_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        if handle.tell() == 0:
            writer.writeheader()
        writer.writerows(records)
    return aggregated


def validation_record(
    model: GeoV2EventClassifierMLP, deployment: ArrayDataset, diagnostic: ArrayDataset,
    config: RobustTrainingConfig, device: torch.device,
) -> dict[str, Any]:
    deployment_probabilities = predict_probabilities(model, deployment, config.batch_size, device)
    diagnostic_probabilities = predict_probabilities(model, diagnostic, config.batch_size, device)
    deployment_metrics = classification_metrics(deployment.labels, deployment_probabilities)
    diagnostic_metrics = classification_metrics(diagnostic.labels, diagnostic_probabilities)
    return {
        "deployment": deployment_metrics, "event_balanced": diagnostic_metrics,
        "selection_eligible": (
            deployment_metrics["normal"]["false_positive_rate"] <= SELECTION_RULE["constraints"]["normal_false_positive_rate_max"]
            and deployment_metrics["anomaly"]["recall"] >= SELECTION_RULE["constraints"]["anomaly_recall_min"]
            and diagnostic_metrics["macro_f1"] >= SELECTION_RULE["constraints"]["event_balanced_macro_f1_min"]
        ),
    }


def selection_key(record: Mapping[str, Any]) -> tuple[float, ...]:
    if not record["selection_eligible"]:
        return (0.0, -float(record["deployment"]["normal"]["false_positive_rate"]), float(record["event_balanced"]["macro_f1"]))
    return (
        1.0, float(record["deployment"]["macro_f1"]), float(record["event_balanced"]["macro_f1"]),
        float(record["deployment"]["anomaly"]["recall"]), float(record["deployment"]["normal"]["specificity"]),
    )


def hierarchy_dominates_flat(hierarchical: Mapping[str, Any], flat: Mapping[str, Any]) -> bool:
    """Adopt thresholding only when its extra complexity is Pareto-better on declared objectives."""
    if not hierarchical["selection_eligible"]:
        return False
    hierarchical_values = (
        float(hierarchical["deployment"]["macro_f1"]),
        float(hierarchical["event_balanced"]["macro_f1"]),
        float(hierarchical["deployment"]["anomaly"]["recall"]),
    )
    flat_values = (
        float(flat["deployment"]["macro_f1"]),
        float(flat["event_balanced"]["macro_f1"]),
        float(flat["deployment"]["anomaly"]["recall"]),
    )
    return all(candidate >= baseline for candidate, baseline in zip(hierarchical_values, flat_values, strict=True)) and any(
        candidate > baseline for candidate, baseline in zip(hierarchical_values, flat_values, strict=True)
    )


def run_validation_candidate(
    dataset_dir: Path, artifact_root: Path, experiment_id: str, config: RobustTrainingConfig,
) -> Path:
    """Train using only explicit train/validation paths; this function cannot load test."""
    config.validate()
    started = time.perf_counter()
    output = artifact_root / experiment_id
    output.mkdir(parents=True, exist_ok=False)
    derived_manifest_path = dataset_dir / "manifest.json"
    derived_manifest = json.loads(derived_manifest_path.read_text(encoding="utf-8"))
    if derived_manifest.get("dataset_version") == "geo_v2_ml_v1_fixed_contract_v2":
        scaler = json.loads((dataset_dir / "scalers" / "history_spatial.json").read_text(encoding="utf-8"))
        manifest = derived_manifest
    else:
        _, scaler, manifest = load_dataset_metadata(dataset_dir)
    features = ROBUST_FEATURE_VARIANTS[config.feature_variant]
    reject_forbidden_columns(features)
    table_dir = dataset_dir / "feature_tables" / "history_spatial"
    train_full = read_split(table_dir / "train.csv", "train", features, config.csv_chunk_size)
    validation_full = read_split(table_dir / "validation.csv", "validation", features, config.csv_chunk_size)
    train_frame, sampling = sample_client_aware(
        train_full, target_anomaly_fraction=config.target_local_anomaly_fraction, seed=config.seed,
    )
    train_data = frame_to_arrays(train_frame, features)
    validation_data = frame_to_arrays(validation_full, features)
    diagnostic = make_diagnostic_view(validation_data, config.seed + 1)
    train_regions = np.asarray(train_data.regions)
    validation_regions = np.asarray(validation_data.regions)
    clients = {
        region: RegionalClient(region, train_data.subset(train_regions == region), validation_data.subset(validation_regions == region))
        for region in EXPECTED_REGIONS
    }
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    seed_everything(config.seed)
    model = GeoV2EventClassifierMLP(len(features), config.hidden_size, dropout_rate=config.dropout_rate)
    arrays = state_dict_to_ndarrays(model)
    frequencies = np.bincount(train_data.labels, minlength=N_CLASSES) / len(train_data)
    strategy = AdaptiveFedAvg(
        global_class_frequencies={index: float(value) for index, value in enumerate(frequencies)},
        alpha=config.alpha, beta=config.beta, q_floor=config.q_floor, g_threshold=config.g_threshold,
        g_min=config.g_min, rare_threshold=config.rare_threshold,
    )
    history: list[dict[str, Any]] = []
    client_history: list[dict[str, Any]] = []
    checkpoints: list[list[np.ndarray]] = []
    best_index = -1
    stale_rounds = 0
    for round_number in range(1, config.rounds + 1):
        updates = []
        for region, client in clients.items():
            local_model = GeoV2EventClassifierMLP(len(features), config.hidden_size, dropout_rate=config.dropout_rate)
            load_ndarrays_into_model(local_model, arrays)
            loss = train_local(local_model, client.train, config, device, seed=config.seed + round_number * 100 + int(region[-2:]))
            local_probabilities = predict_probabilities(local_model, client.validation, config.batch_size, device)
            local_metrics = classification_metrics(client.validation.labels, local_probabilities)
            metrics = {
                "region_id": region, "train_loss": loss, "val_macro_f1": local_metrics["macro_f1"],
                "rare_class_fraction": float((client.train.labels != 0).mean()), "dataset_size": len(client.train),
                "class_weights": effective_class_weights(client.train.labels, config).tolist(),
            }
            client_history.append({"round": round_number, **metrics})
            updates.append((region, state_dict_to_ndarrays(local_model), len(client.train), metrics))
        arrays = aggregate_stabilized_updates(
            strategy, round_number, updates, minimum=config.minimum_client_weight,
            maximum=config.maximum_client_weight, log_path=output / "adaptive_weights.csv",
        )
        load_ndarrays_into_model(model, arrays)
        record = {"round": round_number, "checkpoint_index": round_number, **validation_record(model, validation_data, diagnostic, config, device)}
        history.append(record)
        checkpoints.append([array.copy() for array in arrays])
        candidate_index = max(range(len(history)), key=lambda index: selection_key(history[index]))
        if candidate_index != best_index:
            best_index, stale_rounds = candidate_index, 0
        else:
            stale_rounds += 1
        if round_number >= config.minimum_rounds and stale_rounds >= config.patience:
            break
    if best_index < 0:
        raise RuntimeError("no validation checkpoint was produced")
    best_model = GeoV2EventClassifierMLP(len(features), config.hidden_size, dropout_rate=config.dropout_rate)
    load_ndarrays_into_model(best_model, checkpoints[best_index])
    final_model = GeoV2EventClassifierMLP(len(features), config.hidden_size, dropout_rate=config.dropout_rate)
    load_ndarrays_into_model(final_model, checkpoints[-1])
    best_record = history[best_index]
    model_version = f"fedrouteai-geo-v2-robust-{experiment_id}-r{best_record['round']:02d}"
    metadata = {
        "input_size": len(features), "hidden_size": config.hidden_size, "dropout_rate": config.dropout_rate,
        "labels": list(LABELS), "label_mapping": LABEL_MAPPING, "ordered_feature_names": list(features),
        "scaler_mean": [float(scaler["mean"][name]) for name in features],
        "scaler_scale": [float(scaler["scale"][name]) for name in features],
        "scaler_fit_split": "train", "tables_are_scaled": True, "model_version": model_version,
        "feature_version": f"geo-v2-{config.feature_variant}-{len(features)}-v2",
        "feature_variant": config.feature_variant, "history_cadence_seconds": 120,
        "baseline_definition": "normal-only segment prehistory mean, fixed from training reference",
        "neighbor_definition": "canonical directed same-timestamp observed outgoing neighbors",
        "dataset_version": manifest["dataset_version"], "source_dataset_version": manifest.get("source_dataset_version", DATASET_VERSION), "network_version": manifest["network_version"],
        "training_config": asdict(config), "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint_metric": {"name": "documented_multi_objective_validation_rule", "value": selection_key(best_record)},
    }
    for filename, selected_model in (("best_model.pt", best_model), ("final_model.pt", final_model)):
        torch.save({**metadata, "state_dict": {name: value.detach().cpu() for name, value in selected_model.state_dict().items()}}, output / filename)
    weights = pd.read_csv(output / "adaptive_weights.csv").to_dict("records")
    provenance = {
        "experiment_id": experiment_id, "dataset_version": manifest["dataset_version"],
        "canonical_dataset_untouched": True, "test_accessed": False,
        "train_path": str(table_dir / "train.csv"), "validation_path": str(table_dir / "validation.csv"),
        "test_path": None, "elapsed_seconds": time.perf_counter() - started,
    }
    _write_json(output / "config.json", asdict(config))
    _write_json(output / "sampling.json", sampling)
    _write_json(output / "client_distributions.json", sampling["clients"])
    _write_json(output / "training_history.json", history)
    _write_json(output / "client_metrics.json", client_history)
    pd.DataFrame(client_history).to_csv(output / "client_metrics.csv", index=False)
    _write_json(output / "adaptive_weights.json", weights)
    _write_json(output / "feature_schema.json", {"variant": config.feature_variant, "ordered_features": features, "feature_version": metadata["feature_version"]})
    _write_json(output / "scaler.json", {"fit_split": "train", "feature_order": features, "mean": {name: scaler["mean"][name] for name in features}, "scale": {name: scaler["scale"][name] for name in features}})
    _write_json(output / "provenance.json", provenance)
    _write_json(output / "validation_selection.json", {"rule": SELECTION_RULE, "selected_round": best_record["round"], "selected": best_record, "accepted": best_record["selection_eligible"]})
    return output


def finalize_once(candidate_dir: Path, test_csv: Path) -> Path:
    """Evaluate one already-selected candidate and refuse repeated test receipts."""
    receipt = candidate_dir / "final_test_receipt.json"
    if receipt.exists():
        raise FileExistsError("final test was already evaluated for this candidate")
    selection = json.loads((candidate_dir / "validation_selection.json").read_text(encoding="utf-8"))
    if not selection.get("accepted"):
        raise ValueError("candidate did not pass validation acceptance criteria")
    payload = torch.load(candidate_dir / "best_model.pt", map_location="cpu", weights_only=False)
    features = payload["ordered_feature_names"]
    frame = read_split(test_csv, "test", features, 50_000)
    data = frame_to_arrays(frame, features)
    diagnostic = make_diagnostic_view(data, int(payload["training_config"]["seed"]) + 2)
    model = GeoV2EventClassifierMLP(len(features), payload["hidden_size"], dropout_rate=payload["dropout_rate"])
    model.load_state_dict(payload["state_dict"], strict=True)
    probabilities = predict_probabilities(model, data, int(payload["training_config"]["batch_size"]), torch.device("cpu"))
    by_row = {row_id: probabilities[index] for index, row_id in enumerate(data.row_ids)}
    diagnostic_probabilities = np.stack([by_row[row_id] for row_id in diagnostic.row_ids])
    metrics = classification_metrics(data.labels, probabilities)
    balanced = classification_metrics(diagnostic.labels, diagnostic_probabilities)
    _write_json(candidate_dir / "metrics.json", {"full_untouched_test": metrics, "event_balanced_test": balanced, "test_evaluation_count": 1})
    _write_confusion_csv(candidate_dir / "confusion_matrix.csv", metrics["confusion_matrix"])
    _write_confusion_csv(candidate_dir / "event_confusion_matrix.csv", np.asarray(metrics["confusion_matrix"])[1:, 1:].tolist(), LABELS[1:])
    pd.DataFrame([{"class": label, **values} for label, values in metrics["per_class"].items()]).to_csv(candidate_dir / "per_class_metrics.csv", index=False)
    _write_json(receipt, {"evaluated_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_sha256": _sha256(candidate_dir / "best_model.pt"), "test_sha256": _sha256(test_csv), "selection_completed_before_test_access": True})
    return receipt


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_confusion_csv(path: Path, matrix: Sequence[Sequence[int]], labels: Sequence[str] = LABELS) -> None:
    pd.DataFrame(matrix, index=labels, columns=labels).rename_axis("actual").to_csv(path)


def evaluate_hierarchical_validation(
    candidate_dir: Path, dataset_dir: Path, *, thresholds: Sequence[float] = (0.25, 0.5, 0.75),
) -> dict[str, Any]:
    """Validation-only two-stage diagnostic using label-free anomaly probability."""
    payload = torch.load(candidate_dir / "best_model.pt", map_location="cpu", weights_only=False)
    features = payload["ordered_feature_names"]
    frame = read_split(
        dataset_dir / "feature_tables" / "history_spatial" / "validation.csv",
        "validation", features, 50_000,
    )
    data = frame_to_arrays(frame, features)
    diagnostic = make_diagnostic_view(data, int(payload["training_config"]["seed"]) + 1)
    model = GeoV2EventClassifierMLP(len(features), payload["hidden_size"], dropout_rate=payload["dropout_rate"])
    model.load_state_dict(payload["state_dict"], strict=True)
    probabilities = predict_probabilities(model, data, int(payload["training_config"]["batch_size"]), torch.device("cpu"))
    probability_by_row = {row_id: probabilities[index] for index, row_id in enumerate(data.row_ids)}
    diagnostic_probabilities = np.stack([probability_by_row[row_id] for row_id in diagnostic.row_ids])
    records = []
    for threshold in thresholds:
        adjusted = probabilities.copy()
        anomaly_score = 1.0 - adjusted[:, 0]
        force_normal = anomaly_score < threshold
        adjusted[force_normal, 1:] = 0.0
        adjusted[~force_normal, 0] = 0.0
        balanced_adjusted = diagnostic_probabilities.copy()
        balanced_score = 1.0 - balanced_adjusted[:, 0]
        balanced_normal = balanced_score < threshold
        balanced_adjusted[balanced_normal, 1:] = 0.0
        balanced_adjusted[~balanced_normal, 0] = 0.0
        deployment = classification_metrics(data.labels, adjusted)
        event_balanced = classification_metrics(diagnostic.labels, balanced_adjusted)
        eligible = (
            deployment["normal"]["false_positive_rate"] <= SELECTION_RULE["constraints"]["normal_false_positive_rate_max"]
            and deployment["anomaly"]["recall"] >= SELECTION_RULE["constraints"]["anomaly_recall_min"]
            and event_balanced["macro_f1"] >= SELECTION_RULE["constraints"]["event_balanced_macro_f1_min"]
        )
        records.append({"threshold": threshold, "selection_eligible": eligible, "deployment": deployment, "event_balanced": event_balanced})
    flat_probabilities = probabilities.copy()
    flat = {
        "selection_eligible": True,
        "deployment": classification_metrics(data.labels, flat_probabilities),
        "event_balanced": classification_metrics(diagnostic.labels, diagnostic_probabilities),
    }
    best_hierarchical = max(records, key=selection_key)
    result = {
        "method": "normal when 1-P(normal) is below validation-only threshold; otherwise argmax over seven events",
        "flat": flat, "candidates": records, "best_hierarchical": best_hierarchical,
        "selection_policy": "hierarchical must Pareto-dominate flat macro F1, event-balanced macro F1, and anomaly recall",
        "selected": "hierarchical" if hierarchy_dominates_flat(best_hierarchical, flat) else "flat",
        "test_accessed": False,
    }
    _write_json(candidate_dir / "hierarchical_validation.json", result)
    return result
