"""初始化数据库表，创建默认管理员、角色、菜单"""
import datetime

from sqlalchemy import inspect, text
from app.core.database import engine, SessionLocal, Base
from app.core.security import hash_password

from app.models.user import SysUser, RememberToken  # noqa: F401
from app.models.rbac import SysRole, SysMenu, SysDept, SysUserRole, SysRoleMenu  # noqa: F401
from app.models.project import PmsProject, PmsTask, PmsProgressLog, PmsProjectArchive, ErpSyncLog, PmsProjectSheetDetail  # noqa: F401
from app.models.dict import SysDict, SysDictItem  # noqa: F401
from app.models.operation_log import SysOperationLog  # noqa: F401


def _init_dict_data(db):
    """迁移旧字段分类并初始化开发注册的业务枚举。"""
    from app.services.enum_registry import initialize_enum_definitions

    return initialize_enum_definitions(db)


def _ensure_role_product_lines_column():
    """Upgrade existing role tables before any ORM query references the new column."""
    inspector = inspect(engine)
    if not inspector.has_table("sys_role"):
        return

    columns = {column["name"] for column in inspector.get_columns("sys_role")}
    if "product_lines" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE sys_role ADD product_lines NVARCHAR(256) NULL"))
    print("迁移完成：sys_role 已添加产品线范围字段")


