from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List

class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: List[int]
    RESORT_PHONE: str = "+380000000000"
    RESORT_ADDRESS: str = "Чернівецька область"
    RESORT_INSTAGRAM: str = "@ukrainski_maldivi"
    MONOBANK_CARD: str
    MONOBANK_CARD_OWNER: str
    WEEKDAY_PRICE: int = 1700
    WEEKEND_PRICE: int = 2200
    PAYMENT_TIMEOUT_HOURS: int = 24

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        elif isinstance(v, int):
            return [v]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
