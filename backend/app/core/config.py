import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _cors_origins() -> tuple[str, ...]:
    raw = os.getenv("CORS_ORIGINS", "")
    origins = tuple(origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip())
    environment = os.getenv("APP_ENV", "development").lower()
    if environment in {"production", "prod"}:
        if not origins or "*" in origins:
            raise RuntimeError("CORS_ORIGINS must list explicit HTTPS frontend origins in production")
        if any(not origin.startswith("https://") for origin in origins):
            raise RuntimeError("Production CORS origins must use HTTPS")
    return origins or (
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5175", "http://127.0.0.1:5175",
        "http://localhost:3000", "http://127.0.0.1:3000",
    )


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "AI Job Simulator Backend")
    supabase_url: str | None = os.getenv("SUPABASE_URL")
    supabase_service_role_key: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    dataset_max_file_size_bytes: int = int(os.getenv("DATASET_MAX_FILE_SIZE_BYTES", str(10 * 1024 * 1024)))
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    llm_max_requests_per_minute: int = int(os.getenv("LLM_MAX_REQUESTS_PER_MINUTE", "20"))
    cors_origins: tuple[str, ...] = _cors_origins()


settings = Settings()
