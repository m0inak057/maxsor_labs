from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    database_url: str = "sqlite:///./support.db"
    knowledge_base_dir: str = "./knowledge_base"

    class Config:
        env_file = ".env"


settings = Settings()
