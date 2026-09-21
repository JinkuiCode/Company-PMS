from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings, validate_runtime_config
from app.core.database import engine, get_db
from app.api import auth, users, roles, menus, depts, projects, sso, erp, dicts, operation_logs, field_catalog, field_policies
from app.api import parameters
from app.api import sync_tasks
from app.api import purchase_reports
from app.services.authorization import get_current_user_context, require_permission
from app.models.init_db import init_db
from app.services.database_revision import check_database_ready
from app.models.rbac import SysRole, SysRoleMenu, SysMenu, SysUserRole


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Production startup is read-only; upgrades require a separate command."""
    validate_runtime_config(settings)
    if settings.PMS_ENV == "production":
        check_database_ready(engine)
    else:
        init_db()
    print(f"   {settings.APP_NAME} 启动成功")
    import threading
    import asyncio
    from app.core.database import SessionLocal
    from app.services.erp_queue import worker
    stop = threading.Event()
    runner = threading.Thread(target=worker, args=(stop, SessionLocal), daemon=True, name='pms-erp-worker') if settings.ERP_SYNC_WORKER_ENABLED else None
    if runner:
        runner.start()
    try:
        yield
    finally:
        stop.set()
        if runner:
            await asyncio.to_thread(runner.join, 300)


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def private_validation_error(request, exc):
    if request.url.path.startswith(("/api/auth/", "/api/sso/", "/api/parameters", "/api/users")):
        return JSONResponse(status_code=422, content={"detail": [
            {key: error[key] for key in ("type", "loc", "msg") if key in error}
            for error in exc.errors()
        ]})
    return await request_validation_exception_handler(request, exc)

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
app.include_router(parameters.router)
app.include_router(sync_tasks.router)
app.include_router(purchase_reports.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(menus.router)
app.include_router(depts.router)
app.include_router(projects.router)
app.include_router(sso.router)
app.include_router(erp.router)
app.include_router(dicts.router)
app.include_router(operation_logs.router)
app.include_router(field_catalog.router)
app.include_router(field_policies.router)


@app.get("/api/health", tags=["系统"], include_in_schema=False)
def health_check():
    return {"status": "ok"}


@app.get("/api/my-menus", tags=["系统"])
def get_my_menus(scope_ctx: dict = Depends(get_current_user_context), db: Session = Depends(get_db)):
    """获取当前用户的菜单树（根据角色）"""
    # 获取用户的角色
    role_ids = [role_id for (role_id,) in db.query(SysUserRole.role_id).join(
        SysRole, SysRole.id == SysUserRole.role_id
    ).filter(
        SysUserRole.user_id == scope_ctx["user_id"],
        SysRole.status == 1,
    ).all()]
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
        SysMenu.menu_type.in_(["M", "C"]),
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
    scope_ctx: dict = Depends(require_permission("dashboard:view")),
    db: Session = Depends(get_db),
):
    """获取仪表盘统计数据"""
    from app.services import dashboard as dashboard_service
    return dashboard_service.get_dashboard_stats(db, scope_ctx)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
