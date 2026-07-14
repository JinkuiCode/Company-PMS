"""业务字段规则 API。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.field_policy import FieldPolicyBatchUpdate
from app.services.authorization import require_permission
from app.services.field_policy import (
    get_effective_field_policies,
    reset_field_policies,
    update_field_policies,
)


router = APIRouter(prefix="/api/field-policies", tags=["字段规则"])


@router.get("", summary="查询生效字段规则")
def list_field_policies(
    module: str,
    db: Session = Depends(get_db),
    _scope_ctx: dict = Depends(require_permission("system:field-policy:view")),
):
    return get_effective_field_policies(db, module)


@router.put("/{module}", summary="批量保存字段规则")
def save_field_policies(
    module: str,
    data: FieldPolicyBatchUpdate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:field-policy:edit")),
):
    return update_field_policies(
        db,
        module,
        data,
        operator_id=scope_ctx["user_id"],
        request=request,
    )


@router.post("/{module}/reset", summary="恢复代码默认字段规则")
def reset_module_field_policies(
    module: str,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:field-policy:edit")),
):
    return reset_field_policies(
        db,
        module,
        operator_id=scope_ctx["user_id"],
        request=request,
    )
