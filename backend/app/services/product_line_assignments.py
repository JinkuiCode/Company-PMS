"""Explicit historical assignments, separate from schema upgrades and startup."""
import hashlib
import json
from collections import Counter

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import inspect, text
from app.models.database_revision import PmsDatabaseRevision
from app.models.product_line import SysProductLine, SysRoleProductLine
from app.models.project import PmsProjectArchive, PmsProject
from app.models.rbac import SysRole
from app.models.operation_log import SysOperationLog
from app.services.authorization import build_authorization_context
from app.services.database_revision import CURRENT_DATABASE_REVISION
from app.services.operation_log import record_operation_log


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class LineMapping(StrictRecord):
    key: str = Field(pattern=r'^kingdee:[1-9][0-9]*$')
    product_line_id: int = Field(gt=0)
    organization_id: int = Field(gt=0)


class ArchiveMapping(StrictRecord):
    archive_id: int = Field(gt=0)
    project_code: str = Field(min_length=1, max_length=100)
    legacy_product_line_id: int | None
    target_product_line_key: str


class RoleMapping(StrictRecord):
    role_id: int = Field(gt=0)
    product_line_keys: list[str]


class LegacyOrganizationMapping(StrictRecord):
    legacy_product_line_id: int = Field(gt=0)
    organization_id: int = Field(gt=0)


class AssignmentPlan(StrictRecord):
    source_revision: str
    source_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    lines: list[LineMapping]
    archives: list[ArchiveMapping]
    roles: list[RoleMapping]


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), default=str).encode()).hexdigest()


def _rows(db, model, fields, *, lock=False):
    inspector = inspect(db.connection())
    if not inspector.has_table(model.__tablename__):
        return []
    present = {item['name'] for item in inspector.get_columns(model.__tablename__)}
    names = [name for name in fields if name in present]
    query = db.query(*(getattr(model, name) for name in names)).order_by(model.id)
    if lock and db.bind.dialect.name == 'mssql':
        query = query.with_hint(model, 'WITH (UPDLOCK, HOLDLOCK)', dialect_name='mssql')
    return [{name: values.get(name) for name in fields}
            for row in query.all() for values in [dict(zip(names, row))]]


def snapshot(db, *, lock=False):
    """Also reads pre-upgrade schemas; absence of a new FK remains explicit null."""
    archives = _rows(db, PmsProjectArchive, ['id', 'project_code', 'project_name', 'product_line_id',
        'business_product_line_id', 'manager_id', 'created_by', 'updated_at', 'erp_sync_status'], lock=lock)
    for row in archives:
        row['legacy_product_line_id'] = row.pop('product_line_id')
    lines = _rows(db, SysProductLine, ['id', 'source_key', 'organization_id', 'organization_code',
        'organization_name', 'display_name', 'is_enabled', 'updated_at'], lock=lock)
    roles = _rows(db, SysRole, ['id', 'role_code', 'role_name', 'status', 'data_scope',
                              'product_category_ids', 'updated_at'], lock=lock)
    grants = _rows(db, SysRoleProductLine, ['id', 'role_id', 'product_line_id'], lock=lock)
    projects = _rows(db, PmsProject, ['id', 'project_code', 'archive_id'], lock=lock)
    revisions = _rows(db, PmsDatabaseRevision, ['id', 'revision'], lock=lock)
    revision = next((row['revision'] for row in revisions if row['id'] == 1), None)
    state = dict(source_revision=revision, archives=archives, lines=lines, roles=roles, grants=grants, projects=projects)
    fingerprint = _digest(state)
    counts = Counter(row['project_code'].strip().casefold() for row in archives)
    archive_ids = {row['id'] for row in archives}
    issues = {
        '未归属档案': [row for row in archives if row['business_product_line_id'] is None],
        '项目编码冲突': [row for row in archives if counts[row['project_code'].strip().casefold()] > 1],
        '进度缺少有效档案引用': [row for row in projects if row['archive_id'] not in archive_ids],
        '角色需明确产品线授权': roles,
    }
    return {**state, 'source_fingerprint': fingerprint, 'issues': issues}


