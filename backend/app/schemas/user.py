from typing import Annotated
from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator
from datetime import datetime

EmployeeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
MobileText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]
Mailbox = Annotated[EmailStr, Field(max_length=254)]


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
    must_change_password: bool = False
    access_token: str
    token_type: str = "bearer"
    remember_token: str | None = None  # 勾选记住我时返回长期令牌


class UserInfo(BaseModel):
    email: EmailStr | None = None
    must_change_password: bool = False
    id: int
    username: str
    real_name: str
    dept_id: int | None
    mobile: str | None
    status: int
    role_codes: list[str] = []
    home_path: str = "/403"
    permissions: list[str] = []
    data_scope: int = 1
    product_category_ids: list[int] | None = None
    product_line_ids: list[int] = Field(default_factory=list)
    model_config = {"from_attributes": True}


# ========== 用户管理 CRUD ==========
class UserCreate(BaseModel):
    model_config = {"extra": "forbid"}
    username: EmployeeText = Field(..., title="账号（工号）")
    real_name: EmployeeText = Field(..., title="员工姓名")
    email: Mailbox | None = None
    dept_id: int | None = None
    mobile: MobileText | None = None
    status: int = Field(default=1, ge=0, le=1, strict=True)
    role_ids: list[int] = []


class UserUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    real_name: EmployeeText | None = None
    email: Mailbox | None = None
    dept_id: int | None = None
    mobile: MobileText | None = None
    status: int | None = Field(default=None, ge=0, le=1, strict=True)
    role_ids: list[int] | None = None

    @field_validator("real_name", "status", mode="before")
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("该字段不可为空")
        return value


class UserResponse(BaseModel):
    email: EmailStr | None = None
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


class ChangePasswordRequest(BaseModel):
    model_config = {"extra": "forbid"}
    new_password: str = Field(min_length=8, max_length=64)
    confirm_password: str = Field(min_length=8, max_length=64)
