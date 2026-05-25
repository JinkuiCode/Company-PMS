"""初始化数据库表，创建默认管理员、角色、菜单"""
from app.core.database import engine, SessionLocal, Base
from app.core.security import hash_password

from app.models.user import SysUser, RememberToken  # noqa: F401
from app.models.rbac import SysRole, SysMenu, SysDept, SysUserRole, SysRoleMenu  # noqa: F401
from app.models.project import PmsProject, PmsTask, PmsProgressLog  # noqa: F401


def init_db():
    """创建所有表，并插入默认数据"""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. 创建默认管理员
        admin = db.query(SysUser).filter(SysUser.username == "admin").first()
        if not admin:
            admin = SysUser(username="admin", real_name="系统管理员", password_hash=hash_password("admin123"), status=1)
            db.add(admin)
            db.commit()
            print("默认管理员已创建: admin / admin123")

        # 2. 创建默认角色
        role = db.query(SysRole).filter(SysRole.role_code == "admin").first()
        if not role:
            role = SysRole(role_name="超级管理员", role_code="admin", data_scope=4, remark="拥有全部权限")
            db.add(role)
            db.commit()

        # 3. 分配管理员角色
        if not db.query(SysUserRole).filter_by(user_id=admin.id, role_id=role.id).first():
            db.add(SysUserRole(user_id=admin.id, role_id=role.id))
            db.commit()

        # 4. 创建默认菜单
        if not db.query(SysMenu).first():
            menus = [
                SysMenu(id=1, parent_id=0, menu_name="系统管理", menu_type="M", icon="Setting", sort=1),
                SysMenu(id=11, parent_id=1, menu_name="用户管理", menu_type="C", path="/system/user", permission_code="system:user:list", icon="User", sort=1),
                SysMenu(id=12, parent_id=1, menu_name="角色管理", menu_type="C", path="/system/role", permission_code="system:role:list", icon="Avatar", sort=2),
                SysMenu(id=13, parent_id=1, menu_name="菜单管理", menu_type="C", path="/system/menu", permission_code="system:menu:list", icon="Menu", sort=3),
                SysMenu(id=14, parent_id=1, menu_name="部门管理", menu_type="C", path="/system/dept", permission_code="system:dept:list", icon="OfficeBuilding", sort=4),
                SysMenu(id=3, parent_id=0, menu_name="仪表盘", menu_type="C", path="/dashboard", icon="DataAnalysis", sort=0),
                SysMenu(id=2, parent_id=0, menu_name="项目管理", menu_type="M", icon="Folder", sort=2),
                SysMenu(id=21, parent_id=2, menu_name="项目列表", menu_type="C", path="/project/list", permission_code="project:list", icon="List", sort=1),
            ]
            db.add_all(menus)
            db.commit()
            print("默认菜单已创建")

        # 5. 给管理员角色分配所有菜单权限
        all_menus = db.query(SysMenu).all()
        for menu in all_menus:
            if not db.query(SysRoleMenu).filter_by(role_id=role.id, menu_id=menu.id).first():
                db.add(SysRoleMenu(role_id=role.id, menu_id=menu.id))
        db.commit()

        # 6. 创建示例部门
        if not db.query(SysDept).first():
            depts = [
                SysDept(id=1, parent_id=0, dept_name="技术部", sort=1),
                SysDept(id=2, parent_id=0, dept_name="产品部", sort=2),
            ]
            db.add_all(depts)
            db.commit()

        # 7. 创建示例项目
        if not db.query(PmsProject).first():
            proj = PmsProject(
                id=1, project_code="PMS-2026-001", project_name="企业内部项目管理系统",
                dept_id=1, pm_id=admin.id, status=1, start_date="2026-05-01", end_date="2026-08-31",
                budget=50, description="开发一套企业内部的 PMS 系统，具备项目管理、任务进度跟踪、RBAC权限管控等功能",
            )
            db.add(proj)
            db.commit()

            # 8. 创建示例任务
            tasks = [
                PmsTask(id=1, project_id=1, task_name="需求分析与原型设计", assignee_id=admin.id, progress=100, status=3, start_date="2026-05-01", due_date="2026-05-10", sort=1),
                PmsTask(id=2, project_id=1, task_name="数据库设计与建表", assignee_id=admin.id, progress=100, status=3, start_date="2026-05-05", due_date="2026-05-12", sort=2),
                PmsTask(id=3, project_id=1, task_name="RBAC权限模块开发", assignee_id=admin.id, progress=80, status=2, start_date="2026-05-10", due_date="2026-05-20", sort=3),
                PmsTask(id=4, project_id=1, task_name="项目管理模块开发", assignee_id=admin.id, progress=60, status=2, start_date="2026-05-15", due_date="2026-06-01", sort=4),
                PmsTask(id=5, project_id=1, task_name="进度填报页面开发", assignee_id=admin.id, progress=30, status=2, start_date="2026-05-18", due_date="2026-06-10", sort=5),
                PmsTask(id=6, project_id=1, task_name="测试与部署", assignee_id=admin.id, progress=0, status=1, start_date="2026-06-10", due_date="2026-06-20", sort=6),
            ]
            db.add_all(tasks)
            db.commit()
            print("示例项目和任务已创建")

    finally:
        db.close()
