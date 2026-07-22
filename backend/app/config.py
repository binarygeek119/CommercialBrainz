import os
from functools import lru_cache

from pydantic import model_validator
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
    session_token_expire_minutes: int = 1440
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    app_public_url: str = "http://localhost:5173"

    edit_open_days: int = 14
    split_open_days: int = 90
    split_vote_threshold: int = 20
    edit_early_close_votes: int = 3
    brand_early_close_votes: int = 10
    voting_min_account_days: int = 14
    voting_min_accepted_edits: int = 10
    voting_no_vote_extension_hours: int = 72

    rate_limit_anon: float = 1.0
    rate_limit_auth: float = 5.0

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "commercialbrainz@outlook.com"
    dmca_contact: str = "commercialbrainz@outlook.com"

    password_reset_expire_minutes: int = 60
    email_verification_expire_minutes: int = 1440

    submit_slots_base: int = 1
    submit_slots_max: int = 20
    submit_slots_points_per_slot: int = 20
    reputation_point_value: float = 0.25

    gcs_dump_bucket: str = ""
    gcp_project_id: str = ""

    api_public_url: str = "http://localhost:8000"
    archive_export_dir: str = "exports/archive-org"
    ia_access_key: str = ""
    ia_secret_key: str = ""
    ia_collection: str = "commercialbrainz"
    ia_skip_upload: bool = False

    hash_temp_dir: str = "/tmp/commercialbrainz-hash"
    ytdlp_format: str = (
        "bv*[height<=480]+ba/b[height<=480]/bv*+ba/b"
    )
    # Optional YouTube auth for yt-dlp bot / age-gate blocks.
    # Admin panel writes the managed path; env override wins when that file exists.
    ytdlp_cookies_managed_path: str = "/data/ytdlp/cookies.txt"
    ytdlp_cookies_file: str = ""
    # Host-only fallback, e.g. "chrome" or "chrome:Profile 1" — usually unavailable in Docker.
    ytdlp_cookies_from_browser: str = ""
    hash_max_file_mb: int = 200
    # Max Hamming distance for perceptual-hash duplicate / lookup matches (64-bit pHash).
    phash_duplicate_threshold: int = 8
    fingerprint_max_retries: int = 3
    fingerprint_retry_delay_minutes: int = 15
    bulk_submit_min_reputation: float = 500.0
    bulk_submit_max_playlist_items: int = 50
    registration_invite_only: bool = False
    thumbnail_max_bytes: int = 2 * 1024 * 1024
    thumbnail_upload_dir: str = "/data/thumbnails"
    logo_upload_dir: str = "/data/logos"
    logo_max_bytes: int = 5 * 1024 * 1024

    @model_validator(mode="after")
    def normalize_service_urls_for_docker(self) -> "Settings":
        """Inside Compose, .env often points at localhost — use service hostnames instead."""
        if os.getenv("RUNNING_IN_DOCKER") != "1":
            return self
        if "@localhost" in self.database_url or "@127.0.0.1" in self.database_url:
            self.database_url = self.database_url.replace(
                "@localhost", "@postgres"
            ).replace("@127.0.0.1", "@postgres")
        if "@localhost" in self.database_url_sync or "@127.0.0.1" in self.database_url_sync:
            self.database_url_sync = self.database_url_sync.replace(
                "@localhost", "@postgres"
            ).replace("@127.0.0.1", "@postgres")
        if "localhost" in self.redis_url or "127.0.0.1" in self.redis_url:
            self.redis_url = self.redis_url.replace(
                "localhost", "redis"
            ).replace("127.0.0.1", "redis")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
