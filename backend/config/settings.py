from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Polymarket API
    poly_private_key: str = Field(default="", description="EOA private key hex")
    poly_api_key: str = Field(default="", description="L2 API key")
    poly_api_secret: str = Field(default="", description="L2 API secret")
    poly_api_passphrase: str = Field(default="", description="L2 API passphrase")

    clob_host: str = "https://clob.polymarket.com"
    gamma_host: str = "https://gamma-api.polymarket.com"
    ws_host: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    # Trading parameters
    max_capital_usd: float = 500.0
    max_position_pct: float = 0.03
    daily_drawdown_limit: float = 0.08
    min_edge_cents: float = 6.0
    oracle_risk_buffer_a: float = 0.005
    oracle_risk_buffer_default: float = 0.02
    kelly_fraction: float = 0.25

    # Safety
    sim_mode: bool = True

    # Infrastructure
    database_url: str = "sqlite+aiosqlite:///./trading.db"
    log_level: str = "INFO"
    backend_port: int = 8000
    backend_host: str = "0.0.0.0"

    # Alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


settings = Settings()
