import os
from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from typing import Optional, Literal


class Settings(BaseSettings):

    # RabbitMQ設定
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_RETRY_COUNT: int = 5
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

settings = Settings()