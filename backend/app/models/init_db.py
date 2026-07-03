"""初始化数据库表，创建默认管理员、角色、菜单"""
import datetime

from sqlalchemy import text
from app.core.database import engine, SessionLocal, Base
from app.core.security import hash_password

from app.models.user import SysUser, RememberToken  # noqa: F401
from app.models.rbac import SysRole, SysMenu, SysDept, SysUserRole, SysRoleMenu  # noqa: F401
from app.models.project import PmsProject, PmsTask, PmsProgressLog, PmsProjectArchive, ErpSyncLog  # noqa: F401
from app.models.dict import SysDict, SysDictItem  # noqa: F401


def _init_dict_data(db):
    """初始化数据字典：每个表单页面的字段映射"""
    dict_categories = [
        {"dict_code": "user_manage", "dict_name": "用户管理", "page_name": "用户管理", "table_name": "sys_user", "sort": 1},
        {"dict_code": "role_manage", "dict_name": "角色管理", "page_name": "角色管理", "table_name": "sys_role", "sort": 2},
        {"dict_code": "project_list", "dict_name": "项目进度", "page_name": "项目进度", "table_name": "pms_project", "sort": 3},
        {"dict_code": "project_archive", "dict_name": "项目档案", "page_name": "项目档案", "table_name": "pms_project_archive", "sort": 4},
        {"dict_code": "project_task", "dict_name": "任务进度", "page_name": "项目进度", "table_name": "pms_task", "sort": 5},
        # 枚举定义（供下拉框使用）
        {"dict_code": "archive_status", "dict_name": "档案状态", "page_name": "枚举定义", "table_name": "pms_project_archive", "field_name": "status", "sort": 10},
        {"dict_code": "project_status", "dict_name": "项目状态", "page_name": "枚举定义", "table_name": "pms_project", "field_name": "status", "sort": 11},
        {"dict_code": "product_line", "dict_name": "产品线", "page_name": "枚举定义", "table_name": "pms_project_archive", "field_name": "product_line", "sort": 12},
        {"dict_code": "product_type", "dict_name": "产品类型", "page_name": "枚举定义", "table_name": "pms_project_archive", "field_name": "product_type", "sort": 13},
        {"dict_code": "task_status", "dict_name": "任务状态", "page_name": "枚举定义", "table_name": "pms_task", "field_name": "status", "sort": 14},
        {"dict_code": "erp_sync_status", "dict_name": "同步状态", "page_name": "枚举定义", "table_name": "pms_project_archive", "field_name": "erp_sync_status", "sort": 15},
        {"dict_code": "data_scope", "dict_name": "数据权限", "page_name": "枚举定义", "table_name": "sys_role", "field_name": "data_scope", "sort": 16},
    ]
    dict_items = {
        # ===== 用户管理 字段 =====
        "user_manage": [
            {"item_value": "username", "item_label": "用户名", "field_type": "text", "sort": 1},
            {"item_value": "real_name", "item_label": "姓名", "field_type": "text", "sort": 2},
            {"item_value": "dept_id", "item_label": "部门", "field_type": "relation", "description": "sys_dept.id", "sort": 3},
            {"item_value": "mobile", "item_label": "手机号", "field_type": "text", "sort": 4},
            {"item_value": "status", "item_label": "状态", "field_type": "enum", "description": "1=启用 0=禁用", "sort": 5},
        ],
        # ===== 角色管理 字段 =====
        "role_manage": [
            {"item_value": "role_name", "item_label": "角色名称", "field_type": "text", "sort": 1},
            {"item_value": "role_code", "item_label": "角色编码", "field_type": "text", "sort": 2},
            {"item_value": "data_scope", "item_label": "数据权限", "field_type": "enum", "description": "1=本人 2=本部门 3=本部门及子部门 4=全部", "sort": 3},
            {"item_value": "status", "item_label": "状态", "field_type": "enum", "description": "1=启用 0=禁用", "sort": 4},
            {"item_value": "remark", "item_label": "备注", "field_type": "text", "sort": 5},
        ],
        # ===== 项目进度 字段 =====
        "project_list": [
            {"item_value": "project_code", "item_label": "项目编号", "field_type": "text", "sort": 1},
            {"item_value": "project_name", "item_label": "项目名称", "field_type": "text", "sort": 2},
            {"item_value": "dept_id", "item_label": "所属部门", "field_type": "relation", "description": "sys_dept.id", "sort": 3},
            {"item_value": "pm_id", "item_label": "项目经理", "field_type": "relation", "description": "sys_user.id", "sort": 4},
            {"item_value": "status", "item_label": "状态", "field_type": "enum", "description": "1=进行中 2=已完结 3=暂停", "sort": 5},
            {"item_value": "start_date", "item_label": "开始日期", "field_type": "date", "sort": 6},
            {"item_value": "end_date", "item_label": "结束日期", "field_type": "date", "sort": 7},
            {"item_value": "budget", "item_label": "预算(万元)", "field_type": "number", "sort": 8},
            {"item_value": "description", "item_label": "项目描述", "field_type": "text", "sort": 9},
        ],
        # ===== 项目档案 字段 =====
        "project_archive": [
            {"item_value": "project_code", "item_label": "项目编号", "field_type": "text", "sort": 1},
            {"item_value": "project_name", "item_label": "项目名称", "field_type": "text", "sort": 2},
            {"item_value": "status", "item_label": "状态", "field_type": "enum", "description": "1=未启动 2=进行中 3=已完结 4=暂停", "sort": 3},
            {"item_value": "manager_id", "item_label": "负责人", "field_type": "relation", "description": "sys_user.id", "sort": 4},
            {"item_value": "product_line", "item_label": "产品线", "field_type": "enum", "description": "Bench/光伏/Single/HOTSPM", "sort": 5},
            {"item_value": "product_type", "item_label": "产品类型", "field_type": "enum", "description": "链式/槽式", "sort": 6},
            {"item_value": "plan_start_date", "item_label": "计划开始", "field_type": "date", "sort": 7},
            {"item_value": "plan_end_date", "item_label": "计划结束", "field_type": "date", "sort": 8},
            {"item_value": "erp_sync_status", "item_label": "同步状态", "field_type": "enum", "description": "success/failed/pending", "sort": 9},
            {"item_value": "erp_sync_time", "item_label": "最后同步时间", "field_type": "date", "sort": 10},
        ],
        # ===== 任务进度 字段 =====
        "project_task": [
            {"item_value": "task_name", "item_label": "任务名称", "field_type": "text", "sort": 1},
            {"item_value": "assignee_id", "item_label": "负责人", "field_type": "relation", "description": "sys_user.id", "sort": 2},
            {"item_value": "progress", "item_label": "进度(%)", "field_type": "number", "sort": 3},
            {"item_value": "status", "item_label": "状态", "field_type": "enum", "description": "1=未开始 2=进行中 3=已完成", "sort": 4},
            {"item_value": "start_date", "item_label": "开始日期", "field_type": "date", "sort": 5},
            {"item_value": "due_date", "item_label": "截止日期", "field_type": "date", "sort": 6},
            {"item_value": "sort", "item_label": "排序", "field_type": "number", "sort": 7},
        ],
        # ===== 枚举定义 =====
        "archive_status": [
            {"item_value": "1", "item_label": "未启动", "sort": 1},
            {"item_value": "2", "item_label": "进行中", "sort": 2},
            {"item_value": "3", "item_label": "已完结", "sort": 3},
            {"item_value": "4", "item_label": "暂停", "sort": 4},
        ],
        "project_status": [
            {"item_value": "1", "item_label": "进行中", "sort": 1},
            {"item_value": "2", "item_label": "已完结", "sort": 2},
            {"item_value": "3", "item_label": "暂停", "sort": 3},
        ],
        "product_line": [
            {"item_value": "Bench", "item_label": "Bench", "sort": 1},
            {"item_value": "光伏", "item_label": "光伏", "sort": 2},
            {"item_value": "Single", "item_label": "Single", "sort": 3},
            {"item_value": "HOTSPM", "item_label": "HOTSPM", "sort": 4},
        ],
        "product_type": [
            {"item_value": "链式", "item_label": "链式", "sort": 1},
            {"item_value": "槽式", "item_label": "槽式", "sort": 2},
        ],
        "task_status": [
            {"item_value": "1", "item_label": "未开始", "sort": 1},
            {"item_value": "2", "item_label": "进行中", "sort": 2},
            {"item_value": "3", "item_label": "已完成", "sort": 3},
        ],
        "erp_sync_status": [
            {"item_value": "success", "item_label": "成功", "sort": 1},
            {"item_value": "failed", "item_label": "失败", "sort": 2},
            {"item_value": "pending", "item_label": "待同步", "sort": 3},
        ],
        "data_scope": [
            {"item_value": "1", "item_label": "本人", "sort": 1},
            {"item_value": "2", "item_label": "本部门", "sort": 2},
            {"item_value": "3", "item_label": "本部门及子部门", "sort": 3},
            {"item_value": "4", "item_label": "全部", "sort": 4},
        ],
    }
    for cat in dict_categories:
        existing = db.query(SysDict).filter(SysDict.dict_code == cat["dict_code"]).first()
        if not existing:
            d = SysDict(**cat)
            db.add(d)
            db.commit()
            db.refresh(d)
            for item in dict_items.get(cat["dict_code"], []):
                db.add(SysDictItem(dict_id=d.id, **item))
            db.commit()
            print(f"初始化字典: {cat['dict_name']}")
        else:
            # 已存在的分类：更新表名等元数据
            changed = False
            for k, v in cat.items():
                if k != "dict_code" and getattr(existing, k, None) != v:
                    setattr(existing, k, v)
                    changed = True
            if changed:
                db.commit()


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
                SysMenu(id=13, parent_id=1, menu_name="数据字典", menu_type="C", path="/system/dict", permission_code="system:dict:list", icon="Collection", sort=3),
                SysMenu(id=15, parent_id=1, menu_name="字段管理", menu_type="C", path="/system/field", permission_code="system:field:list", icon="List", sort=4),
                SysMenu(id=3, parent_id=0, menu_name="仪表盘", menu_type="C", path="/dashboard", icon="DataAnalysis", sort=0),
                SysMenu(id=2, parent_id=0, menu_name="项目管理", menu_type="M", icon="Folder", sort=2),
                SysMenu(id=22, parent_id=2, menu_name="项目档案", menu_type="C", path="/project/archive", permission_code="project:archive:list", icon="FolderOpened", sort=1),
                SysMenu(id=21, parent_id=2, menu_name="项目进度", menu_type="C", path="/project/list", permission_code="project:list", icon="List", sort=2),
            ]
            db.add_all(menus)
            db.commit()
            print("默认菜单已创建")

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

        # 4.2 迁移：插入按钮级权限菜单（项目进度 / 项目档案 / 系统管理）
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
            {"id": 132, "parent_id": 13, "menu_name": "新增", "menu_type": "B", "permission_code": "system:dict:add", "sort": 2},
            {"id": 133, "parent_id": 13, "menu_name": "编辑", "menu_type": "B", "permission_code": "system:dict:edit", "sort": 3},
            {"id": 134, "parent_id": 13, "menu_name": "删除", "menu_type": "B", "permission_code": "system:dict:delete", "sort": 4},
            # 字段管理 按钮权限 (parent_id=15)
            {"id": 151, "parent_id": 15, "menu_name": "查看", "menu_type": "B", "permission_code": "system:field:view", "sort": 1},
            {"id": 152, "parent_id": 15, "menu_name": "新增", "menu_type": "B", "permission_code": "system:field:add", "sort": 2},
            {"id": 153, "parent_id": 15, "menu_name": "编辑", "menu_type": "B", "permission_code": "system:field:edit", "sort": 3},
            {"id": 154, "parent_id": 15, "menu_name": "删除", "menu_type": "B", "permission_code": "system:field:delete", "sort": 4},
        ]
        for bm in button_menus:
            existing = db.query(SysMenu).filter(SysMenu.id == bm["id"]).first()
            if not existing:
                db.add(SysMenu(**bm))
        db.commit()

        # 5. 给管理员角色分配所有菜单权限
        all_menus = db.query(SysMenu).all()
        for menu in all_menus:
            if not db.query(SysRoleMenu).filter_by(role_id=role.id, menu_id=menu.id).first():
                db.add(SysRoleMenu(role_id=role.id, menu_id=menu.id))
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
                dept_id=1, pm_id=admin.id, status=1,
                start_date=datetime.date(2026, 5, 1), end_date=datetime.date(2026, 8, 31),
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
