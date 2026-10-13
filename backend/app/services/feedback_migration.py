"""Bounded upgrade with no historical initialization and no startup regrant."""
from sqlalchemy import inspect, select, text
from uuid import uuid4
from sqlalchemy.orm import Session
from app.models.feedback import FeedbackReport, FeedbackFollowup, FeedbackAttachment, FeedbackNotification
from app.models.database_revision import PmsDatabaseRevision
from app.models.rbac import SysMenu, SysRole, SysRoleMenu
from app.models.dict import SysDict, SysDictItem
from app.services.feedback_enums import FEEDBACK_ENUMS

PREVIOUS = '2026-10-12-parameter-secret-01'
REVISION = '2026-10-12-feedback-02'
INITIAL_REVISION = '2026-10-12-feedback-01'
TABLES = [model.__table__ for model in (FeedbackReport, FeedbackFollowup, FeedbackAttachment, FeedbackNotification)]
PERMISSIONS = [('view', '查看'), ('add', '新增'), ('supplement', '补充信息'), ('handle', '处理全部提报'), ('export', '导出'), ('notification:retry', '重试邮件')]


def install_feedback(db):
    for code, meta in FEEDBACK_ENUMS.items():
        if db.query(SysDict).filter_by(dict_code=code).first():
            continue
        definition = SysDict(dict_code=code, dict_name=meta['name'], page_name='枚举管理',
            table_name=meta['table_name'], field_name=meta['field_name'], description=meta['description'],
            status=1, sort=meta['sort'], next_value=len(meta['items']) + 1)
        db.add(definition)
        db.flush()
        for index, (value, label) in enumerate(meta['items'], 1):
            db.add(SysDictItem(dict_id=definition.id, item_value=value, item_label=label, sort=index, status=1))
    root = db.query(SysMenu).filter_by(permission_code='feedback:view').first()
    if root is None:
        root = SysMenu(parent_id=0, menu_name='问题提报', menu_type='C', path='/feedback', icon='ChatLineSquare', permission_code='feedback:view', sort=4)
        db.add(root)
        db.flush()
        nodes = [root]
        for index, (code, label) in enumerate(PERMISSIONS[1:], 1):
            node = SysMenu(parent_id=root.id, menu_name=label, menu_type='B', permission_code='feedback:' + code, sort=index)
            db.add(node)
            nodes.append(node)
        db.flush()
        for role in db.query(SysRole).filter(SysRole.status == 1, SysRole.role_code.in_(['admin', 'business_admin', 'operator'])):
            for node in nodes:
                if role.role_code != 'admin' and node.permission_code in ('feedback:handle', 'feedback:notification:retry'):
                    continue
                db.add(SysRoleMenu(role_id=role.id, menu_id=node.id))
    db.flush()


def upgrade_feedback(engine):
    with engine.begin() as connection:
        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql('BEGIN')
        table = PmsDatabaseRevision.__table__
        revision = connection.execute(select(table.c.revision).where(table.c.id == 1).with_hint(table, 'WITH (UPDLOCK, HOLDLOCK)', dialect_name='mssql')).scalar_one_or_none()
        if revision not in (PREVIOUS, INITIAL_REVISION, REVISION):
            raise RuntimeError('问题提报限定升级需要 parameter-secret-01 数据库版本')
        if revision in (INITIAL_REVISION, REVISION):
            for new_table in TABLES:
                columns = {column['name'] for column in inspect(connection).get_columns(new_table.name)} if inspect(connection).has_table(new_table.name) else set()
                expected = {column.name for column in new_table.columns}
                if revision == INITIAL_REVISION and new_table.name == 'pms_feedback_report':
                    expected.discard('submission_id')
                if not expected.issubset(columns):
                    raise RuntimeError('问题提报数据库版本与表结构不一致')
            if revision == INITIAL_REVISION:
                if 'submission_id' in {column['name'] for column in inspect(connection).get_columns('pms_feedback_report')}:
                    raise RuntimeError('提交去重字段已存在但版本未升级，停止以避免覆盖')
                connection.exec_driver_sql("ALTER TABLE pms_feedback_report ADD submission_id NVARCHAR(36) NOT NULL DEFAULT ''")
                for report_id in connection.execute(text('SELECT id FROM pms_feedback_report')).scalars().all():
                    connection.execute(text('UPDATE pms_feedback_report SET submission_id=:value WHERE id=:id'), {'value':str(uuid4()), 'id':report_id})
                next(index for index in FeedbackReport.__table__.indexes if index.name == 'uq_feedback_submission').create(connection)
                connection.execute(table.update().where(table.c.id == 1).values(revision=REVISION))
            indexes = inspect(connection).get_indexes('pms_feedback_report')
            if not any(index['name'] == 'uq_feedback_submission' and index['unique'] and index['column_names'] == ['author_id', 'submission_id'] for index in indexes):
                raise RuntimeError('问题提报提交去重索引缺失或不一致')
            return
        for new_table in TABLES:
            if inspect(connection).has_table(new_table.name):
                raise RuntimeError('问题提报表已存在但版本未升级，停止以避免覆盖')
            new_table.create(connection)
        db = Session(bind=connection)
        try:
            install_feedback(db)
            db.flush()
            connection.execute(table.update().where(table.c.id == 1).values(revision=REVISION))
        finally:
            db.close()
