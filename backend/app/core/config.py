from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "PMS 项目管理系统"
    DEBUG: bool = True

    # 数据库（MSSQL 2017）
    DB_HOST: str = "10.10.1.149"
    DB_PORT: int = 1433
    DB_USER: str = "sa-jinky"
    DB_PASSWORD: str = "Qwerty1234."
    DB_NAME: str = "PMS"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mssql+pyodbc://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?driver=ODBC+Driver+17+for+SQL+Server"
            f"&charset=utf8"
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

    # 金蝶云星空 ERP 对接（Session 认证模式）
    K3_URL: str = "http://10.10.1.248/k3cloud"  # 金蝶服务器地址（内网用 http 避免证书问题）
    K3_ACCT_ID: str = "6a1fd19d9e068f"          # 账套 ID
    K3_USERNAME: str = "I0001"                   # 金蝶登录账号
    K3_PASSWORD: str = "Jsydadmin123."           # 金蝶登录密码


settings = Settings()
