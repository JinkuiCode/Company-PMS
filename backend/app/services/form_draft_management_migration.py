"""Explicit revision 02, including the frozen 01 step; no runtime upgrades/grants."""
from sqlalchemy import select
from app.models.form_draft import PmsFormDraft
from app.models.database_revision import PmsDatabaseRevision
from app.models.rbac import SysMenu
from app.services.form_draft_migration import (PREVIOUS as GOVERNANCE,REVISION as PREVIOUS,
    upgrade_form_drafts_connection,verify_form_draft_structure)
from app.services.governance_migration import verify_governance_structure

REVISION='2026-10-16-form-draft-02'
PERMISSION='project:archive:draft:manage'

def _parent(connection):
    table=SysMenu.__table__
    rows=connection.execute(select(table.c.id).where(table.c.menu_type=='C',table.c.path=='/project/archive',
        table.c.permission_code=='project:archive:list')).scalars().all()
    if len(rows)!=1:raise RuntimeError('项目档案菜单结构不匹配')
    return rows[0]

def install_draft_management_permission(connection):
    table=SysMenu.__table__;parent=_parent(connection)
    rows=connection.execute(select(table.c.parent_id,table.c.menu_type,table.c.path).where(table.c.permission_code==PERMISSION)).all()
    if rows and (len(rows)!=1 or tuple(rows[0])!=(parent,'B',None)):
        raise RuntimeError('草稿管理权限节点冲突')
    if not rows:connection.execute(table.insert().values(parent_id=parent,menu_name='草稿管理',menu_type='B',permission_code=PERMISSION,sort=12))

def verify_draft_management_structure(connection):
    verify_governance_structure(connection)
    verify_form_draft_structure(connection,PmsFormDraft.__table__)
    table=SysMenu.__table__;parent=_parent(connection)
    rows=connection.execute(select(table.c.parent_id,table.c.menu_type,table.c.path).where(table.c.permission_code==PERMISSION)).all()
    if len(rows)!=1 or tuple(rows[0])!=(parent,'B',None):raise RuntimeError('草稿管理权限节点缺失或冲突')

def upgrade_draft_management(engine):
    with engine.begin() as connection:
        if connection.dialect.name=='sqlite':connection.exec_driver_sql('BEGIN')
        revisions=PmsDatabaseRevision.__table__
        revision=connection.execute(select(revisions.c.revision).where(revisions.c.id==1).with_hint(
            revisions,'WITH (UPDLOCK, HOLDLOCK)',dialect_name='mssql')).scalar_one_or_none()
        if revision==REVISION:
            verify_draft_management_structure(connection);return
        if revision not in (GOVERNANCE,PREVIOUS):raise RuntimeError('草稿管理限定升级需要governance-01或form-draft-01')
        upgrade_form_drafts_connection(connection)
        install_draft_management_permission(connection)
        verify_draft_management_structure(connection)
        connection.execute(revisions.update().where(revisions.c.id==1).values(revision=REVISION))
