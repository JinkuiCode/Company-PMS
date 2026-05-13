from pydantic import BaseModel, Field
from datetime import datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: int
    username: str
    real_name: str
    dept_id: int | None
    mobile: str | None
    status: int
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
