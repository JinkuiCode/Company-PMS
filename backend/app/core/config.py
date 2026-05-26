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

    # 免密登录 Remember Me
    REMEMBER_TOKEN_EXPIRE_DAYS: int = 180  # 默认半年，可调整为 365（一年）

    # 泛微 OA SSO 单点登录
    SSO_ENABLED: bool = True
    SSO_SECRET_KEY: str = "weaver-sso-secret-32byte-key!!"  # 与泛微约定，32字节用于 AES-256
    SSO_AUTO_CREATE_USER: bool = True  # SSO 用户首次登录自动创建账号
    SSO_TOKEN_EXPIRE_SECONDS: int = 300  # token 有效期 5 分钟
    SSO_OA_DOMAIN: str = "oa.aelsystem.cn"  # OA 域名，用于 Referer 校验（空字符串跳过校验）

    # OA 统一认证中心配置
    OA_BASE_URL: str = "http://10.10.1.149:8081"
    OA_APP_ID: str = "ssss"  # 认证应用标识（TODO: 切回 PMS 应用 1b26f14a-...）
    OA_APP_SECRET: str = "yjcust"  # 认证应用密钥
    OA_GET_TOKEN_URL: str = "http://10.10.1.149:8081/ssologin/getToken"
    OA_CHECK_TOKEN_URL: str = "http://10.10.1.149:8081/ssologin/checkToken"
    OA_LOGIN_URL: str = "http://10.10.1.149:8081/login/login.jsp"
    PMS_CALLBACK_URL: str = "http://10.10.91.60:5174/sso/callback"
    PMS_FRONTEND_URL: str = "http://10.10.91.60:5174"
    OA_SERVICE_VALIDATE_URL: str = "http://10.10.1.149:8081/sso/serviceValidate"  # CAS ticket 验证端点
    OA_CHECK_USER_PWD_URL: str = "http://10.10.1.149:8081/ssologin/checkUserPassword"  # OA 密码验证 REST 端点
    OA_HRM_SERVICE_URL: str = "http://10.10.1.149:8081/services/HrmService"  # OA 人力资源 WebService（checkUser SOAP）


settings = Settings()
