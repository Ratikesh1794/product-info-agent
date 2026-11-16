from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    cors_origins: list[str] = ["http://localhost:5173"]
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"
    database_url: str = "postgresql+psycopg://localhost:5432/product_agent"
    auto_migrate: bool = True  # run alembic upgrade on API startup (one-click dev)
    catalog_path: Path = BACKEND_DIR / "data" / "bosch_product_catalog_mock.csv"


settings = Settings()
