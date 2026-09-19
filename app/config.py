"""Every environment variable this app reads, read once, here.

DATABASE_URL is honoured verbatim when set. That is deliberate and it is the
rule most likely to confuse: a leftover value in a machine's .env beats the
POSTGRES_* parts and breaks that machine, with an error that points at the
database rather than at the file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "production"

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
