from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://baobab:baobab@localhost:5432/baobab"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "baobab"
    secret_key: str = "dev-secret-key"
    environment: str = "development"
    resend_api_key: str = ""
    resend_from: str = "BAOBAB <contact@vaeg-conformite.fr>"
    app_url: str = "https://www.vaegbaobab.com"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_currency: str = "xof"


settings = Settings()
