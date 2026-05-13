"""项目管理业务逻辑"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException

from app.models.project import PmsProject, PmsTask, PmsProgressLog
from app.models.user import SysUser
from app.models.rbac import SysDept
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    TaskCreate, TaskUpdate, TaskResponse,
)


# ==================== 项目 ====================
def get_project_list(db: Session, page: int = 1, page_size: int = 15, dept_id: int | None = None, status: int | None = None):
    query = db.query(PmsProject)
    if dept_id:
        query = query.filter(PmsProject.dept_id == dept_id)
    if status:
        query = query.filter(PmsProject.status == status)

    total = query.count()
    projects = query.order_by(PmsProject.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for p in projects:
        dept = db.query(SysDept).filter(SysDept.id == p.dept_id).first()
        pm = db.query(SysUser).filter(SysUser.id == p.pm_id).first()
        total_tasks = db.query(PmsTask).filter(PmsTask.project_id == p.id).count()
        avg_progress = db.query(func.avg(PmsTask.progress)).filter(PmsTask.project_id == p.id).scalar() or 0

        items.append(ProjectResponse(
            id=p.id, project_code=p.project_code, project_name=p.project_name,
            dept_id=p.dept_id, pm_id=p.pm_id, status=p.status,
            start_date=p.start_date, end_date=p.end_date,
            budget=p.budget, description=p.description,
            dept_name=dept.dept_name if dept else "",
            pm_name=pm.real_name if pm else "",
            task_count=total_tasks, total_progress=round(float(avg_progress), 1),
            created_at=p.created_at, updated_at=p.updated_at,
        ))
    return {"total": total, "items": items}


def create_project(db: Session, data: ProjectCreate):
    if db.query(PmsProject).filter(PmsProject.project_code == data.project_code).first():
        raise HTTPException(status_code=400, detail="项目编号已存在")
    proj = PmsProject(**data.model_dump())
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return {"msg": "创建成功", "id": proj.id}


def update_project(db: Session, project_id: int, data: ProjectUpdate):
    proj = db.query(PmsProject).filter(PmsProject.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(proj, key, val)
    db.commit()
    return {"msg": "更新成功"}


def delete_project(db: Session, project_id: int):
    proj = db.query(PmsProject).filter(PmsProject.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    db.query(PmsTask).filter(PmsTask.project_id == project_id).delete()
    db.delete(proj)
    db.commit()
    return {"msg": "删除成功"}


# ==================== 任务 & 进度 ====================
def get_tasks(db: Session, project_id: int) -> list[TaskResponse]:
    tasks = db.query(PmsTask).filter(PmsTask.project_id == project_id).order_by(PmsTask.sort, PmsTask.id).all()
    result = []
    for t in tasks:
        user = db.query(SysUser).filter(SysUser.id == t.assignee_id).first()
        result.append(TaskResponse(
            id=t.id, project_id=t.project_id, task_name=t.task_name,
            assignee_id=t.assignee_id, progress=t.progress, status=t.status,
            start_date=t.start_date, due_date=t.due_date, parent_id=t.parent_id, sort=t.sort,
            assignee_name=user.real_name if user else "",
            created_at=t.created_at, updated_at=t.updated_at,
        ))
    return result


def create_task(db: Session, data: TaskCreate):
    task = PmsTask(**data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"msg": "创建成功", "id": task.id}


def update_task(db: Session, task_id: int, data: TaskUpdate, operator_id: int):
    task = db.query(PmsTask).filter(PmsTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    old_progress = task.progress

    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(task, key, val)

    # 如果进度发生变化，记录日志
    if "progress" in update_data and update_data["progress"] != old_progress:
        log = PmsProgressLog(
            task_id=task_id, old_progress=old_progress, new_progress=update_data["progress"],
            operator_id=operator_id,
        )
        db.add(log)

    db.commit()
    return {"msg": "更新成功", "id": task.id}


def delete_task(db: Session, task_id: int):
    task = db.query(PmsTask).filter(PmsTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    db.query(PmsProgressLog).filter(PmsProgressLog.task_id == task_id).delete()
    db.delete(task)
    db.commit()
    return {"msg": "删除成功"}


def get_progress_logs(db: Session, task_id: int) -> list[dict]:
    logs = db.query(PmsProgressLog).filter(PmsProgressLog.task_id == task_id).order_by(PmsProgressLog.created_at.desc()).all()
    return [
        {"id": l.id, "task_id": l.task_id, "old_progress": l.old_progress,
         "new_progress": l.new_progress, "operator_id": l.operator_id,
         "remark": l.remark, "created_at": str(l.created_at)}
        for l in logs
    ]
