"""Entry point to start the Flower server with the adaptive strategy.
Run this, then run federated_clients/run_client.py once per region."""
import flwr as fl

from app.services.federated_learning.adaptive_aggregation import AdaptiveFedAvg
from app.services.federated_learning.local_model import LocalModel
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def start_server():
    initial = LocalModel.initial()
    strategy = AdaptiveFedAvg(
        min_fit_clients=settings.FL_MIN_CLIENTS,
        min_available_clients=settings.FL_MIN_CLIENTS,
        initial_parameters=fl.common.ndarrays_to_parameters(initial.get_parameters()),
    )
    logger.info("Starting Flower server for %d rounds, min_clients=%d",
                settings.FL_NUM_ROUNDS, settings.FL_MIN_CLIENTS)
    fl.server.start_server(
        server_address="0.0.0.0:8080",
        config=fl.server.ServerConfig(num_rounds=settings.FL_NUM_ROUNDS),
        strategy=strategy,
    )


if __name__ == "__main__":
    start_server()
