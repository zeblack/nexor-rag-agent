from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    api_auth_token: str

    vpn_check_interval_seconds: int = 30
    vpn_expected_ip: str = ""
    vpn_ip_check_url: str = "https://api.ipify.org"

    embedding_model_name: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"

    models_yaml_path: str = "config/models.yaml"


settings = Settings()
