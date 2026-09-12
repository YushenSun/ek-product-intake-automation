from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./ek_intake.db")
    extraction_provider: str = os.getenv("EXTRACTION_PROVIDER", "mock")
    openai_base_url: str = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "https://api.openai.com/v1")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    manual_minutes_per_product: float = float(os.getenv("MANUAL_MINUTES_PER_PRODUCT", "6"))


settings = Settings()
