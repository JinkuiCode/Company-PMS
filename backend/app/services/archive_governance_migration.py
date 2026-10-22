"""Independent bounded upgrade. Never run this from application startup."""
import re
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session
from app.models.archive_change import ArchiveChange
from app.models.database_revision import PmsDatabaseRevision
from app.models.field_policy import SysBusinessFieldPolicy
from app.models.dict import SysDict, SysDictItem
# Historical seven-field input is immutable; later runtime policies must not rewrite this migration.
ARCHIVE_GOVERNANCE_REQUIRED_FIELDS = ('archive_category', 'machine_model', 'quantity', 'quantity_unit', 'manager_id')
ARCHIVE_GOVERNANCE_CONDITIONAL_FIELDS = ('equipment_series', 'serial_no')

PREVIOUS='2026-10-12-feedback-02'
FIRST_REVISION='2026-10-14-archive-governance-01'
REVISION='2026-10-14-archive-governance-02'
STATE_ITEMS=[('1','草稿'),('2','待审批'),('3','已通过'),('4','已退回'),('5','已撤回')]


def install_archive_governance(db):
    cutoff=db.scalar(select(func.now()))
    for key in (*ARCHIVE_GOVERNANCE_REQUIRED_FIELDS,*ARCHIVE_GOVERNANCE_CONDITIONAL_FIELDS):
        row=db.query(SysBusinessFieldPolicy).filter_by(module_code='project_archive',field_key=key).first()
        if row is None:
            row=SysBusinessFieldPolicy(module_code='project_archive',field_key=key)
            db.add(row)
        row.visible=True;row.editable=True
        row.required=key in ARCHIVE_GOVERNANCE_REQUIRED_FIELDS
        row.list_available=True
        if row.required_effective_at is None:row.required_effective_at=cutoff
    definition=db.query(SysDict).filter_by(dict_code='archive_change_status').first()
    if definition is None:
        definition=SysDict(dict_code='archive_change_status',dict_name='档案变更审批状态',status=1,sort=18,
            table_name='pms_archive_change',field_name='status',page_name='项目档案变更',next_value=6)
        db.add(definition);db.flush()
        for index,(value,label) in enumerate(STATE_ITEMS,1):
            db.add(SysDictItem(dict_id=definition.id,item_value=value,item_label=label,sort=index,status=1))
    db.query(SysBusinessFieldPolicy).filter(SysBusinessFieldPolicy.module_code=='project_archive',SysBusinessFieldPolicy.field_key.in_(['plan_start_date','plan_end_date'])).delete(synchronize_session=False)
    db.flush()


def _drop_archive_plan_columns(connection):
    names={column['name'] for column in inspect(connection).get_columns('pms_project_archive')}
    for name in ('plan_start_date','plan_end_date'):
        if name not in names:continue
        if connection.dialect.name=='mssql':
            constraints=connection.execute(text("SELECT dc.name FROM sys.default_constraints dc JOIN sys.columns c ON c.object_id=dc.parent_object_id AND c.column_id=dc.parent_column_id WHERE dc.parent_object_id=OBJECT_ID('pms_project_archive') AND c.name=:name"),{'name':name}).scalars().all()
            for constraint in constraints:
                quoted=connection.dialect.identifier_preparer.quote(constraint)
                connection.exec_driver_sql(f'ALTER TABLE pms_project_archive DROP CONSTRAINT {quoted}')
        connection.exec_driver_sql(f'ALTER TABLE pms_project_archive DROP COLUMN {name}')


def _add_legacy_marker(connection):
    columns={column['name'] for column in inspect(connection).get_columns('pms_project_archive')}
    if 'governance_legacy' in columns:raise RuntimeError('存量标记已存在但版本未升级，停止避免覆盖')
    sql=('ALTER TABLE pms_project_archive ADD governance_legacy BIT NOT NULL '
         'CONSTRAINT DF_pms_archive_governance_legacy DEFAULT 0 WITH VALUES') if connection.dialect.name=='mssql' else (
         'ALTER TABLE pms_project_archive ADD COLUMN governance_legacy BOOLEAN NOT NULL DEFAULT 0')
    connection.exec_driver_sql(sql)
    # Only rows present in the locked, independent upgrade receive historical compatibility.
    connection.exec_driver_sql('UPDATE pms_project_archive SET governance_legacy=1')


