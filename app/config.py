"""Every environment variable this app reads, read once, here.

DATABASE_URL is honoured verbatim when set. That is deliberate and it is the
rule most likely to confuse: a leftover value in a machine's .env beats the
POSTGRES_* parts and breaks that machine, with an error that points at the
database rather than at the file.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ENVS = ("development", "production")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "production"

    @field_validator("app_env")
    @classmethod
    def app_env_is_one_of_the_known_ones(cls, value: str) -> str:
        """Reject a typo rather than resolve it.

        `APP_ENV=prod` is not production. Unvalidated, a predicate written as
        "not development" would read it as a real environment and harden a
        development machine; written the other way round it would soften a real
        one. Neither failure announces itself, so the value is refused at
        startup instead.
        """
        if value not in APP_ENVS:
            raise ValueError(f"APP_ENV must be one of {', '.join(APP_ENVS)}, not {value!r}")
        return value

    @property
    def is_development(self) -> bool:
        """Deliberately the NARROW predicate.

        There is no `is_production`, and that is the point: any environment
        name added later is treated as a real one by default and gets the
        careful behaviour, rather than escaping it by not being named here.
        """
        return self.app_env == "development"

    postgres_user: str = "food"
    postgres_password: str = ""
    postgres_db: str = "food"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    database_url: str | None = None

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
