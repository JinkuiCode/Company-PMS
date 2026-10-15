"""Explicit, additive governance upgrade. Application startup never calls it."""
from sqlalchemy import String, inspect, select, text

from app.models.database_revision import PmsDatabaseRevision
from app.models.operation_log import SysOperationLog
from app.models.rbac import SysMenu
from app.models.release import PmsRelease, PmsReleaseNotice, PmsReleaseMail

PREVIOUS = '2026-10-14-archive-governance-02'
REVISION = '2026-10-15-governance-01'
LOG_COLUMNS = {'root_entity_type': 64, 'root_entity_id': 64, 'diff_items_data': None}
RELEASE_TABLES = (PmsRelease.__table__, PmsReleaseNotice.__table__, PmsReleaseMail.__table__)


def install_governance_permissions(connection):
    """Install once; deliberately grant no role, including the admin template."""
    menus = SysMenu.__table__
    parents = connection.execute(select(menus.c.id).where(
        menus.c.menu_type == 'C', menus.c.path == '/project/archive',
        menus.c.permission_code == 'project:archive:list',
    )).scalars().all()
    if len(parents) != 1:
        raise RuntimeError('项目档案菜单结构不匹配，升级不会自动修正')
    rows = connection.execute(select(menus.c.parent_id, menus.c.menu_type, menus.c.path).where(
        menus.c.permission_code == 'project:archive:maintain',
    )).all()
    if rows:
        if len(rows) != 1 or tuple(rows[0]) != (parents[0], 'B', None):
            raise RuntimeError('档案维护权限节点冲突')
    else:
        connection.execute(menus.insert().values(parent_id=parents[0], menu_name='临时维护',
            menu_type='B', permission_code='project:archive:maintain', sort=10))
    audit_parents = connection.execute(select(menus.c.id).where(menus.c.menu_type == 'C',
        menus.c.path == '/system/operation-log', menus.c.permission_code == 'system:operation-log:list')).scalars().all()
    if len(audit_parents) != 1: raise RuntimeError('操作日志菜单结构不匹配')
    for code, label in [('publish', '发布版本'), ('manage', '管理版本投递'), ('retry', '重试版本邮件')]:
        permission = 'system:release:' + code
        nodes = connection.execute(select(menus.c.parent_id, menus.c.menu_type, menus.c.path).where(menus.c.permission_code == permission)).all()
        if nodes and (len(nodes) != 1 or tuple(nodes[0]) != (audit_parents[0], 'B', None)):
            raise RuntimeError('版本管理权限节点冲突')
        if not nodes: connection.execute(menus.insert().values(parent_id=audit_parents[0],
            menu_name=label, menu_type='B', permission_code=permission, sort=11))


def _unique_key_columns(connection, inspector, table):
    """Read enforced unique keys; MSSQL does not implement UQ reflection."""
    if connection.dialect.name != 'mssql':
        keys = {tuple(item['column_names']) for item in inspector.get_unique_constraints(table.name)}
        keys.update(tuple(item['column_names']) for item in inspector.get_indexes(table.name) if item['unique'])
        return keys
    rows = connection.execute(text('''SELECT i.index_id, c.name AS column_name, ic.key_ordinal
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id=t.schema_id
        JOIN sys.indexes i ON i.object_id=t.object_id
        JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
        JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
        WHERE s.name=:schema_name AND t.name=:table_name
          AND i.is_unique=1 AND i.is_primary_key=0 AND i.is_disabled=0
          AND i.is_hypothetical=0 AND i.has_filter=0
          AND ic.key_ordinal>0 AND ic.is_included_column=0
        ORDER BY i.index_id, ic.key_ordinal'''), {
            'schema_name': table.schema or inspector.default_schema_name or 'dbo',
            'table_name': table.name,
        }).mappings()
    keys = {}
    for row in rows:
        keys.setdefault(row['index_id'], []).append(row['column_name'])
    return {tuple(columns) for columns in keys.values()}


