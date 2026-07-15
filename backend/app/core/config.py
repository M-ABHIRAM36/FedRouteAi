"""
Central app configuration, loaded from environment variables (.env).
Every other module should read settings from here — never hardcode
DB URLs, city coordinates, or simulation constants elsewhere.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    APP_NAME: str = "FedRouteAI"
    API_V1_PREFIX: str = "/api/v1"
    ENV: str = "development"
    DEBUG: bool = True

    # --- Database ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "fedrouteai"
    POSTGRES_USER: str = "fedrouteai"
    POSTGRES_PASSWORD: str = "fedrouteai"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- City / map defaults (used by map matching + graph builder) ---
    CITY_NAME: str = "Hyderabad, India"
    CITY_CENTER_LAT: float = 17.3850
    CITY_CENTER_LON: float = 78.4867

    # --- Map matching ---
    MAP_MATCH_MAX_CANDIDATE_DISTANCE_M: float = 40.0  # ignore matches further than this

    # --- Event detection ---
    EVENT_CONFIDENCE_THRESHOLD: float = 0.70  # below this, don't surface an event
    GRAPH_REASONING_NEIGHBOR_DEPTH: int = 1   # how many hops of neighbors to inspect

    # --- Federated learning ---
    FL_NUM_ROUNDS: int = 20
    FL_MIN_CLIENTS: int = 3
    FL_LOCAL_EPOCHS: int = 1

    # --- Routing ---
    ROUTE_EVENT_PENALTY_FACTOR: float = 3.0  # multiplies travel_time on an affected edge


settings = Settings()