def init_db():
    """创建所有表，并插入默认数据"""
    is_fresh_database = not inspect(engine).has_table("sys_role")
    Base.metadata.create_all(bind=engine)
    _ensure_role_product_lines_column()

    db = SessionLocal()
    try:
        # 1. 仅全新数据库创建默认管理员和角色，已有数据库不补建权限主体
        admin = db.query(SysUser).filter(SysUser.username == "admin").first()
        if is_fresh_database and not admin:
            admin = SysUser(username="admin", real_name="系统管理员", password_hash=hash_password("admin123"), status=1)
            db.add(admin)
            db.commit()
            print("默认管理员已创建: admin / admin123")

        # 2. 创建默认角色
        role = db.query(SysRole).filter(SysRole.role_code == "admin").first()
        if is_fresh_database and not role:
            role = SysRole(role_name="超级管理员", role_code="admin", data_scope=4, remark="拥有全部权限")
            db.add(role)
            db.commit()

        # 3. 分配管理员角色
        if is_fresh_database and admin and role and not db.query(SysUserRole).filter_by(user_id=admin.id, role_id=role.id).first():
            db.add(SysUserRole(user_id=admin.id, role_id=role.id))
            db.commit()

        # 4. 创建默认菜单
        if not db.query(SysMenu).first():
            menus = [
                SysMenu(id=1, parent_id=0, menu_name="系统管理", menu_type="M", icon="Setting", sort=1),
                SysMenu(id=11, parent_id=1, menu_name="用户管理", menu_type="C", path="/system/user", permission_code="system:user:list", icon="User", sort=1),
                SysMenu(id=12, parent_id=1, menu_name="角色管理", menu_type="C", path="/system/role", permission_code="system:role:list", icon="Avatar", sort=2),
                SysMenu(id=13, parent_id=1, menu_name="数据字典", menu_type="C", path="/system/dict", permission_code="system:dict:list", icon="Collection", sort=3),
                SysMenu(id=15, parent_id=1, menu_name="枚举管理", menu_type="C", path="/system/enum", permission_code="system:enum:list", icon="List", sort=4),
                SysMenu(id=16, parent_id=1, menu_name="操作日志", menu_type="C", path="/system/operation-log", permission_code="system:operation-log:list", icon="Document", sort=5),
                SysMenu(id=3, parent_id=0, menu_name="仪表盘", menu_type="C", path="/dashboard", icon="DataAnalysis", sort=0),
                SysMenu(id=2, parent_id=0, menu_name="项目管理", menu_type="M", icon="Folder", sort=2),
                SysMenu(id=22, parent_id=2, menu_name="项目档案", menu_type="C", path="/project/archive", permission_code="project:archive:list", icon="FolderOpened", sort=1),
                SysMenu(id=21, parent_id=2, menu_name="项目进度", menu_type="C", path="/project/list", permission_code="project:list", icon="List", sort=2),
            ]
            db.add_all(menus)
            db.commit()
            print("默认菜单已创建")

        dashboard_menu = db.query(SysMenu).filter(SysMenu.id == 3).first()
        if dashboard_menu and dashboard_menu.permission_code != "dashboard:view":
            dashboard_menu.permission_code = "dashboard:view"
            db.commit()

        # 4.1 迁移：删除已废弃的「部门管理」菜单（已整合到用户管理）
        old_dept_menu = db.query(SysMenu).filter(SysMenu.id == 14).first()
        if old_dept_menu:
            db.query(SysRoleMenu).filter(SysRoleMenu.menu_id == 14).delete()
            db.delete(old_dept_menu)
            db.commit()
            print("迁移完成：已删除部门管理菜单")

        # 4.2 迁移：「菜单管理」更名为「数据字典」
        menu13 = db.query(SysMenu).filter(SysMenu.id == 13).first()
        if menu13 and (menu13.menu_name != "数据字典" or menu13.path != "/system/dict"):
            menu13.menu_name = "数据字典"
            menu13.path = "/system/dict"
            menu13.permission_code = "system:dict:list"
            menu13.icon = "Collection"
            db.commit()
            print("迁移完成：菜单管理 -> 数据字典")

        # 4.2.1 迁移：字段管理改为只维护开发注册业务枚举，沿用菜单 ID 保留角色授权。
        enum_menu = db.query(SysMenu).filter(SysMenu.id == 15).first()
        desired = {
            "parent_id": 1,
            "menu_name": "枚举管理",
            "menu_type": "C",
            "path": "/system/enum",
            "permission_code": "system:enum:list",
            "icon": "List",
            "sort": 4,
        }
        if not enum_menu:
            enum_menu = SysMenu(id=15, **desired)
            db.add(enum_menu)
            db.commit()
            print("迁移完成：已添加枚举管理菜单")
        else:
            changed = False
            for key, value in desired.items():
                if getattr(enum_menu, key) != value:
                    setattr(enum_menu, key, value)
                    changed = True
            if changed:
                db.commit()
                print("迁移完成：字段管理 -> 枚举管理")

        # 数据字典改为只读目录，删除原新增/编辑/删除按钮权限。
        obsolete_dict_button_ids = [132, 133, 134]
        db.query(SysRoleMenu).filter(SysRoleMenu.menu_id.in_(obsolete_dict_button_ids)).delete(
            synchronize_session=False
        )
        db.query(SysMenu).filter(SysMenu.id.in_(obsolete_dict_button_ids)).delete(
            synchronize_session=False
        )
        db.commit()

        # 4.3 迁移：补齐「操作日志」菜单
        operation_log_menu = db.query(SysMenu).filter(SysMenu.id == 16).first()
        if not operation_log_menu:
            db.add(SysMenu(
                id=16, parent_id=1, menu_name="操作日志", menu_type="C",
                path="/system/operation-log", permission_code="system:operation-log:list",
                icon="Document", sort=5,
            ))
            db.commit()
            print("迁移完成：已添加操作日志菜单")
        else:
            changed = False
            desired = {
                "parent_id": 1,
                "menu_name": "操作日志",
                "menu_type": "C",
                "path": "/system/operation-log",
                "permission_code": "system:operation-log:list",
                "icon": "Document",
                "sort": 5,
            }
            for key, value in desired.items():
                if getattr(operation_log_menu, key) != value:
                    setattr(operation_log_menu, key, value)
                    changed = True
            if changed:
                db.commit()
                print("迁移完成：已更新操作日志菜单")

        # 4.4 迁移：插入按钮级权限菜单（项目进度 / 项目档案 / 系统管理）
        button_menus = [
            # 项目进度 按钮权限 (parent_id=21)
            {"id": 211, "parent_id": 21, "menu_name": "查看", "menu_type": "B", "permission_code": "project:list:view", "sort": 1},
            {"id": 212, "parent_id": 21, "menu_name": "新增", "menu_type": "B", "permission_code": "project:list:add", "sort": 2},
            {"id": 213, "parent_id": 21, "menu_name": "编辑", "menu_type": "B", "permission_code": "project:list:edit", "sort": 3},
            {"id": 214, "parent_id": 21, "menu_name": "删除", "menu_type": "B", "permission_code": "project:list:delete", "sort": 4},
            # 项目档案 按钮权限 (parent_id=22)
            {"id": 221, "parent_id": 22, "menu_name": "查看", "menu_type": "B", "permission_code": "project:archive:view", "sort": 1},
            {"id": 222, "parent_id": 22, "menu_name": "新增", "menu_type": "B", "permission_code": "project:archive:add", "sort": 2},
            {"id": 223, "parent_id": 22, "menu_name": "编辑", "menu_type": "B", "permission_code": "project:archive:edit", "sort": 3},
            {"id": 224, "parent_id": 22, "menu_name": "删除", "menu_type": "B", "permission_code": "project:archive:delete", "sort": 4},
            {"id": 225, "parent_id": 22, "menu_name": "同步", "menu_type": "B", "permission_code": "project:archive:sync", "sort": 5},
            # 系统管理 按钮权限 (parent_id=1)
            {"id": 111, "parent_id": 11, "menu_name": "查看", "menu_type": "B", "permission_code": "system:user:view", "sort": 1},
            {"id": 112, "parent_id": 11, "menu_name": "新增", "menu_type": "B", "permission_code": "system:user:add", "sort": 2},
            {"id": 113, "parent_id": 11, "menu_name": "编辑", "menu_type": "B", "permission_code": "system:user:edit", "sort": 3},
            {"id": 114, "parent_id": 11, "menu_name": "删除", "menu_type": "B", "permission_code": "system:user:delete", "sort": 4},
            {"id": 121, "parent_id": 12, "menu_name": "查看", "menu_type": "B", "permission_code": "system:role:view", "sort": 1},
            {"id": 122, "parent_id": 12, "menu_name": "新增", "menu_type": "B", "permission_code": "system:role:add", "sort": 2},
            {"id": 123, "parent_id": 12, "menu_name": "编辑", "menu_type": "B", "permission_code": "system:role:edit", "sort": 3},
            {"id": 124, "parent_id": 12, "menu_name": "删除", "menu_type": "B", "permission_code": "system:role:delete", "sort": 4},
            {"id": 131, "parent_id": 13, "menu_name": "查看", "menu_type": "B", "permission_code": "system:dict:view", "sort": 1},
            # 枚举管理按钮权限，沿用原字段管理菜单 ID 保留现有角色授权关系。
            {"id": 151, "parent_id": 15, "menu_name": "查看", "menu_type": "B", "permission_code": "system:enum:view", "sort": 1},
            {"id": 152, "parent_id": 15, "menu_name": "新增", "menu_type": "B", "permission_code": "system:enum:add", "sort": 2},
            {"id": 153, "parent_id": 15, "menu_name": "编辑", "menu_type": "B", "permission_code": "system:enum:edit", "sort": 3},
            {"id": 154, "parent_id": 15, "menu_name": "删除", "menu_type": "B", "permission_code": "system:enum:delete", "sort": 4},
            # 操作日志 按钮权限 (parent_id=16)
            {"id": 161, "parent_id": 16, "menu_name": "查看", "menu_type": "B", "permission_code": "system:operation-log:view", "sort": 1},
        ]
        for bm in button_menus:
            existing = db.query(SysMenu).filter(SysMenu.id == bm["id"]).first()
            if not existing:
                db.add(SysMenu(**bm))
            else:
                for key, value in bm.items():
                    if key != "id":
                        setattr(existing, key, value)
        db.commit()

        # 5. 仅全新数据库首次给默认管理员授权；后续启动绝不回补人工撤销的权限
        if is_fresh_database and role:
            all_menus = db.query(SysMenu).all()
            db.add_all([SysRoleMenu(role_id=role.id, menu_id=menu.id) for menu in all_menus])
            db.commit()

        # 5.8 初始化数据字典分类和枚举项
        _init_dict_data(db)

        # 5.5 迁移：pms_project_archive 表添加 ERP 同步字段
        try:
            db.execute(text("SELECT erp_synced FROM pms_project_archive"))
        except Exception:
            db.execute(text("ALTER TABLE pms_project_archive ADD erp_synced INT NOT NULL DEFAULT 0"))
            db.execute(text("ALTER TABLE pms_project_archive ADD erp_sync_time DATETIME NULL"))
            db.execute(text("ALTER TABLE pms_project_archive ADD erp_sync_status NVARCHAR(32) NULL"))
            db.execute(text("ALTER TABLE pms_project_archive ADD erp_error_msg NVARCHAR(512) NULL"))
            db.commit()
            print("迁移完成：pms_project_archive 已添加 ERP 同步字段")

        # 5.6 迁移：pms_project_archive 表添加新业务字段
        try:
            db.execute(text("SELECT product_line FROM pms_project_archive"))
        except Exception:
            db.execute(text("ALTER TABLE pms_project_archive ADD product_line NVARCHAR(32) NULL"))
            db.execute(text("ALTER TABLE pms_project_archive ADD plan_start_date DATETIME NULL"))
            db.execute(text("ALTER TABLE pms_project_archive ADD plan_end_date DATETIME NULL"))
            db.execute(text("ALTER TABLE pms_project_archive ADD created_by INT NULL"))
            db.execute(text("ALTER TABLE pms_project_archive ADD updated_by INT NULL"))
            db.commit()
            print("迁移完成：pms_project_archive 已添加 product_line/plan_start_date/plan_end_date/created_by/updated_by")

        # 5.7 迁移：pms_project_archive 表添加 erp_sync_by 字段
        try:
            db.execute(text("SELECT erp_sync_by FROM pms_project_archive"))
        except Exception:
            db.execute(text("ALTER TABLE pms_project_archive ADD erp_sync_by INT NULL"))
            db.commit()
            print("迁移完成：pms_project_archive 已添加 erp_sync_by 字段")

        # 5.8 迁移：pms_project 表添加产品线兜底字段
        try:
            db.execute(text("SELECT product_line FROM pms_project"))
        except Exception:
            db.rollback()
            db.execute(text("ALTER TABLE pms_project ADD product_line NVARCHAR(32) NULL"))
            db.commit()
            print("迁移完成：pms_project 已添加 product_line 字段")

        # 5.9 迁移：pms_project 表添加阶段进度字段
        try:
            db.execute(text("SELECT design_progress FROM pms_project"))
        except Exception:
            db.rollback()
            db.execute(text("ALTER TABLE pms_project ADD design_progress INT NULL"))
            db.execute(text("ALTER TABLE pms_project ADD order_progress INT NULL"))
            db.execute(text("ALTER TABLE pms_project ADD kit_progress INT NULL"))
            db.execute(text("ALTER TABLE pms_project ADD frame_progress INT NULL"))
            db.execute(text("ALTER TABLE pms_project ADD dryer_progress INT NULL"))
            db.execute(text("ALTER TABLE pms_project ADD assembly_progress INT NULL"))
            db.execute(text("ALTER TABLE pms_project ADD test_progress INT NULL"))
            db.commit()
            print("迁移完成：pms_project 已添加阶段进度字段")

        # 6. 创建示例部门
        if not db.query(SysDept).first():
            depts = [
                SysDept(id=1, parent_id=0, dept_name="技术部", sort=1),
                SysDept(id=2, parent_id=0, dept_name="产品部", sort=2),
            ]
            db.add_all(depts)
            db.commit()

        # 7. 创建示例项目
        if admin and not db.query(PmsProject).first():
            proj = PmsProject(
                id=1, project_code="PMS-2026-001", project_name="企业内部项目管理系统",
                dept_id=1, pm_id=admin.id, status=1,
                product_line="Bench",
                start_date=datetime.date(2026, 5, 1), end_date=datetime.date(2026, 8, 31),
                design_progress=100, order_progress=100, kit_progress=80, frame_progress=60,
                dryer_progress=45, assembly_progress=30, test_progress=0,
                budget=50, description="开发一套企业内部的 PMS 系统，具备项目管理、任务进度跟踪、RBAC权限管控等功能",
            )
            db.add(proj)
            db.commit()

            # 8. 创建示例任务
            tasks = [
                PmsTask(id=1, project_id=1, task_name="需求分析与原型设计", assignee_id=admin.id, progress=100, status=3, start_date=datetime.date(2026, 5, 1), due_date=datetime.date(2026, 5, 10), sort=1),
                PmsTask(id=2, project_id=1, task_name="数据库设计与建表", assignee_id=admin.id, progress=100, status=3, start_date=datetime.date(2026, 5, 5), due_date=datetime.date(2026, 5, 12), sort=2),
                PmsTask(id=3, project_id=1, task_name="RBAC权限模块开发", assignee_id=admin.id, progress=80, status=2, start_date=datetime.date(2026, 5, 10), due_date=datetime.date(2026, 5, 20), sort=3),
                PmsTask(id=4, project_id=1, task_name="项目管理模块开发", assignee_id=admin.id, progress=60, status=2, start_date=datetime.date(2026, 5, 15), due_date=datetime.date(2026, 6, 1), sort=4),
                PmsTask(id=5, project_id=1, task_name="进度填报页面开发", assignee_id=admin.id, progress=30, status=2, start_date=datetime.date(2026, 5, 18), due_date=datetime.date(2026, 6, 10), sort=5),
                PmsTask(id=6, project_id=1, task_name="测试与部署", assignee_id=admin.id, progress=0, status=1, start_date=datetime.date(2026, 6, 10), due_date=datetime.date(2026, 6, 20), sort=6),
            ]
            db.add_all(tasks)
            db.commit()
            print("示例项目和任务已创建")

    finally:
        db.close()
