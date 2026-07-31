from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    SERVICE_NAME: str = "Finance Intelligence Async Worker"
    ENVIRONMENT: str = Field(default="development")
    CONCURRENCY_LIMIT: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


worker_settings = WorkerSettings()
