"""Master-data transactions; API callers enforce module permissions separately."""
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from app.models.product_line import SysProductLine, SysRoleProductLine
from app.models.project import PmsProjectArchive
from app.services.operation_log import record_operation_log


def get_product_line(db, line_id):
    line = db.get(SysProductLine, line_id)
    if line is None:
        raise HTTPException(404, '产品线不存在')
    return line


def snapshot(line):
    return {key: getattr(line, key) for key in (
        'id', 'source_key', 'organization_id', 'organization_code', 'organization_name',
        'display_name', 'is_enabled', 'sort', 'updated_at')}


def list_product_lines(db, keyword='', page=1, page_size=50):
    if not 1 <= page_size <= 500 or page < 1 or len(keyword) > 100:
        raise HTTPException(422, '分页或搜索参数无效')
    query = db.query(SysProductLine)
    if keyword.strip():
        value = keyword.strip()
        query = query.filter(SysProductLine.display_name.contains(value, autoescape=True)
                             | SysProductLine.organization_name.contains(value, autoescape=True)
                             | SysProductLine.organization_code.contains(value, autoescape=True))
    total = query.count()
    items = query.order_by(SysProductLine.sort, SysProductLine.id).offset((page-1)*page_size).limit(page_size).all()
    return {'items': [snapshot(row) for row in items], 'total': total}


def _log(db, action, line, operator_id, before=None, after=None):
    record_operation_log(db, module='系统管理', action=action, entity_type='sys_product_line',
                         entity_id=line.id, entity_name=line.display_name, operator_id=operator_id,
                         summary={'create': '新增产品线', 'update': '修改产品线', 'delete': '删除产品线'}[action],
                         before_data=before, after_data=after)


def create_product_line(db, data, *, organization, operator_id):
    if not organization.active or organization.organization_id != data.organization_id or organization.source_key != 'kingdee':
        raise HTTPException(422, '请选择有效的金蝶组织')
    name = (data.display_name or organization.name).strip()
    if not 1 <= len(name) <= 128 or len(name.casefold()) > 128:
        raise HTTPException(422, '产品线名称须为 1-128 个字符')
    line = SysProductLine(source_key=organization.source_key, organization_id=organization.organization_id,
        organization_code=organization.code, organization_name=organization.name, display_name=name,
        name_key=name.casefold(), sort=data.sort, created_by=operator_id, updated_by=operator_id)
    try:
        db.add(line)
        db.flush()
        _log(db, 'create', line, operator_id, after=snapshot(line))
        db.commit()
        db.refresh(line)
        return line
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '组织已纳入或产品线名称重复') from None
    except Exception:
        db.rollback()
        raise


def update_product_line(db, line_id, data, *, operator_id):
    line = get_product_line(db, line_id)
    before = snapshot(line)
    values = data.model_dump(exclude_unset=True, exclude={'expected_updated_at'})
    if 'display_name' in values:
        values['name_key'] = values['display_name'].casefold()
        if len(values['name_key']) > 128:
            raise HTTPException(422, '产品线名称过长')
    values.update(updated_by=operator_id, updated_at=max(datetime.now(), line.updated_at + timedelta(microseconds=1)))
    try:
        changed = db.execute(update(SysProductLine).where(SysProductLine.id == line_id,
            SysProductLine.updated_at == data.expected_updated_at).values(**values).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise HTTPException(409, '产品线已被修改，请刷新后重试')
        db.refresh(line)
        _log(db, 'update', line, operator_id, before, snapshot(line))
        db.commit()
        return line
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '产品线名称重复') from None
    except Exception:
        db.rollback()
        raise


def delete_product_line(db, line_id, *, operator_id):
    line = get_product_line(db, line_id)
    archive_ref = select(PmsProjectArchive.id).where(PmsProjectArchive.business_product_line_id == line_id).exists()
    role_ref = select(SysRoleProductLine.id).where(SysRoleProductLine.product_line_id == line_id).exists()
    try:
        before = snapshot(line)
        result = db.execute(delete(SysProductLine).where(SysProductLine.id == line_id, ~archive_ref, ~role_ref))
        if result.rowcount != 1:
            raise HTTPException(409, '产品线已被引用，只能禁用')
        _log(db, 'delete', line, operator_id, before=before)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '产品线已被引用，只能禁用') from None
    except Exception:
        db.rollback()
        raise
