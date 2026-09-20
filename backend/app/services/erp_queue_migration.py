"""Menu grants occur only when the new permission nodes are first created."""
from app.models.rbac import SysMenu, SysRole, SysRoleMenu


def initialize_sync_management(db, *, grant_existing_admin=True):
    nodes = [
        dict(id=19, parent_id=1, menu_name='同步管理', menu_type='C', path='/system/sync', permission_code='system:sync:list', icon='Refresh', sort=8),
        dict(id=191, parent_id=19, menu_name='查看', menu_type='B', permission_code='system:sync:view', sort=1),
        dict(id=192, parent_id=19, menu_name='重试与核查', menu_type='B', permission_code='system:sync:retry', sort=2),
    ]
    admins = db.query(SysRole).filter(SysRole.role_code.in_(['admin', 'business_admin'])).all()
    for node in nodes:
        if db.get(SysMenu, node['id']) is None:
            db.add(SysMenu(**node))
            for role in admins:
                if role.role_code == 'admin' and not grant_existing_admin:
                    continue
                db.add(SysRoleMenu(role_id=role.id, menu_id=node['id']))
    db.commit()
