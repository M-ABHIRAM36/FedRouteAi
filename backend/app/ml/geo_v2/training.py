"""Additive Geo V2 centralized ablation and in-process federated training."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import random
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import torch
from flwr.common import Code, FitRes, Status, ndarrays_to_parameters, parameters_to_ndarrays
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from app.ml.geo_v2.dataset import DATASET_VERSION, LABEL_MAPPING
from app.ml.geo_v2.features import FEATURE_VARIANTS, METADATA_COLUMNS, reject_forbidden_columns
from app.ml.training.adaptive_fedavg import AdaptiveFedAvg
from app.ml.training.class_weights import compute_class_weights


N_CLASSES = 8
EXPECTED_REGIONS = tuple(f"REGION_{index:02d}" for index in range(1, 9))
CANONICAL_VARIANT = "history_spatial"
REQUIRED_TARGET_COLUMNS = ("label", "label_idx")


@dataclass(frozen=True)
class TrainingConfig:
    seed: int = 42
    hidden_size: int = 64
    dropout_rate: float = 0.2
    optimizer: str = "AdamW"
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 256
    centralized_epochs: int = 8
    rounds: int = 8
    local_epochs: int = 2
    train_normal_cap: int = 5_000
    validation_normal_cap: int = 5_000
    csv_chunk_size: int = 50_000
    alpha: float = 0.3
    beta: float = 0.3
    q_floor: float = 0.10
    g_threshold: float = 0.15
    g_min: float = 0.50
    rare_threshold: float = 0.05


@dataclass(frozen=True)
class ArrayDataset:
    features: np.ndarray
    labels: np.ndarray
    row_ids: tuple[str, ...]
    regions: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.labels)

    def subset(self, mask: np.ndarray) -> "ArrayDataset":
        indices = np.flatnonzero(mask)
        return ArrayDataset(
            self.features[indices], self.labels[indices],
            tuple(self.row_ids[index] for index in indices),
            tuple(self.regions[index] for index in indices),
        )


class GeoV2EventClassifierMLP(nn.Module):
    """V2 tabular MLP; separate from the fixed-contract V1 model."""

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        n_classes: int = N_CLASSES,
        dropout_rate: float = 0.2,
    ) -> None:
        super().__init__()
        if input_size <= 0 or hidden_size < 2 or n_classes != N_CLASSES:
            raise ValueError("Geo V2 MLP requires positive inputs, hidden_size >= 2, and 8 classes")
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.n_classes = n_classes
        self.dropout_rate = dropout_rate
        self.net = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.BatchNorm1d(hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.BatchNorm1d(hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, n_classes),
        )
        for layer in self.modules():
            if isinstance(layer, nn.Linear):
                nn.init.xavier_uniform_(layer.weight)
                nn.init.zeros_(layer.bias)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return torch.log_softmax(self.net(features), dim=-1)

    def predict_proba(self, features: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return self(features).exp()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _stable_rank(value: str, seed: int) -> int:
    digest = hashlib.blake2b(f"{seed}:{value}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def validate_scaler_and_schema(
    schema: Mapping[str, Any], scaler: Mapping[str, Any]
) -> tuple[str, ...]:
    variants = schema.get("variants")
    if variants != FEATURE_VARIANTS:
        raise ValueError("saved feature schema does not match code FEATURE_VARIANTS ordering")
    features = tuple(FEATURE_VARIANTS[CANONICAL_VARIANT])
    reject_forbidden_columns(features, context="Geo V2 training features")
    if scaler.get("fit_split") != "train":
        raise ValueError("scaler was not fit on train")
    if tuple(scaler.get("feature_order", ())) != features:
        raise ValueError("scaler feature order does not match canonical feature order")
    for key in ("mean", "scale"):
        values = scaler.get(key, {})
        if tuple(values) != features or not all(np.isfinite(float(values[name])) for name in features):
            raise ValueError(f"invalid scaler {key} values or ordering")
    if any(float(scaler["scale"][name]) <= 0 for name in features):
        raise ValueError("scaler scales must be positive")
    return features


def load_dataset_metadata(dataset_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    schema = json.loads((dataset_dir / "feature_schema.json").read_text(encoding="utf-8"))
    scaler = json.loads((dataset_dir / "scalers" / "history_spatial.json").read_text(encoding="utf-8"))
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    validate_scaler_and_schema(schema, scaler)
    if manifest.get("dataset_version") != DATASET_VERSION:
        raise ValueError("unexpected Geo V2 dataset version")
    if manifest.get("feature_variants") != FEATURE_VARIANTS:
        raise ValueError("manifest feature variants do not match code")
    return schema, scaler, manifest


def _validate_chunk(chunk: pd.DataFrame, split: str, feature_names: Sequence[str]) -> None:
    if set(chunk["split"].astype(str)) != {split}:
        raise ValueError(f"{split} CSV contains incorrect split labels")
    if chunk[list(feature_names)].isna().any().any():
        raise ValueError(f"{split} CSV contains missing feature values")
    expected_idx = chunk["label"].map(LABEL_MAPPING)
    if expected_idx.isna().any() or not np.array_equal(expected_idx.to_numpy(), chunk["label_idx"].to_numpy()):
        raise ValueError(f"{split} CSV label mapping is invalid")


def read_canonical_split(
    csv_path: Path,
    split: str,
    feature_names: Sequence[str],
    *,
    normal_cap: int | None,
    seed: int,
    chunk_size: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read in chunks, preserving all events and retaining lowest-hash normals."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"canonical split not found: {csv_path}")
    usecols = ["row_id", "split", "region_id", *feature_names, *REQUIRED_TARGET_COLUMNS]
    event_parts: list[pd.DataFrame] = []
    normal_candidates: pd.DataFrame | None = None
    original_rows = original_normals = 0
    observed_labels: set[str] = set()
    observed_regions: set[str] = set()
    for chunk in pd.read_csv(csv_path, usecols=usecols, chunksize=chunk_size):
        _validate_chunk(chunk, split, feature_names)
        original_rows += len(chunk)
        normal_mask = chunk["label_idx"].to_numpy() == LABEL_MAPPING["normal"]
        original_normals += int(normal_mask.sum())
        observed_labels.update(chunk["label"].astype(str))
        observed_regions.update(chunk["region_id"].astype(str))
        event_parts.append(chunk.loc[~normal_mask])
        normals = chunk.loc[normal_mask].copy()
        if normal_cap is None:
            normal_candidates = normals if normal_candidates is None else pd.concat([normal_candidates, normals], ignore_index=True)
        elif normal_cap > 0 and not normals.empty:
            normals["_rank"] = normals["row_id"].astype(str).map(lambda value: _stable_rank(value, seed))
            normal_candidates = normals if normal_candidates is None else pd.concat([normal_candidates, normals], ignore_index=True)
            normal_candidates = normal_candidates.nsmallest(normal_cap, "_rank", keep="first")
    if observed_labels != set(LABEL_MAPPING) or observed_regions != set(EXPECTED_REGIONS):
        raise ValueError(f"{split} must contain all 8 classes and regions; labels={sorted(observed_labels)}, regions={sorted(observed_regions)}")
    events = pd.concat(event_parts, ignore_index=True)
    normals = normal_candidates if normal_candidates is not None else pd.DataFrame(columns=events.columns)
    normals = normals.drop(columns=["_rank"], errors="ignore")
    sampled = pd.concat([events, normals], ignore_index=True).sort_values("row_id", kind="stable").reset_index(drop=True)
    record = {
        "split": split,
        "original_rows": original_rows,
        "original_event_rows": original_rows - original_normals,
        "original_normal_rows": original_normals,
        "retained_rows": len(sampled),
        "retained_event_rows": int((sampled["label_idx"] != LABEL_MAPPING["normal"]).sum()),
        "retained_normal_rows": int((sampled["label_idx"] == LABEL_MAPPING["normal"]).sum()),
        "normal_cap": normal_cap,
        "sampling": "all events plus deterministic lowest blake2b(row_id, seed) normal rows",
        "seed": seed,
    }
    return sampled, record


def frame_to_arrays(frame: pd.DataFrame, feature_names: Sequence[str]) -> ArrayDataset:
    return ArrayDataset(
        np.array(frame[list(feature_names)].to_numpy(dtype=np.float32), copy=True, order="C"),
        np.array(frame["label_idx"].to_numpy(dtype=np.int64), copy=True, order="C"),
        tuple(frame["row_id"].astype(str)),
        tuple(frame["region_id"].astype(str)),
    )


def state_dict_to_ndarrays(model: nn.Module) -> list[np.ndarray]:
    return [value.detach().cpu().numpy().copy() for value in model.state_dict().values()]


def load_ndarrays_into_model(model: nn.Module, arrays: Sequence[np.ndarray]) -> None:
    state = model.state_dict()
    if len(arrays) != len(state):
        raise ValueError("model update has incorrect parameter count")
    restored = {}
    for (name, reference), array in zip(state.items(), arrays):
        if tuple(array.shape) != tuple(reference.shape):
            raise ValueError(f"model update shape mismatch for {name}")
        restored[name] = torch.as_tensor(array, dtype=reference.dtype, device=reference.device)
    model.load_state_dict(restored, strict=True)


def _loader(data: ArrayDataset, batch_size: int, shuffle: bool, seed: int) -> DataLoader:
    generator = torch.Generator().manual_seed(seed)
    drop_last = bool(shuffle and len(data) % batch_size == 1)
    return DataLoader(
        TensorDataset(torch.from_numpy(data.features), torch.from_numpy(data.labels)),
        batch_size=batch_size, shuffle=shuffle, generator=generator, drop_last=drop_last,
    )


def train_epochs(
    model: GeoV2EventClassifierMLP,
    data: ArrayDataset,
    config: TrainingConfig,
    device: torch.device,
    *,
    epochs: int,
    seed: int,
) -> float:
    weights = torch.tensor(compute_class_weights(data.labels, N_CLASSES), dtype=torch.float32, device=device)
    criterion = nn.NLLLoss(weight=weights)
    optimizer_type = {"Adam": torch.optim.Adam, "AdamW": torch.optim.AdamW}.get(config.optimizer)
    if optimizer_type is None:
        raise ValueError(f"unsupported optimizer: {config.optimizer}")
    optimizer = optimizer_type(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    model.to(device)
    total_loss = total_rows = 0
    for epoch in range(epochs):
        model.train()
        for features, labels in _loader(data, config.batch_size, True, seed + epoch):
            features, labels = features.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(features), labels)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * len(labels)
            total_rows += len(labels)
    return total_loss / max(total_rows, 1)


def predict_probabilities(
    model: GeoV2EventClassifierMLP, data: ArrayDataset, batch_size: int, device: torch.device
) -> np.ndarray:
    model.to(device).eval()
    probabilities = []
    with torch.no_grad():
        for features, _ in _loader(data, batch_size, False, 0):
            probabilities.append(model.predict_proba(features.to(device)).cpu().numpy())
    return np.concatenate(probabilities) if probabilities else np.empty((0, N_CLASSES), dtype=np.float32)


def evaluate_model(
    model: GeoV2EventClassifierMLP, data: ArrayDataset, batch_size: int, device: torch.device
) -> tuple[dict[str, Any], np.ndarray]:
    probabilities = predict_probabilities(model, data, batch_size, device)
    return metrics_from_probabilities(data.labels, probabilities), probabilities


def metrics_from_probabilities(labels_array: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    predictions = probabilities.argmax(axis=1)
    precision, recall, class_f1, support = precision_recall_fscore_support(
        labels_array, predictions, labels=np.arange(N_CLASSES), zero_division=0,
    )
    labels = [label for label, _ in sorted(LABEL_MAPPING.items(), key=lambda item: item[1])]
    return {
        "rows": len(labels_array),
        "accuracy": float(accuracy_score(labels_array, predictions)),
        "macro_f1": float(f1_score(labels_array, predictions, labels=np.arange(N_CLASSES), average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(labels_array, predictions, average="weighted", zero_division=0)),
        "per_class": {
            label: {"precision": float(precision[index]), "recall": float(recall[index]), "f1": float(class_f1[index]), "support": int(support[index])}
            for index, label in enumerate(labels)
        },
        "confusion_matrix": confusion_matrix(labels_array, predictions, labels=np.arange(N_CLASSES)).tolist(),
    }


def calibration_metrics(probabilities: np.ndarray, labels: np.ndarray, bins: int = 10) -> dict[str, Any]:
    confidence = probabilities.max(axis=1)
    correct = probabilities.argmax(axis=1) == labels
    records = []
    ece = 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    for index in range(bins):
        mask = (confidence >= edges[index]) & (confidence < edges[index + 1] if index < bins - 1 else confidence <= edges[index + 1])
        count = int(mask.sum())
        accuracy = float(correct[mask].mean()) if count else 0.0
        mean_confidence = float(confidence[mask].mean()) if count else 0.0
        ece += count / max(len(labels), 1) * abs(accuracy - mean_confidence)
        records.append({"lower": float(edges[index]), "upper": float(edges[index + 1]), "count": count, "accuracy": accuracy, "mean_confidence": mean_confidence})
    return {
        "ece": float(ece), "bins": records,
        "confidence_semantics": "Uncalibrated softmax confidence is a proxy, not a calibrated probability.",
    }


def select_best_validation_checkpoint(history: Sequence[Mapping[str, Any]]) -> int:
    if not history or any("validation_macro_f1" not in record for record in history):
        raise ValueError("checkpoint selection requires validation_macro_f1")
    return int(max(history, key=lambda record: (float(record["validation_macro_f1"]), -int(record["checkpoint_index"]))) ["checkpoint_index"])


def train_centralized_ablation(
    variant: str,
    train_data: ArrayDataset,
    validation_data: ArrayDataset,
    config: TrainingConfig,
    device: torch.device,
) -> tuple[dict[str, Any], dict[str, torch.Tensor]]:
    columns = FEATURE_VARIANTS[variant]
    canonical_index = {name: index for index, name in enumerate(FEATURE_VARIANTS[CANONICAL_VARIANT])}
    selected = np.array([canonical_index[name] for name in columns])
    train_variant = ArrayDataset(train_data.features[:, selected], train_data.labels, train_data.row_ids, train_data.regions)
    validation_variant = ArrayDataset(validation_data.features[:, selected], validation_data.labels, validation_data.row_ids, validation_data.regions)
    seed_everything(config.seed)
    model = GeoV2EventClassifierMLP(len(columns), config.hidden_size, dropout_rate=config.dropout_rate)
    history = []
    checkpoints = []
    for epoch in range(1, config.centralized_epochs + 1):
        loss = train_epochs(model, train_variant, config, device, epochs=1, seed=config.seed + epoch)
        validation_metrics, _ = evaluate_model(model, validation_variant, config.batch_size, device)
        history.append({"checkpoint_index": epoch, "train_loss": loss, "validation_macro_f1": validation_metrics["macro_f1"]})
        checkpoints.append({name: value.detach().cpu().clone() for name, value in model.state_dict().items()})
    best_epoch = select_best_validation_checkpoint(history)
    best_state = checkpoints[best_epoch - 1]
    model.load_state_dict(best_state)
    best_metrics, _ = evaluate_model(model, validation_variant, config.batch_size, device)
    return {
        "variant": variant, "feature_count": len(columns), "ordered_features": columns,
        "selection_split": "validation_subset", "best_epoch": best_epoch,
        "best_validation_metrics": best_metrics, "history": history,
        "class_weights": compute_class_weights(train_variant.labels, N_CLASSES).tolist(),
    }, best_state


@dataclass
class RegionalClient:
    region_id: str
    train: ArrayDataset
    validation: ArrayDataset

    def fit(
        self, global_arrays: Sequence[np.ndarray], config: TrainingConfig,
        input_size: int, device: torch.device, round_number: int,
    ) -> tuple[list[np.ndarray], dict[str, Any]]:
        model = GeoV2EventClassifierMLP(input_size, config.hidden_size, dropout_rate=config.dropout_rate)
        load_ndarrays_into_model(model, global_arrays)
        started = time.perf_counter()
        loss = train_epochs(
            model, self.train, config, device, epochs=config.local_epochs,
            seed=config.seed + round_number * 100 + int(self.region_id[-2:]),
        )
        validation_metrics, _ = evaluate_model(model, self.validation, config.batch_size, device)
        rare_classes = np.flatnonzero(np.bincount(self.train.labels, minlength=N_CLASSES) / len(self.train) < config.rare_threshold)
        rare_fraction = float(np.isin(self.train.labels, rare_classes).mean())
        metrics = {
            "region_id": self.region_id, "train_loss": loss,
            "val_macro_f1": validation_metrics["macro_f1"],
            "rare_class_fraction": rare_fraction, "dataset_size": len(self.train),
            "training_seconds": time.perf_counter() - started,
        }
        return state_dict_to_ndarrays(model), metrics


class _ClientPlaceholder:
    def __init__(self, cid: str) -> None:
        self.cid = cid


def aggregate_client_updates(
    strategy: AdaptiveFedAvg,
    round_number: int,
    updates: Sequence[tuple[str, Sequence[np.ndarray], int, Mapping[str, Any]]],
) -> list[np.ndarray]:
    client_ids = [item[0] for item in updates]
    if len(updates) != 8 or set(client_ids) != set(EXPECTED_REGIONS):
        raise ValueError("every federated round requires exactly 8 unique canonical clients")
    status = Status(code=Code.OK, message="in-process Geo V2 client fit")
    results = [
        (
            _ClientPlaceholder(client_id),
            FitRes(status=status, parameters=ndarrays_to_parameters(list(arrays)), num_examples=num_examples, metrics=dict(metrics)),
        )
        for client_id, arrays, num_examples, metrics in updates
    ]
    parameters, _ = strategy.aggregate_fit(round_number, results, [])
    if parameters is None:
        raise RuntimeError("adaptive aggregation returned no parameters")
    return parameters_to_ndarrays(parameters)


def build_regional_clients(train_data: ArrayDataset, validation_data: ArrayDataset) -> dict[str, RegionalClient]:
    clients = {}
    train_regions = np.asarray(train_data.regions)
    validation_regions = np.asarray(validation_data.regions)
    for region in EXPECTED_REGIONS:
        local_train = train_data.subset(train_regions == region)
        local_validation = validation_data.subset(validation_regions == region)
        if not len(local_train) or not len(local_validation):
            raise ValueError(f"region {region} lacks train or validation rows")
        clients[region] = RegionalClient(region, local_train, local_validation)
    if tuple(clients) != EXPECTED_REGIONS:
        raise ValueError("client setup did not produce exactly 8 unique regions")
    return clients


def run_federated_loop(
    clients: Mapping[str, RegionalClient], validation_data: ArrayDataset,
    config: TrainingConfig, output_dir: Path, device: torch.device,
) -> tuple[GeoV2EventClassifierMLP, GeoV2EventClassifierMLP, list[dict[str, Any]], list[dict[str, Any]]]:
    if tuple(clients) != EXPECTED_REGIONS:
        raise ValueError("federated loop requires exactly 8 unique ordered clients")
    seed_everything(config.seed)
    input_size = len(FEATURE_VARIANTS[CANONICAL_VARIANT])
    global_model = GeoV2EventClassifierMLP(input_size, config.hidden_size, dropout_rate=config.dropout_rate)
    global_arrays = state_dict_to_ndarrays(global_model)
    frequencies = np.bincount(np.concatenate([client.train.labels for client in clients.values()]), minlength=N_CLASSES)
    frequencies = frequencies / frequencies.sum()
    strategy = AdaptiveFedAvg(
        global_class_frequencies={index: float(value) for index, value in enumerate(frequencies)},
        alpha=config.alpha, beta=config.beta, q_floor=config.q_floor,
        g_threshold=config.g_threshold, g_min=config.g_min,
        rare_threshold=config.rare_threshold, weight_log_path=output_dir / "adaptive_weights.csv",
    )
    round_history: list[dict[str, Any]] = []
    client_history: list[dict[str, Any]] = []
    checkpoints: list[list[np.ndarray]] = []
    for round_number in range(1, config.rounds + 1):
        updates = []
        for region, client in clients.items():
            arrays, metrics = client.fit(global_arrays, config, input_size, device, round_number)
            updates.append((region, arrays, len(client.train), metrics))
            client_history.append({"round": round_number, **metrics})
        global_arrays = aggregate_client_updates(strategy, round_number, updates)
        load_ndarrays_into_model(global_model, global_arrays)
        validation_metrics, _ = evaluate_model(global_model, validation_data, config.batch_size, device)
        round_history.append({
            "checkpoint_index": round_number, "round": round_number,
            "validation_macro_f1": validation_metrics["macro_f1"],
            "validation_accuracy": validation_metrics["accuracy"],
        })
        checkpoints.append([array.copy() for array in global_arrays])
    best_round = select_best_validation_checkpoint(round_history)
    best_model = GeoV2EventClassifierMLP(input_size, config.hidden_size, dropout_rate=config.dropout_rate)
    load_ndarrays_into_model(best_model, checkpoints[best_round - 1])
    final_model = GeoV2EventClassifierMLP(input_size, config.hidden_size, dropout_rate=config.dropout_rate)
    load_ndarrays_into_model(final_model, checkpoints[-1])
    return best_model, final_model, round_history, client_history


def make_event_balanced_subset(data: ArrayDataset, seed: int) -> ArrayDataset:
    event_mask = data.labels != LABEL_MAPPING["normal"]
    event_indices = np.flatnonzero(event_mask)
    normal_indices = np.flatnonzero(~event_mask)
    ranked = sorted(normal_indices, key=lambda index: _stable_rank(data.row_ids[index], seed))[:len(event_indices)]
    selected = np.sort(np.concatenate([event_indices, np.asarray(ranked, dtype=int)]))
    mask = np.zeros(len(data), dtype=bool)
    mask[selected] = True
    return data.subset(mask)


def _git_revision(repo_root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True,
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _json_write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def load_geo_v2_artifact(path: Path, device: str | torch.device = "cpu") -> tuple[GeoV2EventClassifierMLP, dict[str, Any]]:
    artifact = torch.load(path, map_location=device, weights_only=False)
    model = GeoV2EventClassifierMLP(
        artifact["input_size"], artifact["hidden_size"], len(artifact["labels"]), artifact["dropout_rate"],
    )
    model.load_state_dict(artifact["state_dict"], strict=True)
    model.to(device).eval()
    return model, artifact


def save_model_artifact(
    path: Path, model: GeoV2EventClassifierMLP, scaler: Mapping[str, Any],
    manifest: Mapping[str, Any], config: TrainingConfig, repo_root: Path,
    *, round_number: int, checkpoint_metric: float,
) -> None:
    ordered_features = FEATURE_VARIANTS[CANONICAL_VARIANT]
    labels = [label for label, _ in sorted(LABEL_MAPPING.items(), key=lambda item: item[1])]
    torch.save({
        "state_dict": {name: value.detach().cpu() for name, value in model.state_dict().items()},
        "input_size": len(ordered_features), "hidden_size": config.hidden_size,
        "dropout_rate": config.dropout_rate, "labels": labels,
        "label_mapping": LABEL_MAPPING, "ordered_feature_names": ordered_features,
        "scaler_mean": [float(scaler["mean"][name]) for name in ordered_features],
        "scaler_scale": [float(scaler["scale"][name]) for name in ordered_features],
        "scaler_fit_split": scaler["fit_split"], "tables_are_scaled": True,
        "model_version": f"fedrouteai-geo-v2-round-{round_number:02d}",
        "dataset_version": manifest["dataset_version"],
        "network_version": manifest["network_version"],
        "training_config": asdict(config),
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_revision": _git_revision(repo_root),
        "checkpoint_metric": {"name": "validation_macro_f1", "value": checkpoint_metric},
    }, path)


def run_training(
    dataset_dir: Path, artifact_root: Path, run_id: str,
    config: TrainingConfig, repo_root: Path,
) -> Path:
    started = time.perf_counter()
    seed_everything(config.seed)
    output_dir = artifact_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    _, scaler, manifest = load_dataset_metadata(dataset_dir)
    features = FEATURE_VARIANTS[CANONICAL_VARIANT]
    table_dir = dataset_dir / "feature_tables" / CANONICAL_VARIANT
    train_frame, train_sampling = read_canonical_split(
        table_dir / "train.csv", "train", features, normal_cap=config.train_normal_cap,
        seed=config.seed, chunk_size=config.csv_chunk_size,
    )
    validation_frame, validation_sampling = read_canonical_split(
        table_dir / "validation.csv", "validation", features, normal_cap=config.validation_normal_cap,
        seed=config.seed + 1, chunk_size=config.csv_chunk_size,
    )
    train_data = frame_to_arrays(train_frame, features)
    validation_data = frame_to_arrays(validation_frame, features)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    centralized = {}
    for variant in FEATURE_VARIANTS:
        result, _ = train_centralized_ablation(variant, train_data, validation_data, config, device)
        centralized[variant] = result
    _json_write(output_dir / "centralized_ablations.json", centralized)

    clients = build_regional_clients(train_data, validation_data)
    client_distributions = {
        region: {
            "train_rows": len(client.train), "validation_rows": len(client.validation),
            "train_class_counts": np.bincount(client.train.labels, minlength=N_CLASSES).tolist(),
            "validation_class_counts": np.bincount(client.validation.labels, minlength=N_CLASSES).tolist(),
        }
        for region, client in clients.items()
    }
    # From this point, each client owns only its regional arrays.
    del train_frame, validation_frame, train_data
    best_model, final_model, round_history, client_history = run_federated_loop(
        clients, validation_data, config, output_dir, device,
    )
    best_round = select_best_validation_checkpoint(round_history)
    best_validation_metrics, _ = evaluate_model(best_model, validation_data, config.batch_size, device)
    final_validation_metrics, _ = evaluate_model(final_model, validation_data, config.batch_size, device)

    save_model_artifact(
        output_dir / "best_model.pt", best_model, scaler, manifest, config, repo_root,
        round_number=best_round, checkpoint_metric=best_validation_metrics["macro_f1"],
    )
    save_model_artifact(
        output_dir / "final_model.pt", final_model, scaler, manifest, config, repo_root,
        round_number=config.rounds, checkpoint_metric=final_validation_metrics["macro_f1"],
    )

    # Test is loaded and evaluated only after validation-only model selection.
    test_frame, test_record = read_canonical_split(
        table_dir / "test.csv", "test", features, normal_cap=None,
        seed=config.seed + 2, chunk_size=config.csv_chunk_size,
    )
    test_data = frame_to_arrays(test_frame, features)
    diagnostic_data = make_event_balanced_subset(test_data, config.seed + 3)
    test_metrics, test_probabilities = evaluate_model(best_model, test_data, config.batch_size, device)
    probability_by_row = {row_id: test_probabilities[index] for index, row_id in enumerate(test_data.row_ids)}
    diagnostic_probabilities = np.stack([probability_by_row[row_id] for row_id in diagnostic_data.row_ids])
    diagnostic_metrics = metrics_from_probabilities(diagnostic_data.labels, diagnostic_probabilities)
    calibration = {
        "full_untouched_test": calibration_metrics(test_probabilities, test_data.labels),
        "event_balanced_diagnostic": calibration_metrics(diagnostic_probabilities, diagnostic_data.labels),
    }
    adaptive_weights = pd.read_csv(output_dir / "adaptive_weights.csv").to_dict("records")
    comparison = {
        "selection_basis": "validation_subset_macro_f1_only",
        "centralized_validation_macro_f1": {name: result["best_validation_metrics"]["macro_f1"] for name, result in centralized.items()},
        "federated_best_validation_macro_f1": best_validation_metrics["macro_f1"],
        "federated_full_test_macro_f1": test_metrics["macro_f1"],
        "note": "Centralized ablations were not evaluated on test; test was consumed once for the selected federated checkpoint.",
    }
    metrics = {
        "best_round": best_round, "best_validation_subset": best_validation_metrics,
        "final_round_validation_subset": final_validation_metrics,
        "full_untouched_test": test_metrics, "event_balanced_test_diagnostic": diagnostic_metrics,
        "test_evaluation_count": 1,
    }
    privacy = {
        "statement": "This is an in-process FL simulation. Canonical train rows are partitioned by region before rounds; each client trains only on its own rows, and aggregation receives model state_dict arrays plus scalar telemetry. No formal differential-privacy guarantee is claimed.",
        "centralized_ablation_exception": "The explicitly requested centralized ablations use the sampled canonical training table before client partitioning.",
        "limitations": [
            "In-process isolation is logical, not process or hardware isolation.",
            "BatchNorm running statistics and counters are included in model updates.",
            "Softmax confidence is an uncalibrated proxy.",
        ],
    }
    _json_write(output_dir / "metrics.json", metrics)
    _json_write(output_dir / "per_class_metrics.json", {
        "full_untouched_test": test_metrics["per_class"], "event_balanced_test_diagnostic": diagnostic_metrics["per_class"],
    })
    _json_write(output_dir / "confusion_matrices.json", {
        "label_order": [label for label, _ in sorted(LABEL_MAPPING.items(), key=lambda item: item[1])],
        "full_untouched_test": test_metrics["confusion_matrix"],
        "event_balanced_test_diagnostic": diagnostic_metrics["confusion_matrix"],
    })
    _json_write(output_dir / "federated_history.json", round_history)
    _json_write(output_dir / "client_history.json", client_history)
    _json_write(output_dir / "client_distributions.json", client_distributions)
    _json_write(output_dir / "adaptive_weights.json", adaptive_weights)
    _json_write(output_dir / "calibration.json", calibration)
    _json_write(output_dir / "centralized_federated_comparison.json", comparison)
    _json_write(output_dir / "privacy_statement.json", privacy)
    _json_write(output_dir / "sampling.json", {
        "training": train_sampling, "validation_evaluation_subset": validation_sampling,
        "test": test_record,
        "event_balanced_test_diagnostic": {
            "rows": len(diagnostic_data), "event_rows": int((diagnostic_data.labels != 0).sum()),
            "normal_rows": int((diagnostic_data.labels == 0).sum()), "seed": config.seed + 3,
        },
    })
    _json_write(output_dir / "run.json", {
        "run_id": run_id, "device": str(device), "elapsed_seconds": time.perf_counter() - started,
        "config": asdict(config), "dataset_path": str(dataset_dir),
        "canonical_tables": [str(table_dir / f"{split}.csv") for split in ("train", "validation", "test")],
        "test_loaded_after_checkpoint_selection": True,
    })
    return output_dir
