"""Explicit additive approval-notice upgrade; never run by production startup."""
from sqlalchemy import inspect, select, String, Integer, DateTime
from app.models.business_notice import BusinessNotice, BusinessNoticeMail
from app.models.database_revision import PmsDatabaseRevision
from app.models.rbac import SysMenu
from app.services.archive_policy_revision_migration import verify_archive_policy, revision_query
from app.services.form_draft_management_migration import _parent
from app.services.governance_migration import _unique_key_columns

PREVIOUS = '2026-10-21-archive-policy-01'
REVISION = '2026-10-27-archive-notice-01'
PERMISSIONS = ('project:archive:notification:manage','project:archive:notification:retry')
TABLES = (BusinessNotice.__table__,BusinessNoticeMail.__table__)


def notice_permissions(connection, *, create=False):
    table=SysMenu.__table__;parent=_parent(connection)
    for code,label in zip(PERMISSIONS,('管理审批投递','重试审批邮件')):
        rows=connection.execute(select(table.c.parent_id,table.c.menu_type,table.c.path).where(table.c.permission_code==code)).all()
        if rows and (len(rows)!=1 or tuple(rows[0])!=(parent,'B',None)):
            raise RuntimeError('审批通知权限节点冲突')
        if not rows:
            if not create:raise RuntimeError('审批通知权限节点缺失')
            connection.execute(table.insert().values(parent_id=parent,menu_name=label,menu_type='B',permission_code=code,sort=13))


def verify_business_notice_structure(connection):
    inspector=inspect(connection)
    for table in TABLES:
        if not inspector.has_table(table.name):raise RuntimeError('审批通知表缺失，请执行限定升级')
        columns={c['name']:c for c in inspector.get_columns(table.name)}
        if set(columns)!=set(table.columns.keys()):raise RuntimeError('审批通知表字段不一致')
        for expected in table.columns:
            actual=columns[expected.name]
            family=String if isinstance(expected.type,String) else Integer if isinstance(expected.type,Integer) else DateTime
            if not isinstance(actual['type'],family) or bool(actual['nullable'])!=expected.nullable:
                raise RuntimeError('审批通知字段类型或空值约束不一致：'+expected.name)
            if family is String and actual['type'].length!=expected.type.length:
                raise RuntimeError('审批通知字段长度不一致：'+expected.name)
        if inspector.get_pk_constraint(table.name)['constrained_columns']!=['id']:
            raise RuntimeError('审批通知主键不一致')
        unique=('change_id','event','request_version','user_id') if table.name==BusinessNotice.__tablename__ else ('notice_id',)
        if unique not in _unique_key_columns(connection,inspector,table):raise RuntimeError('审批通知唯一约束缺失')
        indexes={i['name']:i for i in inspector.get_indexes(table.name)}
        for expected in table.indexes:
            actual=indexes.get(expected.name)
            if not actual or actual['unique'] or actual['column_names']!=[c.name for c in expected.columns]:
                raise RuntimeError('审批通知索引不一致')
        foreign=inspector.get_foreign_keys(table.name)
        for expected in table.foreign_keys:
            if not any(i['constrained_columns']==[expected.parent.name] and i['referred_table']==expected.column.table.name
                and i['referred_columns']==[expected.column.name] for i in foreign):
                raise RuntimeError('审批通知归属外键缺失')
    notice_permissions(connection)


def upgrade_business_notices(engine):
    with engine.begin() as connection:
        if connection.dialect.name=='sqlite':connection.exec_driver_sql('BEGIN IMMEDIATE')
        revision=connection.execute(revision_query()).scalar_one_or_none()
        if revision not in (PREVIOUS,REVISION):raise RuntimeError('审批通知限定升级需要archive-policy-01版本')
        verify_archive_policy(connection,strict_values=False)
        if revision==REVISION:
            verify_business_notice_structure(connection);return
        if any(inspect(connection).has_table(table.name) for table in TABLES):
            raise RuntimeError('旧版本已有通知表或部分结构，停止升级并核查')
        notice_permissions(connection,create=True)
        for table in TABLES:table.create(connection)
        verify_business_notice_structure(connection)
        connection.execute(PmsDatabaseRevision.__table__.update().where(PmsDatabaseRevision.id==1).values(revision=REVISION))
