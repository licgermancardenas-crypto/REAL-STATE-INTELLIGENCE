from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Real State Intelligence API"
    debug: bool = False

    database_url: str
    secret_key: str = "changeme"

    allowed_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"


settings = Settings()
