from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.authorization import get_current_user_context, require_permission
from app.schemas.dict import DictItemCreate, DictItemUpdate
from app.services import dict as dict_service

router = APIRouter(prefix="/api/dicts", tags=["数据字典"])


@router.get(
    "",
    summary="注册业务枚举列表",
    dependencies=[Depends(require_permission("system:enum:view"))],
)
def list_dicts(db: Session = Depends(get_db)):
    return dict_service.get_dict_list(db)


@router.get("/{dict_id}/items", summary="获取枚举值列表", dependencies=[Depends(require_permission("system:enum:view"))])
def list_dict_items(dict_id: int, db: Session = Depends(get_db)):
    return dict_service.get_dict_items(db, dict_id)


@router.post("/{dict_id}/items", summary="新增枚举项")
def create_dict_item(
    dict_id: int,
    data: DictItemCreate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:enum:add")),
):
    return dict_service.create_dict_item(db, dict_id, data, operator_id=scope_ctx["user_id"], request=request)


@router.put("/items/{item_id}", summary="编辑枚举项")
def update_dict_item(
    item_id: int,
    data: DictItemUpdate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:enum:edit")),
):
    return dict_service.update_dict_item(db, item_id, data, operator_id=scope_ctx["user_id"], request=request)


@router.delete("/items/{item_id}", summary="删除枚举项")
def delete_dict_item(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:enum:delete")),
):
    return dict_service.delete_dict_item(db, item_id, operator_id=scope_ctx["user_id"], request=request)


# ==================== 按编码查询（供前端表单下拉使用） ====================
@router.get("/code/{dict_code}", summary="按编码查询枚举值")
def get_dict_by_code(
    dict_code: str,
    db: Session = Depends(get_db),
    _scope_ctx: dict = Depends(get_current_user_context),
):
    """已登录用户读取表单枚举值。"""
    result = dict_service.get_dict_by_code(db, dict_code)
    if not result:
        return {"dict_code": dict_code, "dict_name": "", "items": []}
    return result
