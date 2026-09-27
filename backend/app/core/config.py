from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DevSynt AI RAG Assistant"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./rag_app.db"
    upload_dir: str = "uploads"
    max_upload_mb: int = 20
    cors_origins: str = "http://localhost:5173"

    gemini_api_key: str = ""
    gemini_llm_model: str = "gemini-3.8-flash"
    gemini_embedding_model: str = "gemini-embedding-2"
    embedding_dimension: int = 768

    qdrant_path: str = "./qdrant_data"
    qdrant_collection: str = "documents"
    chunk_size: int = 1200
    chunk_overlap: int = 200
    top_k: int = 5
    min_retrieval_score: float = 0.50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def qdrant_storage_path(self) -> Path:
        return Path(self.qdrant_path)

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