def inspect_plan(db, raw_plan, *, state=None):
    plan = AssignmentPlan.model_validate(raw_plan)
    state = state if state is not None else snapshot(db)
    errors = []
    if plan.source_revision != state['source_revision'] or state['source_revision'] != CURRENT_DATABASE_REVISION:
        errors.append('数据库版本不符；请先完成独立结构升级后重新生成清单')
    if plan.source_fingerprint != state['source_fingerprint']:
        errors.append('源快照已变化；请重新核对并确认清单')
    lines = {row['id']: row for row in state['lines']}
    archives = {row['id']: row for row in state['archives']}
    roles = {row['id']: row for row in state['roles']}
    keys = {}
    for name, values in [('产品线键', [row.key for row in plan.lines]),
                         ('组织绑定', [row.organization_id for row in plan.lines]),
                         ('产品线编号', [row.product_line_id for row in plan.lines]),
                         ('档案编号', [row.archive_id for row in plan.archives]),
                         ('项目编码', [row.project_code.strip().casefold() for row in plan.archives]),
                         ('角色编号', [row.role_id for row in plan.roles])]:
        if len(values) != len(set(values)):
            errors.append(f'{name}重复')
    for item in plan.lines:
        line = lines.get(item.product_line_id)
        if (line is None or line['source_key'] != 'kingdee' or line['organization_id'] != item.organization_id
                or item.key != f'kingdee:{item.organization_id}' or not line['is_enabled']):
            errors.append(f'产品线绑定不存在、禁用或与组织不符：{item.key}')
        else:
            keys[item.key] = item.product_line_id
    for item in plan.archives:
        archive = archives.get(item.archive_id)
        if (archive is None or archive['project_code'] != item.project_code
                or archive['legacy_product_line_id'] != item.legacy_product_line_id):
            errors.append(f'档案源值不匹配：{item.archive_id}')
        elif archive['business_product_line_id'] is not None:
            errors.append(f'档案已有组织归属，不能使用期初工具覆盖：{item.archive_id}')
        if item.target_product_line_key not in keys:
            errors.append(f'档案目标产品线未列明：{item.archive_id}')
    for item in plan.roles:
        if item.role_id not in roles:
            errors.append(f'角色不存在：{item.role_id}')
        if len(item.product_line_keys) != len(set(item.product_line_keys)):
            errors.append(f'角色产品线重复：{item.role_id}')
        if any(key not in keys for key in item.product_line_keys):
            errors.append(f'角色目标产品线未列明：{item.role_id}')
    if state['issues']['项目编码冲突']:
        errors.append('存在项目编码冲突，须先处理')
    return {'ready': not errors, 'errors': errors, 'archive_count': len(plan.archives),
            'role_count': len(plan.roles), 'batch_id': _digest(plan.model_dump())}


def prepare_archive_plan(db, raw_mappings):
    """Read-only expansion of approved legacy IDs; never infer or assign role grants."""
    mappings = [LegacyOrganizationMapping.model_validate(item) for item in raw_mappings]
    if not mappings or len({item.legacy_product_line_id for item in mappings}) != len(mappings):
        raise HTTPException(422, '历史产品线映射不能为空或重复')
    state = snapshot(db)
    targets, lines = {}, {}
    for item in mappings:
        matches = [line for line in state['lines'] if line['source_key'] == 'kingdee'
                   and line['organization_id'] == item.organization_id and line['is_enabled']]
        if len(matches) != 1:
            raise HTTPException(422, f'请先在页面创建并启用组织对应产品线：{item.organization_id}')
        key = f'kingdee:{item.organization_id}'
        targets[item.legacy_product_line_id] = key
        lines[key] = dict(key=key, product_line_id=matches[0]['id'], organization_id=item.organization_id)
    archives, unmatched = [], []
    for archive in state['archives']:
        if archive['business_product_line_id'] is not None:
            continue
        key = targets.get(archive['legacy_product_line_id'])
        if key is None:
            unmatched.append(archive)
            continue
        archives.append(dict(archive_id=archive['id'], project_code=archive['project_code'],
                             legacy_product_line_id=archive['legacy_product_line_id'],
                             target_product_line_key=key))
    plan = dict(source_revision=state['source_revision'] or '', source_fingerprint=state['source_fingerprint'],
                lines=list(lines.values()), archives=archives, roles=[])
    result = inspect_plan(db, plan, state=state)
    if not archives:
        result['ready'] = False
        result['errors'].append('没有可迁移的未归属档案')
    return {**result, 'plan': plan, 'unmatched_archives': unmatched}


def apply_plan(db, raw_plan, *, operator_id):
    """Caller owns this dedicated transaction; no unrelated pending writes allowed."""
    plan = AssignmentPlan.model_validate(raw_plan)
    batch_id = _digest(plan.model_dump())
    if db.new or db.dirty or db.deleted:
        raise HTTPException(409, '迁移必须使用独立、无待保存修改的会话')
    db.rollback()
    try:
        # Lock the inspected rows/ranges through commit, including empty grant ranges.
        if db.bind.dialect.name == 'sqlite':
            db.execute(text('BEGIN IMMEDIATE'))
        state = snapshot(db, lock=True)
        context = build_authorization_context(db, operator_id)
        if 'system:product-line:migrate' not in context.get('permissions', []):
            raise HTTPException(403, '无产品线迁移权限')
        previous = db.query(SysOperationLog).filter_by(entity_type='product_line_assignment_batch',
            entity_id=batch_id, status='success').first()
        if previous is not None:
            db.rollback()
            return {'status': 'already_applied', 'batch_id': batch_id}
        result = inspect_plan(db, plan.model_dump(), state=state)
        if not result['ready']:
            raise HTTPException(409, result)
        keys = {item.key: item.product_line_id for item in plan.lines}
        for item in plan.archives:
            db.query(PmsProjectArchive).filter_by(id=item.archive_id).update(
                {'business_product_line_id': keys[item.target_product_line_key]}, synchronize_session=False)
        for item in plan.roles:
            db.query(SysRoleProductLine).filter_by(role_id=item.role_id).delete(synchronize_session=False)
            db.add_all([SysRoleProductLine(role_id=item.role_id, product_line_id=keys[key])
                        for key in item.product_line_keys])
        db.flush()
        after = snapshot(db)
        record_operation_log(db, module='系统管理', action='import',
            entity_type='product_line_assignment_batch', entity_id=batch_id,
            entity_name='产品线组织期初归属', operator_id=operator_id,
            summary=f'产品线期初迁移：{len(plan.archives)} 个档案，{len(plan.roles)} 个角色',
            before_data={'archives': state['archives'], 'grants': state['grants']},
            after_data={'archives': after['archives'], 'grants': after['grants']})
        db.commit()
        return {'status': 'applied', **result}
    except Exception:
        db.rollback()
        raise
