"""Create inventory menu once; never replenish revoked role grants."""
from app.models.rbac import SysMenu, SysRole, SysRoleMenu


def initialize_inventory_report(db, *, grant_existing_admin=True):
    parent=db.query(SysMenu).filter_by(parent_id=0,menu_name='报表中心',menu_type='M').one_or_none()
    admin=db.query(SysRole).filter_by(role_code='admin').first()
    if parent is None:
        parent=SysMenu(menu_name='报表中心',menu_type='M',parent_id=0,icon='DataAnalysis',sort=3)
        db.add(parent);db.flush()
        if admin and grant_existing_admin:db.add(SysRoleMenu(role_id=admin.id,menu_id=parent.id))
    page=None
    for name,code,kind,path,sort in [('即时库存查询','report:inventory:list','C','/reports/inventory',2),
                                   ('查看','report:inventory:view','B',None,1),('导出','report:inventory:export','B',None,2)]:
        parent_id=parent.id if kind=='C' else page.id
        node=db.query(SysMenu).filter_by(permission_code=code).one_or_none()
        if node:
            if node.parent_id!=parent_id or node.menu_type!=kind or node.path!=path:
                raise RuntimeError('即时库存菜单结构冲突，请先核对数据库')
        else:
            node=SysMenu(parent_id=parent_id,menu_name=name,permission_code=code,menu_type=kind,path=path,sort=sort,icon='Document' if kind=='C' else None)
            db.add(node);db.flush()
            if admin and grant_existing_admin:db.add(SysRoleMenu(role_id=admin.id,menu_id=node.id))
        if kind=='C':page=node
    db.commit()
