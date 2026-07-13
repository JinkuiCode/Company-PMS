from pydantic import BaseModel, Field
from datetime import datetime


class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False  # 是否启用长期免密登录


class AutoLoginRequest(BaseModel):
    remember_token: str  # 免密登录令牌


class SsoLoginRequest(BaseModel):
    """OA JSP 重定向携带的 SSO 免密登录参数"""
    sso_login_id: str  # OA 用户的 loginId
    ts: int  # 秒级时间戳（防重放）
    sign: str  # HMAC-SHA256 签名（防伪造）


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    remember_token: str | None = None  # 勾选记住我时返回长期令牌


class UserInfo(BaseModel):
    id: int
    username: str
    real_name: str
    dept_id: int | None
    mobile: str | None
    status: int
    role_codes: list[str] = []
    permissions: list[str] = []
    data_scope: int = 1
    product_lines: list[str] | None = None
    model_config = {"from_attributes": True}


# ========== 用户管理 CRUD ==========
class UserCreate(BaseModel):
    username: str = Field(..., max_length=64)
    real_name: str = Field(..., max_length=64)
    password: str = Field(..., max_length=32)
    dept_id: int | None = None
    mobile: str | None = None
    status: int = 1
    role_ids: list[int] = []


class UserUpdate(BaseModel):
    real_name: str | None = None
    password: str | None = None  # 重置密码，变更后所有免密令牌失效
    dept_id: int | None = None
    mobile: str | None = None
    status: int | None = None
    role_ids: list[int] | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    real_name: str
    dept_id: int | None
    mobile: str | None
    status: int
    role_ids: list[int] = []  # 关联的角色ID列表
    role_names: list[str] = []  # 关联的角色名称列表
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    total: int
    items: list[UserResponse]
