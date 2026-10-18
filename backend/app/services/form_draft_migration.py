"""Explicit additive migration. Never invoked by application startup."""
import re
from sqlalchemy import inspect, select, text, String, Integer, DateTime, MetaData, Table, Column, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.mssql import NVARCHAR
from app.models.database_revision import PmsDatabaseRevision
from app.models.user import SysUser  # noqa: F401 - resolve owner_id before standalone DDL/type checks
from app.models.form_draft import PmsFormDraft
from app.services.governance_migration import verify_governance_structure

PREVIOUS = '2026-10-15-governance-01'
REVISION = '2026-10-16-form-draft-01'

def frozen_v1_table():
    """Historical DDL must not follow additions to the live ORM model."""
    metadata=MetaData()
    Table('sys_user',metadata,Column('id',Integer,primary_key=True))
    return Table('pms_form_draft',metadata,
        Column('id',NVARCHAR(36),primary_key=True,nullable=False),
        Column('owner_id',Integer,ForeignKey('sys_user.id'),nullable=False),
        Column('resource',NVARCHAR(32),nullable=False),Column('payload_json',NVARCHAR(None),nullable=False),
        Column('product_line_id',Integer,nullable=True),Column('version',Integer,nullable=False),
        Column('status',NVARCHAR(16),nullable=False),Column('archive_id',Integer,nullable=True),
        Column('created_at',DateTime,nullable=False),Column('updated_at',DateTime,nullable=False),
        Index('idx_form_draft_owner','owner_id','resource','status','updated_at'),
        CheckConstraint('version > 0',name='ck_form_draft_version'),
        CheckConstraint("status IN ('active','used','deleted')",name='ck_form_draft_status'))

def _draft_check_constraints(connection, inspector, table):
    if connection.dialect.name != 'mssql':
        return inspector.get_check_constraints(table.name)
    rows = connection.execute(text("""SELECT cc.name, cc.definition, cc.is_disabled, cc.is_not_trusted
        FROM sys.check_constraints cc
        JOIN sys.tables t ON t.object_id=cc.parent_object_id
        JOIN sys.schemas s ON s.schema_id=t.schema_id
        WHERE s.name=:schema_name AND t.name=:table_name"""), {
            'schema_name': table.schema or inspector.default_schema_name or 'dbo',
            'table_name': table.name,
        }).mappings().all()
    return [{'name': row['name'], 'sqltext': row['definition']} for row in rows
            if row['is_disabled'] == 0 and row['is_not_trusted'] == 0]

def verify_form_draft_structure(connection, table=None):
    inspector = inspect(connection)
    table = frozen_v1_table() if table is None else table
    if not inspector.has_table(table.name):
        raise RuntimeError('草稿表缺失，请执行独立数据库升级')
    columns = {row['name']: row for row in inspector.get_columns(table.name)}
    if set(columns) != set(table.columns.keys()):
        raise RuntimeError('草稿表字段结构不一致')
    for expected in table.columns:
        actual = columns[expected.name]
        family = String if isinstance(expected.type, String) else Integer if isinstance(expected.type, Integer) else DateTime
        if not isinstance(actual['type'], family) or bool(actual['nullable']) != expected.nullable:
            raise RuntimeError('草稿表字段类型/空值约束不一致：' + expected.name)
        if family is String and actual['type'].length != expected.type.length:
            raise RuntimeError('草稿表字段长度不一致：' + expected.name)
    if inspector.get_pk_constraint(table.name)['constrained_columns'] != ['id']:
        raise RuntimeError('草稿表主键不一致')
    index = next((i for i in inspector.get_indexes(table.name) if i['name'] == 'idx_form_draft_owner'), None)
    if not index or index['unique'] or index['column_names'] != ['owner_id','resource','status','updated_at']:
        raise RuntimeError('草稿表索引不一致')
    def normalized(expression):
        expression = re.sub(r"\bN(?=')", '', expression, flags=re.I)
        return re.sub(r'[\s\[\]()]', '', expression).lower()
    checks = {i['name']:normalized(i['sqltext']) for i in _draft_check_constraints(connection, inspector, table)}
    status = checks.get('ck_form_draft_status', '')
    # SQL Server can rewrite IN to an OR expression in catalog metadata.
    expected_status = {"status='active'", "status='used'", "status='deleted'"}
    valid_status = status == "statusin'active','used','deleted'" or set(status.split('or')) == expected_status
    if checks.get('ck_form_draft_version') != 'version>0' or not valid_status:
        raise RuntimeError('草稿表检查约束不一致')
    foreign_keys = inspector.get_foreign_keys(table.name)
    if not any(i['constrained_columns'] == ['owner_id'] and i['referred_table'] == 'sys_user'
               and i['referred_columns'] == ['id'] for i in foreign_keys):
        raise RuntimeError('草稿归属外键缺失')

def upgrade_form_drafts(engine):
    with engine.begin() as connection:
        if connection.dialect.name == 'sqlite': connection.exec_driver_sql('BEGIN')
        upgrade_form_drafts_connection(connection)

def upgrade_form_drafts_connection(connection):
    revisions = PmsDatabaseRevision.__table__
    revision = connection.execute(select(revisions.c.revision).where(revisions.c.id == 1).with_hint(
        revisions, 'WITH (UPDLOCK, HOLDLOCK)', dialect_name='mssql')).scalar_one_or_none()
    if revision not in (PREVIOUS, REVISION):
        raise RuntimeError(f'草稿限定升级需要 {PREVIOUS}')
    verify_governance_structure(connection)
    if revision == REVISION:
        verify_form_draft_structure(connection)
        return
    if inspect(connection).has_table('pms_form_draft'):
        raise RuntimeError('草稿表已存在但版本未升级，请核对现场')
    frozen_v1_table().create(connection)
    verify_form_draft_structure(connection)
    connection.execute(revisions.update().where(revisions.c.id == 1).values(revision=REVISION))
