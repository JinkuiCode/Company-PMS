from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "PMS 项目管理系统"
    DEBUG: bool = True

    # 数据库
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "root123456"
    DB_NAME: str = "pms"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )

    # JWT
    SECRET_KEY: str = "pms-dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 小时

    # 泛微 OA SSO 单点登录
    SSO_ENABLED: bool = True
    SSO_SECRET_KEY: str = "weaver-sso-secret-32byte-key!!"  # 与泛微约定，32字节用于 AES-256
    SSO_AUTO_CREATE_USER: bool = True  # SSO 用户首次登录自动创建账号
    SSO_TOKEN_EXPIRE_SECONDS: int = 300  # token 有效期 5 分钟
    SSO_OA_DOMAIN: str = "oa.aelsystem.cn"  # OA 域名，用于 Referer 校验（空字符串跳过校验）


settings = Settings()
