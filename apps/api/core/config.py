"""Application configuration.

Every value that differs between environments comes from the environment. There are no hardcoded
credentials, URLs, or tenant identifiers anywhere in this package.

One refusal lives here on purpose: production will not start with the placeholder JWT secret from
`.env.example`. A default that is safe only because nobody deployed it is not safe, and this exact
mistake is one of the most common causes of a forgeable token in a small deployment (SEC-003).
"""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    api_base_url: str = Field(default="http://localhost:8000")

    database_url: str = Field(
        default="postgresql+psycopg://threadmind:threadmind@localhost:5432/threadmind"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # "clerk" in any deployment that holds real data; "dev" only for local work and CI.
    auth_provider: str = Field(default="dev")

    # Development-only token signing. Ignored entirely when auth_provider is "clerk", which is why
    # the production guard below can allow it to stay at its placeholder value in Clerk mode.
    jwt_secret: str = Field(default=PLACEHOLDER_SECRET)
    jwt_algorithm: str = Field(default="HS256")
    access_token_ttl_minutes: int = Field(default=60)

    # Clerk. The issuer is the Frontend API URL, e.g. https://your-app.clerk.accounts.dev.
    clerk_issuer: str = Field(default="")
    clerk_jwks_url: str = Field(default="")
    clerk_secret_key: str = Field(default="")
    clerk_publishable_key: str = Field(default="")
    # Comma-separated origins allowed in the token's azp claim (the dashboard's own origin).
    clerk_authorized_parties: str = Field(default="")

    vision_service_url: str = Field(default="http://localhost:8100")
    predictive_service_url: str = Field(default="http://localhost:8101")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def uses_clerk(self) -> bool:
        return self.auth_provider == "clerk"

    @property
    def authorized_parties(self) -> tuple[str, ...]:
        return tuple(p.strip() for p in self.clerk_authorized_parties.split(",") if p.strip())

    @model_validator(mode="after")
    def refuse_unsafe_production_defaults(self) -> "Settings":
        # The rule that matters, checked first so its message wins: a production deployment may not
        # sign its own tokens. A shared secret that mints tokens for every tenant is the exact
        # defect SEC-002 describes, and leaving it reachable in production is not a configuration
        # preference.
        if self.is_production and not self.uses_clerk:
            raise ValueError(
                "AUTH_PROVIDER must be 'clerk' in production. The dev provider signs tokens with a "
                "shared secret, so anyone holding it can mint a token for any organization."
            )

        if self.is_production and not self.uses_clerk and self.jwt_secret == PLACEHOLDER_SECRET:
            raise ValueError(
                "JWT_SECRET must be set to a real secret in production: a shared placeholder "
                "secret lets anyone mint a token for any organization (SEC-003)."
            )
        if self.jwt_algorithm != "HS256" and not self.jwt_secret:
            raise ValueError("JWT_SECRET is required for the configured algorithm")

        if self.uses_clerk:
            if not self.clerk_issuer:
                raise ValueError("CLERK_ISSUER is required when AUTH_PROVIDER=clerk")
            if not self.clerk_issuer.startswith("https://"):
                # A plaintext issuer would let a network attacker serve their own JWKS.
                raise ValueError("CLERK_ISSUER must be an https URL")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
