"""Explicit product-line grants, with no role-code or empty-selection bypass."""
from fastapi import HTTPException
from app.models.product_line import SysProductLine, SysRoleProductLine
from app.models.rbac import SysRole


def get_authorized_product_line_ids(db, roles):
    role_ids = [role.id for role in roles]
    if not role_ids:
        return []
    rows = (db.query(SysRoleProductLine.product_line_id)
            .join(SysRole, SysRole.id == SysRoleProductLine.role_id)
            .join(SysProductLine, SysProductLine.id == SysRoleProductLine.product_line_id)
            .filter(SysRole.id.in_(role_ids), SysRole.status == 1)
            .distinct().order_by(SysRoleProductLine.product_line_id).all())
    return [line_id for (line_id,) in rows]


def require_line_access(db, context, line_id, *, selectable=False, lock=False):
    if not context or line_id not in (context.get('product_line_ids') or []):
        raise HTTPException(404, '产品线不存在或无权访问')
    if lock:
        query = db.query(SysProductLine).filter(SysProductLine.id == line_id).populate_existing()
        if db.bind.dialect.name == 'mssql':
            query = query.with_hint(SysProductLine, 'WITH (UPDLOCK, HOLDLOCK)', dialect_name='mssql')
        else:
            query = query.with_for_update()
        line = query.one_or_none()
    else:
        line = db.get(SysProductLine, line_id)
    if line is None:
        raise HTTPException(404, '产品线不存在或无权访问')
    if selectable and not line.is_enabled:
        raise HTTPException(422, '产品线已禁用，不可新增或变更选入')
    return line
