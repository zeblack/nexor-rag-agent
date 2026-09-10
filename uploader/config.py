from dataclasses import dataclass

from dotenv import dotenv_values


@dataclass
class UploaderConfig:
    api_url: str
    api_token: str
    max_retries: int = 3
    timeout_seconds: float = 120.0
    poll_interval_seconds: float = 3.0
    poll_timeout_seconds: float = 300.0
    allow_insecure_local: bool = False

    def __post_init__(self):
        if not self.allow_insecure_local and not self.api_url.startswith("https://"):
            raise ValueError(
                f"API_URL '{self.api_url}' não usa HTTPS. Use uma URL https:// "
                "ou passe --allow-insecure-local explicitamente para teste local sem internet."
            )


def load_config(env_path: str = ".env", allow_insecure_local: bool = False) -> UploaderConfig:
    values = dotenv_values(env_path)
    return UploaderConfig(
        api_url=values.get("API_URL", "").rstrip("/"),
        api_token=values.get("API_TOKEN", ""),
        max_retries=int(values.get("MAX_RETRIES", 3)),
        timeout_seconds=float(values.get("TIMEOUT_SECONDS", 120.0)),
        poll_interval_seconds=float(values.get("POLL_INTERVAL_SECONDS", 3.0)),
        poll_timeout_seconds=float(values.get("POLL_TIMEOUT_SECONDS", 300.0)),
        allow_insecure_local=allow_insecure_local,
    )
