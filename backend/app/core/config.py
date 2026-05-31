"""应用配置：从环境变量 / .env 读取。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "lab_bot"
    database_url: str = "sqlite:///./lab_bot.db"

    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 天

    # 微信小程序
    wechat_appid: str = ""
    wechat_secret: str = ""
    wechat_mock: bool = True

    # 学校统一认证 (CAS)
    sso_base_url: str = "https://sso.scnu.edu.cn"
    sso_service_url: str = "https://your-backend.example.com/api/auth/sso/callback"
    sso_mock: bool = True

    # 预约策略：是否自动通过（否则需管理员审批）
    booking_auto_approve: bool = True

    # AI
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
