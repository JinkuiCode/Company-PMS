"""仪表盘统计服务"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta

from app.models.project import PmsProject, PmsTask
from app.models.rbac import SysDept
from app.services.project import get_child_dept_ids


def get_dashboard_stats(db: Session, scope_context: dict) -> dict:
    """获取仪表盘统计数据，严格遵守数据权限"""
    user_id = scope_context["user_id"]
    dept_id = scope_context["dept_id"]
    scope = scope_context["data_scope"]

    # 构建带权限过滤的项目基础查询
    base_query = db.query(PmsProject)
    if scope == 1:
        base_query = base_query.filter(PmsProject.pm_id == user_id)
    elif scope == 2:
        if dept_id:
            base_query = base_query.filter(PmsProject.dept_id == dept_id)
    elif scope == 3:
        if dept_id:
            allowed = get_child_dept_ids(db, dept_id)
            base_query = base_query.filter(PmsProject.dept_id.in_(allowed))
    # scope == 4: 不过滤

    # 获取可见项目 ID 列表（后续统计共用）
    visible_project_ids = [p.id for p in base_query.all()]

    # 1. 总数统计
    total_projects = len(visible_project_ids)
    total_tasks = 0
    if visible_project_ids:
        total_tasks = db.query(func.count(PmsTask.id)).filter(
            PmsTask.project_id.in_(visible_project_ids)
        ).scalar() or 0

    # 2. 平均进度
    avg_progress = 0.0
    if visible_project_ids:
        avg_progress = db.query(func.avg(PmsTask.progress)).filter(
            PmsTask.project_id.in_(visible_project_ids)
        ).scalar()
        avg_progress = round(float(avg_progress or 0), 1)

    # 3. 项目状态分布
    status_counts = {"ongoing": 0, "finished": 0, "paused": 0}
    if visible_project_ids:
        projects = db.query(PmsProject).filter(PmsProject.id.in_(visible_project_ids)).all()
        for p in projects:
            if p.status == 1:
                status_counts["ongoing"] += 1
            elif p.status == 2:
                status_counts["finished"] += 1
            elif p.status == 3:
                status_counts["paused"] += 1

    # 4. 部门项目分布
    dept_distribution = []
    if visible_project_ids:
        dept_stats = db.query(
            PmsProject.dept_id, func.count(PmsProject.id)
        ).filter(
            PmsProject.id.in_(visible_project_ids)
        ).group_by(PmsProject.dept_id).all()
        for dept_id_val, cnt in dept_stats:
            dept = db.query(SysDept).filter(SysDept.id == dept_id_val).first()
            dept_distribution.append({
                "dept_name": dept.dept_name if dept else "未知部门",
                "count": cnt,
            })

    # 5. 临期项目（7 天内到期且未完结）
    today = date.today()
    deadline_date = today + timedelta(days=7)
    nearing_deadline = []
    if visible_project_ids:
        near = db.query(PmsProject).filter(
            PmsProject.id.in_(visible_project_ids),
            PmsProject.end_date >= today,
            PmsProject.end_date <= deadline_date,
            PmsProject.status != 2,
        ).order_by(PmsProject.end_date).all()
        for p in near:
            nearing_deadline.append({
                "id": p.id,
                "project_name": p.project_name,
                "end_date": str(p.end_date) if p.end_date else "",
            })

    # 6. 最近项目（前 5 个）
    recent_projects = []
    if visible_project_ids:
        recent = db.query(PmsProject).filter(
            PmsProject.id.in_(visible_project_ids)
        ).order_by(PmsProject.created_at.desc()).limit(5).all()
        for p in recent:
            dept = db.query(SysDept).filter(SysDept.id == p.dept_id).first()
            task_count = db.query(func.count(PmsTask.id)).filter(
                PmsTask.project_id == p.id
            ).scalar() or 0
            prog = db.query(func.avg(PmsTask.progress)).filter(
                PmsTask.project_id == p.id
            ).scalar() or 0
            recent_projects.append({
                "id": p.id,
                "project_code": p.project_code,
                "project_name": p.project_name,
                "dept_name": dept.dept_name if dept else "",
                "status": p.status,
                "task_count": task_count,
                "total_progress": round(float(prog), 1),
            })

    return {
        "total_projects": total_projects,
        "total_tasks": total_tasks,
        "avg_progress": avg_progress,
        "status_distribution": status_counts,
        "dept_distribution": dept_distribution,
        "nearing_deadline": nearing_deadline,
        "recent_projects": recent_projects,
    }
