"""One-time explicit administrator data grant; revocation is never replenished."""
from app.models.rbac import SysMenu, SysRole, SysRoleMenu
from app.services.business_data_scope import ALL_BUSINESS_DATA


def initialize_all_business_data(db, *, grant_existing_admin=True):
    if db.query(SysMenu).filter_by(permission_code=ALL_BUSINESS_DATA).first():
        return
    node = SysMenu(parent_id=0, menu_name='全部业务数据', visible=0,
                   menu_type='B', permission_code=ALL_BUSINESS_DATA, sort=90)
    db.add(node)
    db.flush()
    admin = db.query(SysRole).filter_by(role_code='admin').first()
    if admin and grant_existing_admin:
        db.add(SysRoleMenu(role_id=admin.id, menu_id=node.id))
    db.commit()
