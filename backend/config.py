from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./farm_scout.db"
    GEE_PROJECT_ID: str = ""
    GEE_SERVICE_ACCOUNT_KEY_PATH: str = ""
    GEE_SERVICE_ACCOUNT_JSON: str = ""
    DEMO_MODE: bool = True
    SECRET_KEY: str = "supersecretkey_for_future_jwt"

    # ML weights for health score
    NDVI_WEIGHT: float = 0.40
    NDMI_WEIGHT: float = 0.25
    NDRE_WEIGHT: float = 0.20
    TEMPORAL_WEIGHT: float = 0.15

    # Severity thresholds
    HEALTHY_THRESHOLD: int = 80
    MILD_THRESHOLD: int = 60
    MODERATE_THRESHOLD: int = 40

    CLOUD_COVER_MAX: int = 20
    MIN_HOTSPOT_AREA_HA: float = 0.01

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