def verify_governance_structure(connection):
    inspector = inspect(connection)
    if not inspector.has_table('sys_operation_log'):
        raise RuntimeError('治理日志表缺失，请执行独立数据库升级')
    columns = {row['name']: row for row in inspector.get_columns('sys_operation_log')}
    for name, length in LOG_COLUMNS.items():
        column = columns.get(name)
        if column is None or not column['nullable'] or not isinstance(column['type'], String):
            raise RuntimeError(f'治理日志字段结构不一致：{name}')
        actual_length = column['type'].length
        if (length is None and actual_length is not None) or (length is not None and actual_length is not None and actual_length < length):
            raise RuntimeError(f'治理日志字段长度不一致：{name}')
    index = next((row for row in inspector.get_indexes('sys_operation_log') if row['name'] == 'idx_operation_log_root'), None)
    if not index or index['unique'] or index['column_names'] != ['root_entity_type', 'root_entity_id', 'created_at']:
        raise RuntimeError('治理日志关联索引不一致')
    for table in RELEASE_TABLES:
        if not inspector.has_table(table.name) or {row['name'] for row in inspector.get_columns(table.name)} != set(table.columns.keys()):
            raise RuntimeError(f'版本通知表结构不一致：{table.name}')
        expected = {tuple(constraint.columns.keys()) for constraint in table.constraints if constraint.__class__.__name__ == 'UniqueConstraint'}
        actual = _unique_key_columns(connection, inspector, table)
        if not expected.issubset(actual): raise RuntimeError(f'版本通知唯一约束不一致：{table.name}')
    column = next((row for row in inspector.get_columns('pms_feedback_report') if row['name'] == 'runtime_version'), None)
    if not column or not column['nullable'] or not isinstance(column['type'], String) or (column['type'].length is not None and column['type'].length < 32):
        raise RuntimeError('问题提报运行版本字段不一致')


def _install_release_structure(connection, *, allow_existing=False):
    inspector = inspect(connection)
    for table in RELEASE_TABLES:
        if inspector.has_table(table.name):
            if not allow_existing: raise RuntimeError('版本通知表已存在但版本未升级')
        else: table.create(connection)
    columns = {row['name'] for row in inspect(connection).get_columns('pms_feedback_report')}
    if 'runtime_version' in columns:
        if not allow_existing: raise RuntimeError('提报版本字段已存在但数据库版本未升级')
    else: connection.exec_driver_sql('ALTER TABLE pms_feedback_report ADD runtime_version NVARCHAR(32) NULL')


def _install_structure(connection):
    columns = {row['name'] for row in inspect(connection).get_columns('sys_operation_log')}
    # A partially installed target is not silently accepted or repaired.
    if any(name in columns for name in LOG_COLUMNS):
        raise RuntimeError('治理日志字段已存在但版本未升级，请核对升级状态')
    for name, length in LOG_COLUMNS.items():
        sqltype = f'NVARCHAR({length})' if length else ('NVARCHAR(MAX)' if connection.dialect.name == 'mssql' else 'TEXT')
        connection.exec_driver_sql(f'ALTER TABLE sys_operation_log ADD {name} {sqltype} NULL')
    index = next(item for item in SysOperationLog.__table__.indexes if item.name == 'idx_operation_log_root')
    index.create(connection)


def upgrade_governance(engine):
    with engine.begin() as connection:
        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql('BEGIN')
        revisions = PmsDatabaseRevision.__table__
        revision = connection.execute(select(revisions.c.revision).where(revisions.c.id == 1).with_hint(
            revisions, 'WITH (UPDLOCK, HOLDLOCK)', dialect_name='mssql',
        )).scalar_one_or_none()
        if revision not in (PREVIOUS, REVISION):
            raise RuntimeError(f'治理限定升级需要数据库版本 {PREVIOUS}')
        if revision == REVISION:
            verify_governance_structure(connection)
            return
        _install_structure(connection)
        _install_release_structure(connection)
        install_governance_permissions(connection)
        verify_governance_structure(connection)
        connection.execute(revisions.update().where(revisions.c.id == 1).values(revision=REVISION))


def finalize_governance_setup(engine):
    """Full explicit installer only, after historical setup and template grants."""
    with engine.begin() as connection:
        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql('BEGIN')
        columns = {row['name'] for row in inspect(connection).get_columns('sys_operation_log')}
        if not any(name in columns for name in LOG_COLUMNS):
            _install_structure(connection)
        _install_release_structure(connection, allow_existing=True)
        verify_governance_structure(connection)
        install_governance_permissions(connection)
