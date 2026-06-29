from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    telegram_token: str
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"

    middleware_url: str = "http://actual-http-api:5007"
    middleware_api_key: str

    budget_sync_id: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


config = Config()
