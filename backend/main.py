from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.api import auth, users, roles, menus, depts, projects, sso, erp
from app.api.auth import get_current_user_id, get_current_user_context
from app.models.init_db import init_db
from app.models.rbac import SysRoleMenu, SysMenu, SysUserRole


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化数据库"""
    init_db()
    print(f"   {settings.APP_NAME} 启动成功")
    yield


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

# CORS 中间件（开发阶段允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 内网环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(menus.router)
app.include_router(depts.router)
app.include_router(projects.router)
app.include_router(sso.router)
app.include_router(erp.router)


@app.get("/api/my-menus", tags=["系统"])
def get_my_menus(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """获取当前用户的菜单树（根据角色）"""
    # 获取用户的角色
    role_ids = [ur.role_id for ur in db.query(SysUserRole).filter(SysUserRole.user_id == user_id).all()]
    if not role_ids:
        return []

    # 获取这些角色的所有菜单权限
    menu_ids_set = set()
    for rid in role_ids:
        mids = [rm.menu_id for rm in db.query(SysRoleMenu).filter(SysRoleMenu.role_id == rid).all()]
        menu_ids_set.update(mids)

    if not menu_ids_set:
        return []

    # 构建菜单树
    all_menus = db.query(SysMenu).filter(
        SysMenu.id.in_(menu_ids_set),
        SysMenu.status == 1,
        SysMenu.visible == 1,
    ).order_by(SysMenu.parent_id, SysMenu.sort).all()

    menu_dict = {}
    tree = []
    for m in all_menus:
        node = {"id": m.id, "parent_id": m.parent_id, "menu_name": m.menu_name,
                "menu_type": m.menu_type, "path": m.path, "icon": m.icon, "sort": m.sort,
                "children": []}
        menu_dict[m.id] = node

    for m in all_menus:
        if m.parent_id == 0:
            tree.append(menu_dict[m.id])
        elif m.parent_id in menu_dict:
            menu_dict[m.parent_id]["children"].append(menu_dict[m.id])

    return tree


@app.get("/api/dashboard/stats", tags=["仪表盘"])
def dashboard_stats(
    scope_ctx: dict = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """获取仪表盘统计数据"""
    from app.services import dashboard as dashboard_service
    return dashboard_service.get_dashboard_stats(db, scope_ctx)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
