"""只读系统字段目录 API。"""
from fastapi import APIRouter, Depends, Query

from app.services.authorization import require_permission
from app.services.field_catalog import query_field_catalog


router = APIRouter(prefix="/api/field-catalog", tags=["数据字典"])


@router.get("", summary="查询系统字段目录")
def list_field_catalog(
    keyword: str | None = None,
    module: str | None = None,
    value_type: str | None = None,
    source_type: str | None = None,
    enum_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    _scope_ctx: dict = Depends(require_permission("system:dict:view")),
):
    return query_field_catalog(
        keyword=keyword,
        module=module,
        value_type=value_type,
        source_type=source_type,
        enum_only=enum_only,
        page=page,
        page_size=page_size,
    )