def _verify(connection, *, require_marker=True):
    inspector=inspect(connection)
    if not inspector.has_table(ArchiveChange.__tablename__):raise RuntimeError('档案变更表缺失，版本不一致')
    columns={column['name'] for column in inspector.get_columns(ArchiveChange.__tablename__)}
    if columns!={column.name for column in ArchiveChange.__table__.columns}:raise RuntimeError('档案变更字段结构不一致')
    indexes={index['name']:index for index in inspector.get_indexes(ArchiveChange.__tablename__)}
    for name,fields in [('uq_archive_change_submission',['author_id','submission_id']),('uq_archive_change_active',['active_archive_id'])]:
        if name not in indexes or not indexes[name]['unique'] or indexes[name]['column_names']!=fields:raise RuntimeError('档案变更唯一索引不一致')
    predicate=indexes['uq_archive_change_active'].get('dialect_options',{}).get(f'{connection.dialect.name}_where')
    if not re.fullmatch(r'\(*\s*(?:active_archive_id|\[active_archive_id\]|"active_archive_id")\s+IS\s+NOT\s+NULL\s*\)*',str(predicate),re.IGNORECASE):
        raise RuntimeError('档案变更活动唯一索引条件不一致')
    if any(column['name'] in ('plan_start_date','plan_end_date') for column in inspector.get_columns('pms_project_archive')):raise RuntimeError('档案计划列尚未移除')
    if require_marker:
        marker=next((column for column in inspector.get_columns('pms_project_archive') if column['name']=='governance_legacy'),None)
        if not marker or marker['nullable'] or str(marker['default']).strip('() ')!='0':raise RuntimeError('档案存量标记结构不一致')
    policy=SysBusinessFieldPolicy.__table__
    rows=connection.execute(select(policy.c.field_key,policy.c.required_effective_at).where(policy.c.module_code=='project_archive',policy.c.field_key.in_([*ARCHIVE_GOVERNANCE_REQUIRED_FIELDS,*ARCHIVE_GOVERNANCE_CONDITIONAL_FIELDS]))).all()
    if len(rows)!=7 or any(not row.required_effective_at for row in rows):raise RuntimeError('档案必输规则生效时间缺失')
    states=connection.execute(select(SysDictItem.item_value,SysDictItem.item_label,SysDictItem.status).join(SysDict,SysDict.id==SysDictItem.dict_id).where(SysDict.dict_code=='archive_change_status')).all()
    if sorted(states)!=sorted((value,label,1) for value,label in STATE_ITEMS):raise RuntimeError('档案审批固定状态枚举不一致')


def upgrade_archive_governance(engine):
    with engine.begin() as connection:
        if connection.dialect.name=='sqlite':connection.exec_driver_sql('BEGIN')
        revisions=PmsDatabaseRevision.__table__
        revision=connection.execute(select(revisions.c.revision).where(revisions.c.id==1).with_hint(revisions,'WITH (UPDLOCK, HOLDLOCK)',dialect_name='mssql')).scalar_one_or_none()
        if revision not in (PREVIOUS,FIRST_REVISION,REVISION):raise RuntimeError('档案治理限定升级需要feedback-02或governance-01数据库版本')
        if revision==REVISION:_verify(connection);return
        if revision==FIRST_REVISION:_verify(connection,require_marker=False)
        else:
            if inspect(connection).has_table(ArchiveChange.__tablename__):raise RuntimeError('档案变更表已存在但版本未升级，停止避免覆盖')
            ArchiveChange.__table__.create(connection)
        db=Session(bind=connection)
        try:
            if revision==PREVIOUS:
                install_archive_governance(db)
                _drop_archive_plan_columns(connection)
            _add_legacy_marker(connection)
            _verify(connection)
            connection.execute(revisions.update().where(revisions.c.id==1).values(revision=REVISION))
        finally:db.close()


def finalize_archive_governance_setup(engine):
    """Full explicit installer only; bounded existing-db upgrade uses the function above."""
    with engine.begin() as connection:
        if connection.dialect.name=='sqlite':connection.exec_driver_sql('BEGIN')
        db=Session(bind=connection)
        try:
            install_archive_governance(db)
            _drop_archive_plan_columns(connection)
            if 'governance_legacy' not in {column['name'] for column in inspect(connection).get_columns('pms_project_archive')}:
                _add_legacy_marker(connection)
            _verify(connection)
        finally:db.close()
