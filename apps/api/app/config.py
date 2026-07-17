from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Manus SwarmDesk API"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "swarmdesk"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    use_memory_store: bool = False

    # Preferred provider: auto | anthropic | google | openai | xai
    llm_provider: str = "auto"

    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-5"

    google_api_key: str = ""
    gemini_api_key: str = ""
    google_model: str = "gemini-2.0-flash"

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4.1-mini"

    xai_api_key: str = ""
    xai_model: str = "grok-3-mini"

    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096


settings = Settings()
