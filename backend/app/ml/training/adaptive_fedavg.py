"""
Adaptive Federated Aggregation for FedRouteAI.

This module implements the custom AdaptiveFedAvg strategy which modifies the standard
FedAvg aggregation by applying a four-factor weight to each client's update:
1. Dataset size (FedAvg base)
2. Validation Macro F1 quality (floored)
3. Rare-event bonus (bounded)
4. EMA reliability gate
"""
from __future__ import annotations

import csv
import logging
import math
from pathlib import Path
from typing import List, Tuple, Optional

import flwr as fl
from flwr.common import FitRes, Parameters, ndarrays_to_parameters, parameters_to_ndarrays
from flwr.server.client_proxy import ClientProxy

logger = logging.getLogger(__name__)


class AdaptiveFedAvg(fl.server.strategy.FedAvg):
    """
    Adaptive Federated Averaging strategy.
    
    Overrides aggregate_fit to implement ITS-aware adaptive weighting.
    """
    
    def __init__(
        self,
        global_class_frequencies: dict[int, float],
        alpha: float = 0.3,
        beta: float = 0.3,
        q_floor: float = 0.10,
        g_threshold: float = 0.15,
        g_min: float = 0.50,
        rare_threshold: float = 0.05,
        weight_log_path: Path | None = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.alpha = alpha
        self.beta = beta
        self.q_floor = q_floor
        self.g_threshold = g_threshold
        self.g_min = g_min
        
        # Identify rare classes based on global frequencies
        self.rare_classes = frozenset(
            [cls_idx for cls_idx, freq in global_class_frequencies.items() if freq < rare_threshold]
        )
        
        self.ema_f1: dict[str, float] = {}
        self.weight_log_path = weight_log_path

    def _compute_quality(self, val_macro_f1: float) -> float:
        """Computes floored quality factor."""
        return max(self.q_floor, val_macro_f1)

    def _compute_rarity_bonus(self, rare_class_fraction: float) -> float:
        """Computes bounded rarity bonus."""
        return 1.0 + self.beta * rare_class_fraction

    def _update_ema(self, region_id: str, val_macro_f1: float) -> float:
        """Updates and clamps the EMA for the given region."""
        if region_id not in self.ema_f1:
            self.ema_f1[region_id] = max(self.q_floor, val_macro_f1)
        else:
            new_ema = self.alpha * val_macro_f1 + (1.0 - self.alpha) * self.ema_f1[region_id]
            self.ema_f1[region_id] = new_ema
            
        # Strict constraint: EMA must remain in [0, 1]
        self.ema_f1[region_id] = max(0.0, min(1.0, self.ema_f1[region_id]))
        return self.ema_f1[region_id]

    def _compute_gate(self, ema_f1_value: float) -> float:
        """Computes the reliability gate bounded in [g_min, 1.0]."""
        if ema_f1_value >= self.g_threshold:
            gate_value = 1.0
        else:
            gate_value = self.g_min + (1.0 - self.g_min) * (ema_f1_value / self.g_threshold)
            
        # Strict constraint: Gate must remain in [g_min, 1.0]
        return max(self.g_min, min(1.0, gate_value))

    def _log_weights(self, round_num: int, weight_records: list[dict]) -> None:
        """Appends factor and weight telemetry to the CSV log."""
        if not self.weight_log_path:
            return
            
        file_exists = self.weight_log_path.exists()
        
        try:
            with open(self.weight_log_path, 'a', newline='') as csvfile:
                fieldnames = [
                    'round', 'region_id', 'dataset_size', 'val_macro_f1', 
                    'ema_f1', 'quality', 'rare_fraction', 'rarity_bonus', 
                    'gate', 'raw_weight', 'normalized_weight'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                if not file_exists:
                    writer.writeheader()
                    
                for record in weight_records:
                    record['round'] = round_num
                    writer.writerow(record)
        except Exception as e:
            logger.error(f"Failed to write weight log: {e}")

    def aggregate_fit(
        self,
        server_round: int,
        results: List[Tuple[ClientProxy, FitRes]],
        failures: List[Tuple[ClientProxy, FitRes] | BaseException],
    ) -> Tuple[Optional[Parameters], dict]:
        """Aggregate fit results using strict adaptive weighting."""
        if not results:
            return None, {}

        # 1. Compute raw weights with strict validation
        client_records = []
        raw_weights = []
        parsed_results = []
        
        for i, (client_proxy, fit_res) in enumerate(results):
            metrics = fit_res.metrics or {}
            
            # --- Dataset Size Validation ---
            n_k = fit_res.num_examples
            if n_k < 0:
                raise ValueError(f"Client returned negative dataset size: {n_k}")
            if n_k == 0:
                logger.warning(f"Client {client_proxy.cid} returned 0 samples. Skipping contribution.")
                continue
                
            region_id = metrics.get("region_id", f"UNKNOWN_{client_proxy.cid}")
            
            # --- Validation Macro F1 Validation ---
            val_macro_f1_raw = metrics.get("val_macro_f1")
            if val_macro_f1_raw is None:
                val_macro_f1 = 0.0  # Default for missing optional metric
            else:
                val_macro_f1 = float(val_macro_f1_raw)
                if not math.isfinite(val_macro_f1):
                    raise ValueError(f"val_macro_f1 is not finite: {val_macro_f1}")
                if not (0.0 <= val_macro_f1 <= 1.0):
                    raise ValueError(f"val_macro_f1 out of bounds [0,1]: {val_macro_f1}")
            
            # --- Rare Class Fraction Validation ---
            rare_class_fraction_raw = metrics.get("rare_class_fraction")
            if rare_class_fraction_raw is None:
                rare_class_fraction = 0.0  # Default for missing optional metric
            else:
                rare_class_fraction = float(rare_class_fraction_raw)
                if not math.isfinite(rare_class_fraction):
                    raise ValueError(f"rare_class_fraction is not finite: {rare_class_fraction}")
                # Clamp into [0,1]
                rare_class_fraction = max(0.0, min(1.0, rare_class_fraction))
                
            # --- Compute Factors ---
            q_k = self._compute_quality(val_macro_f1)
            rho_k = self._compute_rarity_bonus(rare_class_fraction)
            ema_val = self._update_ema(region_id, val_macro_f1)
            g_k = self._compute_gate(ema_val)
            
            raw_weight = n_k * q_k * rho_k * g_k
            
            raw_weights.append(raw_weight)
            parsed_results.append((client_proxy, fit_res))
            
            client_records.append({
                'region_id': region_id,
                'dataset_size': n_k,
                'val_macro_f1': val_macro_f1,
                'ema_f1': ema_val,
                'quality': q_k,
                'rare_fraction': rare_class_fraction,
                'rarity_bonus': rho_k,
                'gate': g_k,
                'raw_weight': raw_weight
            })

        # If all valid clients had n_k=0, fallback
        if not parsed_results:
            logger.warning(f"Round {server_round}: All clients skipped. Returning None.")
            return None, {}

        total_weight = sum(raw_weights)
        
        if total_weight == 0:
            logger.warning(f"Round {server_round}: total_weight is 0. Falling back to uniform weighting.")
            normalized_weights = [1.0 / len(raw_weights)] * len(raw_weights)
        else:
            normalized_weights = [w / total_weight for w in raw_weights]

        # --- Assertions for development mode ---
        assert math.isclose(sum(normalized_weights), 1.0, rel_tol=1e-5), "Normalized weights do not sum to 1.0"
        assert all(0.0 <= w <= 1.0 for w in normalized_weights), "Normalized weight out of bounds"

        # 2. Aggregate parameters
        weighted_parameters = []
        for i, (client_proxy, fit_res) in enumerate(parsed_results):
            w = normalized_weights[i]
            client_records[i]['normalized_weight'] = w
            
            ndarrays = parameters_to_ndarrays(fit_res.parameters)
            if not weighted_parameters:
                weighted_parameters = [layer * w for layer in ndarrays]
            else:
                assert len(weighted_parameters) == len(ndarrays), "Parameter list length mismatch between clients"
                weighted_parameters = [
                    layer_agg + layer * w
                    for layer_agg, layer in zip(weighted_parameters, ndarrays)
                ]
                
        for wp, cp in zip(weighted_parameters, parameters_to_ndarrays(parsed_results[0][1].parameters)):
            assert wp.shape == cp.shape, f"Shape mismatch in aggregation: {wp.shape} != {cp.shape}"

        # 3. Log weights using Flower's server_round
        self._log_weights(server_round, client_records)

        return ndarrays_to_parameters(weighted_parameters), {}
