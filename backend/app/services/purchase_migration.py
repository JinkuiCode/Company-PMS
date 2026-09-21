"""One-time report menu creation; existing grants are never replenished."""
from app.models.rbac import SysMenu, SysRole, SysRoleMenu


def initialize_purchase_reports(db, *, grant_existing_admin=True):
    nodes = [
        dict(menu_name='报表中心', menu_type='M', icon='DataAnalysis', sort=3),
        dict(menu_name='采购进度查询', menu_type='C', path='/reports/purchase-progress',
             permission_code='report:purchase:list', icon='Document', sort=1),
        dict(menu_name='查看', menu_type='B', permission_code='report:purchase:view', sort=1),
        dict(menu_name='导出', menu_type='B', permission_code='report:purchase:export', sort=2),
    ]
    admin = db.query(SysRole).filter_by(role_code='admin').first()
    resolved = []
    for index, node in enumerate(nodes):
        parent_id = 0 if index == 0 else resolved[0 if index == 1 else 1].id
        query = db.query(SysMenu)
        if index == 0:
            query = query.filter_by(parent_id=0, menu_name=node['menu_name'], menu_type='M')
        else:
            query = query.filter_by(permission_code=node['permission_code'])
        existing = query.one_or_none()
        if existing:
            if existing.parent_id != parent_id or existing.menu_type != node['menu_type'] or existing.path != node.get('path'):
                raise RuntimeError('报表菜单结构冲突，请先核对数据库升级')
            resolved.append(existing)
            continue
        created = SysMenu(parent_id=parent_id, **node)
        db.add(created)
        db.flush()
        resolved.append(created)
        if admin and grant_existing_admin:
            db.add(SysRoleMenu(role_id=admin.id, menu_id=created.id))
    db.commit()
