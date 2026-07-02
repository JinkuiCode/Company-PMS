from pydantic import BaseModel, Field
from datetime import datetime


# ========== 角色 ==========
class RoleBase(BaseModel):
    role_name: str = Field(..., max_length=64)
    role_code: str = Field(..., max_length=64)
    data_scope: int = Field(default=1, ge=1, le=4)
    product_lines: str | None = None
    status: int = Field(default=1)
    remark: str | None = None


class RoleCreate(RoleBase):
    menu_ids: list[int] = []  # 创建时可同时分配菜单权限


class RoleUpdate(BaseModel):
    role_name: str | None = None
    data_scope: int | None = None
    product_lines: str | None = None
    status: int | None = None
    remark: str | None = None
    menu_ids: list[int] | None = None  # 分配菜单权限时使用


class RoleResponse(RoleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class RoleListResponse(BaseModel):
    total: int
    items: list[RoleResponse]


# ========== 菜单 ==========
class MenuBase(BaseModel):
    parent_id: int = 0
    menu_name: str = Field(..., max_length=64)
    menu_type: str = Field(default="C", max_length=1)  # M目录 C菜单 B按钮
    permission_code: str | None = None
    path: str | None = None
    component: str | None = None
    icon: str | None = None
    sort: int = 0
    visible: int = 1
    status: int = 1


class MenuCreate(MenuBase):
    pass


class MenuUpdate(BaseModel):
    parent_id: int | None = None
    menu_name: str | None = None
    menu_type: str | None = None
    permission_code: str | None = None
    path: str | None = None
    component: str | None = None
    icon: str | None = None
    sort: int | None = None
    visible: int | None = None
    status: int | None = None


class MenuResponse(MenuBase):
    id: int
    children: list["MenuResponse"] = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ========== 部门 ==========
class DeptBase(BaseModel):
    parent_id: int = 0
    dept_name: str = Field(..., max_length=64)
    leader_id: int | None = None
    sort: int = 0
    status: int = 1


class DeptCreate(DeptBase):
    pass


class DeptUpdate(BaseModel):
    parent_id: int | None = None
    dept_name: str | None = None
    leader_id: int | None = None
    sort: int | None = None
    status: int | None = None


class DeptResponse(DeptBase):
    id: int
    children: list["DeptResponse"] = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
