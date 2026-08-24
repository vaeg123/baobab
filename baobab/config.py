from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valeurs de développement uniquement : si l'une d'elles est encore active
# en environnement de production, le démarrage de l'application échoue
# volontairement (fail fast / fail loud) plutôt que de tourner avec un
# secret public et prévisible.
_INSECURE_DEFAULTS = {
    "dev-secret-key",
    "dev-jwt-secret-change-me",
    "change-me-in-production",
    "baobab-superadmin-dev",
    "",
}
_MIN_SECRET_LENGTH = 32


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
    jwt_secret: str = "dev-jwt-secret-change-me"
    avocassist_integration_secret: str = ""

    # Alias explicites : ces variables existent en production sous le
    # préfixe BAOBAB_ (cohérence avec .env.example et l'historique du
    # projet) plutôt que le nom de champ Pydantic auto-dérivé.
    superadmin_bootstrap_token: str = Field(default="", validation_alias="BAOBAB_SUPERADMIN_TOKEN")
    admin_key: str = Field(default="", validation_alias="BAOBAB_ADMIN_KEY")

    # Origines autorisées pour le CORS, séparées par des virgules.
    # Ne JAMAIS mettre "*" en production : les cookies/tokens applicatifs
    # ne doivent être lisibles que par les origines explicitement listées.
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # Expose /api/docs et /api/redoc même en production si explicitement demandé.
    expose_api_docs: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _reject_insecure_defaults_in_production(self) -> "Settings":
        if not self.is_production:
            return self

        problems: list[str] = []
        for field_name in ("secret_key", "jwt_secret", "superadmin_bootstrap_token", "admin_key"):
            value = getattr(self, field_name)
            if value in _INSECURE_DEFAULTS:
                problems.append(f"{field_name} : valeur absente ou par défaut non sécurisée")
            elif len(value) < _MIN_SECRET_LENGTH:
                problems.append(
                    f"{field_name} : {len(value)} caractères, minimum requis {_MIN_SECRET_LENGTH}"
                )

        if "*" in self.cors_origins_list:
            problems.append("cors_allowed_origins : '*' interdit en production")

        if problems:
            details = "\n  - ".join(problems)
            raise ValueError(
                "Configuration de production non sécurisée, démarrage refusé :\n  - "
                + details
                + "\nPositionnez des secrets forts (>= 32 caractères, générés aléatoirement, "
                "ex. `openssl rand -hex 32`) via les variables d'environnement."
            )
        return self


settings = Settings()
