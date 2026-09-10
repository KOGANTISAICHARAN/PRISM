from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """PRISM backend configuration. All secrets come from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PRISM API"
    demo_mode: bool = True
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60 * 24 * 7

    # Database: SQLite by default, any SQLAlchemy URL (e.g. Supabase Postgres) supported.
    database_url: str = f"sqlite:///{(BASE_DIR / 'prism.db').as_posix()}"

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Storage: "local" or "supabase"
    storage_backend: str = "local"
    local_storage_dir: str = str(BASE_DIR / "storage")
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "prism-evidence"

    # AI provider: "demo" or "openai" (any OpenAI-compatible multimodal endpoint)
    ai_provider: str = "demo"
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_vision_model: str = "gpt-4o-mini"
    ai_text_model: str = "gpt-4o-mini"

    # Embeddings: "sentence-transformers" (all-MiniLM-L6-v2) or "tfidf" fallback
    embedding_backend: str = "tfidf"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Upload limits
    max_upload_mb: int = 15
    allowed_mime_prefixes: str = "image/,video/,application/pdf"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_mime_list(self) -> list[str]:
        return [m.strip() for m in self.allowed_mime_prefixes.split(",") if m.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
