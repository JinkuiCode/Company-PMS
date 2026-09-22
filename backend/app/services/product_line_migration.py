"""Add organization master data without guessing historical assignments."""
from sqlalchemy import inspect, text
from app.models.product_line import SysProductLine, SysRoleProductLine
from app.models.rbac import SysMenu, SysRole, SysRoleMenu


def upgrade_product_lines(engine):
    with engine.begin() as connection:
        SysProductLine.__table__.create(connection, checkfirst=True)
        SysRoleProductLine.__table__.create(connection, checkfirst=True)
        inspector = inspect(connection)
        if not inspector.has_table('pms_project_archive'):
            return
        columns = {column['name'] for column in inspector.get_columns('pms_project_archive')}
        if 'business_product_line_id' not in columns:
            connection.execute(text('ALTER TABLE pms_project_archive ADD business_product_line_id INT NULL '
                                    'REFERENCES sys_product_line(id)'))
        if not any(index['name'] == 'idx_archive_business_product_line' for index in inspect(connection).get_indexes('pms_project_archive')):
            connection.execute(text('CREATE INDEX idx_archive_business_product_line ON pms_project_archive(business_product_line_id)'))


def initialize_product_line_management(db, *, grant_existing_admin=True):
    parent = db.query(SysMenu).filter_by(parent_id=0, menu_type='M', menu_name='系统管理').one_or_none()
    if parent is None:
        raise RuntimeError('系统管理目录缺失，无法新增产品线菜单')
    admin = db.query(SysRole).filter_by(role_code='admin').one_or_none()
    nodes = [dict(menu_name='产品线管理', menu_type='C', path='/system/product-line',
                  icon='OfficeBuilding', permission_code='system:product-line:list', sort=8)]
    for index, (name, action) in enumerate((('查看', 'view'), ('新增', 'add'), ('编辑', 'edit'),
                                          ('删除', 'delete'), ('迁移', 'migrate')), 1):
        nodes.append(dict(menu_name=name, menu_type='B', permission_code='system:product-line:' + action, sort=index))
    page_id = None
    try:
        for index, node in enumerate(nodes):
            parent_id = parent.id if index == 0 else page_id
            existing = db.query(SysMenu).filter_by(permission_code=node['permission_code']).one_or_none()
            if existing is not None:
                if (existing.parent_id != parent_id or existing.menu_type != node['menu_type']
                        or existing.path != node.get('path')):
                    raise RuntimeError('产品线菜单结构冲突，请先核对升级')
                if index == 0:
                    page_id = existing.id
                continue
            menu = SysMenu(parent_id=parent_id, **node)
            db.add(menu)
            db.flush()
            if index == 0:
                page_id = menu.id
            if admin is not None and grant_existing_admin:
                db.add(SysRoleMenu(role_id=admin.id, menu_id=menu.id))
        db.commit()
    except Exception:
        db.rollback()
        raise
