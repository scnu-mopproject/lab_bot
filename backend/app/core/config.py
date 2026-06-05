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

    # 学校统一认证 (华南师大统一身份认证平台 / OAuth2.0)
    # 三档环境只靠 .env 切换：mock(本地) -> 测试环境 -> 生产环境
    sso_mock: bool = True
    # [认证服务地址]：生产为 https://sso.scnu.edu.cn/AccountService；
    # 测试环境地址以审批回执邮件为准，届时改这一项即可切到测试环境。
    sso_base_url: str = "https://sso.scnu.edu.cn/AccountService"
    # 回调地址 redirect_uri：必须在 SSO 登记的域名之下、完整 URL、最好不带参数。
    sso_service_url: str = "https://your-backend.example.com/api/auth/sso/callback"
    # 接入申请通过后由统一认证平台分配
    sso_client_id: str = ""
    sso_client_secret: str = ""
    # 微信小程序的 APPID（小程序登录场景需要；通常与 wechat_appid 相同）
    sso_applet_id: str = ""

    # 预约策略：是否自动通过（否则需管理员审批）
    booking_auto_approve: bool = True

    # 管理员白名单：逗号分隔的 sso_id（学号/工号）。命中者登录即自动赋予 admin 角色。
    admin_sso_ids: str = ""

    @property
    def admin_sso_id_set(self) -> set[str]:
        return {s.strip() for s in self.admin_sso_ids.split(",") if s.strip()}

    # AI
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    # 向量化（文档问答 RAG）。provider: local | bge | openai-compatible
    embedding_provider: str = "local"
    embedding_dim: int = 512          # local 方案维度
    embedding_model: str = ""         # bge 模型名 或 云端 embedding 模型名
    embedding_api_key: str = ""
    embedding_base_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
