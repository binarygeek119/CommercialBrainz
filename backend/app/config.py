from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CommercialBrainz"
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://commercialbrainz:commercialbrainz@localhost:5432/commercialbrainz"
    database_url_sync: str = "postgresql://commercialbrainz:commercialbrainz@localhost:5432/commercialbrainz"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-to-a-long-random-string"
    access_token_expire_minutes: int = 10080
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    edit_open_days: int = 7
    edit_early_close_votes: int = 3
    voting_min_account_days: int = 14
    voting_min_accepted_edits: int = 10
    voting_no_vote_extension_hours: int = 72

    rate_limit_anon: float = 1.0
    rate_limit_auth: float = 5.0

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@commercialbrainz.org"
    dmca_contact: str = "dmca@commercialbrainz.org"

    gcs_dump_bucket: str = ""
    gcp_project_id: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
