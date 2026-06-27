from pydantic_settings import BaseSettings


class Config(BaseSettings, case_sensitive=False):
    telegram_token: str
    gemini_api_key: str

    middleware_url: str = "http://actual-http-api:5007"
    middleware_api_key: str

    budget_sync_id: str

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


config = Config()
