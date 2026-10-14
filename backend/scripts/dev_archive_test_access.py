"""Approved local-only archive acceptance setup; credentials are never copied or printed."""
import json
import os
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

ROLE_CODE='dev_archive_approval_acceptance'


def configure_test_access(db):
    from app.models.user import SysUser
    from app.models.rbac import SysDept,SysRole,SysUserRole,SysRoleMenu,SysMenu
    from app.models.product_line import SysProductLine,SysRoleProductLine
    from app.schemas.rbac import RoleCreate
    from app.schemas.user import UserUpdate
    from app.services.authorization import build_authorization_context,enforce_permission
    from app.services.rbac import create_role,update_user,normalize_role_menu_ids

    owner=db.query(SysUser).filter_by(username='ael',status=1).one()
    head=db.query(SysUser).filter_by(username='A000645',status=1).one()
    department=db.query(SysDept).filter_by(dept_name='信息化',status=1).one()
    line=db.query(SysProductLine).filter_by(display_name='12吋Bench',is_enabled=1).one()
    if head.dept_id!=department.id or department.leader_id!=head.id:
        raise RuntimeError('审批人信息化部门关系与批准基线不一致，未修改')
    if owner.dept_id not in (None,department.id):
        raise RuntimeError('ael现有部门已变化，未覆盖现有归属')
    operator_context=build_authorization_context(db,owner.id)
    for permission in ('system:role:add','system:user:edit'):enforce_permission(operator_context,permission)
    menu_ids=[db.query(SysMenu.id).filter_by(permission_code=code,status=1).one()[0]
              for code in ('project:archive:view','project:archive:edit')]
    expected_menu_ids=normalize_role_menu_ids(db,menu_ids)
    role=db.query(SysRole).filter_by(role_code=ROLE_CODE).first()
    if role is None:
        result=create_role(db,RoleCreate(role_name='开发机档案审批验收',role_code=ROLE_CODE,
            data_scope=2,product_line_ids=[line.id],menu_ids=menu_ids,
            remark='仅开发机档案审批验收；本部门、12吋Bench，查看及编辑'),operator_id=owner.id)
        role=db.get(SysRole,result['id'])
    else:
        actual_menu_ids=sorted(row.menu_id for row in db.query(SysRoleMenu).filter_by(role_id=role.id))
        actual_line_ids=sorted(row.product_line_id for row in db.query(SysRoleProductLine).filter_by(role_id=role.id))
        if role.status!=1 or role.data_scope!=2 or actual_menu_ids!=expected_menu_ids or actual_line_ids!=[line.id]:
            raise RuntimeError('同名测试角色与批准范围不一致，未覆盖现有配置')
    previous_roles=[row.role_id for row in db.query(SysUserRole).filter_by(user_id=head.id)]
    if role.id not in previous_roles:
        update_user(db,head.id,UserUpdate(role_ids=[*previous_roles,role.id]),operator_id=owner.id)
    if owner.dept_id is None:
        update_user(db,owner.id,UserUpdate(dept_id=department.id),operator_id=owner.id)
    return {'role_id':role.id,'owner_id':owner.id,'head_id':head.id,'department_id':department.id,'line_id':line.id}


def main():
    root=Path(__file__).resolve().parents[2]
    database=root/'.runtime/data/pms-dev.db'
    os.environ['DB_DIALECT']='sqlite';os.environ['SQLITE_DB_PATH']=str(database)
    os.environ['PMS_CONFIG_FILE']=str(root/'backend/.env.local')
    sys.path.insert(0,str(root/'backend'))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    import app.models.init_db
    from app.models.project import PmsProjectArchive
    from app.services.operation_log import serialize_model
    from app.models.user import SysUser

    saved=root/'.runtime/backups'/f'archive-test-access-before-{datetime.now():%Y%m%d-%H%M%S}.db'
    saved.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as source,sqlite3.connect(saved) as target:
        source.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('备份校验失败')
    os.chmod(saved,0o600)
    engine=create_engine(f'sqlite:///{database}')
    try:
        with Session(engine) as db:
            archives={row.id:serialize_model(row) for row in db.query(PmsProjectArchive)}
            users={row.id:(row.password_hash,row.email,row.credential_version) for row in db.query(SysUser)}
            result=configure_test_access(db)
            db.expire_all()
            assert archives=={row.id:serialize_model(row) for row in db.query(PmsProjectArchive)}
            assert users=={row.id:(row.password_hash,row.email,row.credential_version) for row in db.query(SysUser)}
            print(json.dumps({**result,'backup':str(saved),'archives_unchanged':len(archives),
                'credentials_and_email':'unchanged'},ensure_ascii=False))
    finally:engine.dispose()


if __name__=='__main__':main()
