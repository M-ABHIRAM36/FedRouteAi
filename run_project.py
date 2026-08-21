"""Start FedRouteAI development components from the repository root.

Examples:
    python run_project.py
    python run_project.py --with-simulator
    python run_project.py --backend-only
    python run_project.py --frontend-only
    python run_project.py --simulator-only --simulator-ticks 10
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
GENERATOR_DIR = ROOT / "scripts" / "dataset_generator"


def _python_executable() -> Path:
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ]
    return next((candidate for candidate in candidates if candidate.exists()), Path(sys.executable))


def _npm_command() -> str | None:
    return shutil.which("npm.cmd") or shutil.which("npm")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start the FedRouteAI backend and frontend development servers.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--backend-only", action="store_true", help="Start only FastAPI.")
    mode.add_argument("--frontend-only", action="store_true", help="Start only Vite.")
    mode.add_argument("--simulator-only", action="store_true", help="Run only the live simulator.")
    parser.add_argument("--with-simulator", action="store_true", help="Run the simulator beside both servers.")
    parser.add_argument("--with-ingestion", action="store_true", help="Send simulator ticks to the live ingestion API.")
    parser.add_argument("--ingest-api-key", default=os.environ.get("LIVE_INGEST_API_KEY", ""))
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--simulator-ticks", type=int, default=0, help="Stop simulator after N ticks; 0 runs continuously.")
    parser.add_argument("--pings-per-tick", type=int, default=1000)
    parser.add_argument("--tick-seconds", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def _check_port(port: int, name: str) -> None:
    if not 1 <= port <= 65535:
        raise SystemExit(f"{name} port must be between 1 and 65535")


def _simulator_code(
    ticks: int,
    pings: int,
    tick_seconds: float,
    seed: int,
    ingestion_url: str,
    ingestion_key: str,
    run_id: str,
) -> str:
    return f"""
import json
import sys
import time

import httpx

sys.path.insert(0, {str(BACKEND_DIR)!r})
sys.path.insert(0, {str(GENERATOR_DIR)!r})

from road_network import build_road_network
from app.services.live_simulation import LiveTrafficSimulation, SimulationConfig
from app.services.live_ingestion.client import LiveIngestionClient

segments, regions = build_road_network(seed={seed})
simulation = LiveTrafficSimulation(
    list(segments.itertuples(index=False)),
    SimulationConfig(
        pings_per_tick={pings},
        tick_interval_seconds={tick_seconds},
        random_seed={seed},
    ),
)
simulation.start()
print(f"[simulator] started: {{len(segments)}} segments, {{len(regions)}} regions", flush=True)
if {bool(ingestion_url)!r}:
    health_url = {ingestion_url!r} + "/api/v1/health"
    for attempt in range(30):
        try:
            if httpx.get(health_url, timeout=1.0).status_code == 200:
                break
        except httpx.TransportError:
            pass
        time.sleep(1.0)
    else:
        raise RuntimeError(f"backend did not become ready at {{health_url}} within 30 seconds")
client = LiveIngestionClient(
    {ingestion_url!r}, {ingestion_key!r}, "fedrouteai-live-simulator", {run_id!r}
) if {bool(ingestion_url)!r} else None

limit = {ticks}
completed = 0
try:
    while limit == 0 or completed < limit:
        batch = simulation.tick()
        completed += 1
        if client:
            result = client.ingest(completed, batch)
            print(
                f"LIVE TICK {{completed:03d}} | generated={{len(batch)}} "
                f"accepted={{result['accepted']}} rejected={{result['rejected']}} "
                f"duplicates={{result['duplicates']}} db={{result['database_ms']:.2f}}ms "
                f"total={{result['total_ms']:.2f}}ms segments={{result['segments']}} "
                f"avg_speed={{result['average_speed_kmph']:.2f}}km/h",
                flush=True,
            )
        else:
            print("[simulator] " + json.dumps(simulation.summary(), default=str), flush=True)
        if limit == 0 or completed < limit:
            time.sleep({tick_seconds})
except KeyboardInterrupt:
    pass
finally:
    simulation.stop()
    print(f"[simulator] stopped after {{completed}} ticks", flush=True)
"""


def _commands(args: argparse.Namespace) -> list[tuple[str, list[str], Path, dict[str, str]]]:
    python = str(_python_executable())
    environment = os.environ.copy()
    commands: list[tuple[str, list[str], Path, dict[str, str]]] = []

    start_backend = not args.frontend_only and not args.simulator_only
    start_frontend = not args.backend_only and not args.simulator_only
    start_simulator = args.with_simulator or args.with_ingestion or args.simulator_only

    if args.with_ingestion and args.frontend_only:
        raise SystemExit("--with-ingestion cannot be combined with --frontend-only")
    if args.with_ingestion and not args.ingest_api_key:
        raise SystemExit("--with-ingestion requires --ingest-api-key or LIVE_INGEST_API_KEY")

    if start_backend:
        backend_env = environment.copy()
        backend_env["PYTHONPATH"] = "."
        if args.with_ingestion:
            backend_env["LIVE_INGEST_API_KEY"] = args.ingest_api_key
        commands.append((
            "backend",
            [python, "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", str(args.backend_port)],
            BACKEND_DIR,
            backend_env,
        ))

    if start_frontend:
        npm = _npm_command()
        if npm is None:
            raise SystemExit("npm was not found. Install Node.js 18+ or use --backend-only.")
        if not (FRONTEND_DIR / "node_modules").exists():
            raise SystemExit("frontend/node_modules is missing. Run: cd frontend && npm install")
        commands.append((
            "frontend",
            [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(args.frontend_port)],
            FRONTEND_DIR,
            environment.copy(),
        ))

    if start_simulator:
        ingestion_url = f"http://127.0.0.1:{args.backend_port}" if args.with_ingestion else ""
        commands.append((
            "simulator",
            [python, "-u", "-c", _simulator_code(
                args.simulator_ticks,
                args.pings_per_tick,
                args.tick_seconds,
                args.seed,
                ingestion_url,
                args.ingest_api_key,
                f"run-{uuid.uuid4().hex}",
            )],
            ROOT,
            environment.copy(),
        ))
    return commands


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)


def main() -> int:
    args = _parser().parse_args()
    _check_port(args.backend_port, "backend")
    _check_port(args.frontend_port, "frontend")
    if args.pings_per_tick <= 0 or args.tick_seconds <= 0 or args.simulator_ticks < 0:
        raise SystemExit("simulator counts and intervals must be positive (ticks may be 0 for continuous mode)")

    processes: list[tuple[str, subprocess.Popen]] = []
    try:
        for name, command, cwd, environment in _commands(args):
            process_options = {}
            if os.name != "nt":
                process_options["start_new_session"] = True
            process = subprocess.Popen(command, cwd=cwd, env=environment, **process_options)
            processes.append((name, process))
            print(f"[{name}] started (PID {process.pid})")

        if any(name == "backend" for name, _ in processes):
            print(f"Backend:  http://127.0.0.1:{args.backend_port}")
            print(f"API docs: http://127.0.0.1:{args.backend_port}/docs")
        if any(name == "frontend" for name, _ in processes):
            print(f"Frontend: http://127.0.0.1:{args.frontend_port}")
        print("Press Ctrl+C to stop all running components.")

        while processes:
            for name, process in processes:
                return_code = process.poll()
                if return_code is not None:
                    if name == "simulator" and (args.simulator_only or args.simulator_ticks > 0):
                        return return_code
                    raise RuntimeError(f"{name} exited unexpectedly with code {return_code}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping FedRouteAI...")
        return 0
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        for _, process in reversed(processes):
            _stop_process(process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
