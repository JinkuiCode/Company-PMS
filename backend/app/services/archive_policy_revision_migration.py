"""Explicit data-only A1 policy revision. Never called by application startup.

Returned before/after values are rollback preparation material, not an automatic
rollback: new records permitted by A1 may be incompatible with older programs.
"""
from sqlalchemy import select
from app.models.database_revision import PmsDatabaseRevision
from app.models.dict import SysDict, SysDictItem
from app.models.field_policy import SysBusinessFieldPolicy
from app.services.form_draft_management_migration import verify_draft_management_structure
from app.services.archive_governance_migration import _verify as verify_archive_governance

PREVIOUS = '2026-10-16-form-draft-02'
REVISION = '2026-10-21-archive-policy-01'
# Frozen migration input, independent of future runtime registrations.
REQUIRED_VALUES = {'archive_category': True, 'manager_id': True,
    'machine_model': False, 'quantity': False, 'quantity_unit': False,
    'equipment_series': False, 'serial_no': False,
    'contract_signed_date': False, 'contract_ship_date': False}


def revision_query():
    table = PmsDatabaseRevision.__table__
    return select(table.c.revision).where(table.c.id == 1).with_hint(
        table, 'WITH (UPDLOCK, HOLDLOCK)', dialect_name='mssql')


def _unit(connection, *, final=False):
    definitions = connection.execute(select(SysDict.__table__).where(
        SysDict.dict_code == 'archive_quantity_unit').with_hint(
        SysDict.__table__, 'WITH (UPDLOCK, HOLDLOCK)', dialect_name='mssql')).mappings().all()
    if len(definitions) != 1 or definitions[0]['status'] != 1:
        raise RuntimeError('单位枚举身份或状态异常，升级停止')
    definition = definitions[0]
    rows = connection.execute(select(SysDictItem.__table__).where(
        SysDictItem.dict_id == definition['id']).with_hint(
        SysDictItem.__table__, 'WITH (UPDLOCK, HOLDLOCK)', dialect_name='mssql')).mappings().all()
    units = [r for r in rows if r['item_value'] == '7']
    if len(units) != 1 or units[0]['status'] != 1 or units[0]['item_label'] not in (('pcs',) if final else ('台', 'pcs')):
        raise RuntimeError('原台单位的稳定编号、名称或状态异常，升级停止')
    unit = dict(units[0])
    if any(r['id'] != unit['id'] and str(r['item_label']).strip().casefold() == 'pcs' for r in rows):
        raise RuntimeError('存在其他同名pcs单位，升级停止')
    return unit


def verify_archive_policy(connection, *, strict_values=True):
    verify_draft_management_structure(connection)
    verify_archive_governance(connection)
    if strict_values:
        _unit(connection, final=True)
    if strict_values:
        table = SysBusinessFieldPolicy.__table__
        rows = connection.execute(select(table.c.field_key, table.c.required).where(
            table.c.module_code == 'project_archive', table.c.field_key.in_(REQUIRED_VALUES))).all()
        if {r.field_key: bool(r.required) for r in rows} != REQUIRED_VALUES:
            raise RuntimeError('档案策略版本与持久必输规则不一致')


def _install(connection):
    # Validate all identities and previous structure before the first write.
    verify_draft_management_structure(connection)
    verify_archive_governance(connection)
    unit = _unit(connection)
    table = SysBusinessFieldPolicy.__table__
    before = [dict(r) for r in connection.execute(select(table).where(
        table.c.module_code == 'project_archive', table.c.field_key.in_(REQUIRED_VALUES))).mappings()]
    existing = {r['field_key']: r for r in before}
    for key, required in REQUIRED_VALUES.items():
        row = existing.get(key)
        if row is None:
            if key not in ('contract_signed_date', 'contract_ship_date'):
                raise RuntimeError('历史档案必输规则缺失，升级停止')
            connection.execute(table.insert().values(module_code='project_archive', field_key=key,
                visible=True, editable=True, required=required, list_available=True))
        elif bool(row['required']) != required:
            # Preserve IDs, cutoff, visibility/editability, user attribution and timestamps.
            connection.execute(table.update().where(table.c.id == row['id']).values(
                required=required, updated_at=row['updated_at']))
    if unit['item_label'] != 'pcs':
        items = SysDictItem.__table__
        connection.execute(items.update().where(items.c.id == unit['id']).values(
            item_label='pcs', updated_at=unit['updated_at']))
    verify_archive_policy(connection)
    after = [dict(r) for r in connection.execute(select(table).where(
        table.c.module_code == 'project_archive', table.c.field_key.in_(REQUIRED_VALUES))).mappings()]
    return {'previous': PREVIOUS, 'target': REVISION,
        'policies': {'before': before, 'after': after},
        'unit': {'before': unit, 'after': _unit(connection, final=True)}}


def upgrade_archive_policy(engine):
    with engine.begin() as connection:
        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        revision = connection.execute(revision_query()).scalar_one_or_none()
        if revision == REVISION:
            verify_archive_policy(connection)
            return {'previous': REVISION, 'target': REVISION, 'unchanged': True}
        if revision != PREVIOUS:
            raise RuntimeError('档案策略限定升级需要form-draft-02版本')
        result = _install(connection)
        table = PmsDatabaseRevision.__table__
        connection.execute(table.update().where(table.c.id == 1).values(revision=REVISION))
        return result


def finalize_archive_policy_setup(engine):
    """Full explicit installer only. Does not mark a revision on its own."""
    with engine.begin() as connection:
        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        return _install(connection)
