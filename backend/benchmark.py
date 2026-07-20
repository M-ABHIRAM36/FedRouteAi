import torch
import time
import json
from pathlib import Path
from app.ml.training.mlp_model import EventClassifierMLP

def run_benchmarks():
    device = torch.device('cpu')
    model = EventClassifierMLP().to(device)
    model.eval()
    
    # 1. Communication Overhead
    num_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    bytes_per_param = 4  # float32
    client_upload_bytes = num_params * bytes_per_param
    client_download_bytes = num_params * bytes_per_param
    
    # 8 clients participating per round
    total_bytes_per_round = (client_upload_bytes + client_download_bytes) * 8
    
    # 2. Inference Latency
    dummy_input = torch.randn(1, 10).to(device)
    
    # Warmup
    for _ in range(100):
        _ = model(dummy_input)
        
    # Measure
    iterations = 1000
    start_time = time.perf_counter()
    for _ in range(iterations):
        _ = model(dummy_input)
    end_time = time.perf_counter()
    
    avg_latency_ms = ((end_time - start_time) / iterations) * 1000
    
    results = {
        'num_parameters': num_params,
        'client_upload_bytes': client_upload_bytes,
        'total_bytes_per_round': total_bytes_per_round,
        'avg_latency_ms': round(avg_latency_ms, 4)
    }
    
    out_dir = Path('../app/ml/artifacts/benchmarks')
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / 'systems_metrics.json', 'w') as f:
        json.dump(results, f, indent=2)
        
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    run_benchmarks()
