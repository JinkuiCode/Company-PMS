import datetime

from sqlalchemy import Integer, DateTime, ForeignKey, func, DECIMAL, Index
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PmsProjectArchive(Base):
    """项目档案表"""
    __tablename__ = "pms_project_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(NVARCHAR(32), unique=True, nullable=False, comment="项目编号")
    project_name: Mapped[str] = mapped_column(NVARCHAR(128), nullable=False, comment="项目名称")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1未启动 2进行中 3已完结 4暂停")
    manager_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), default=None, comment="负责人ID")
    product_type: Mapped[str | None] = mapped_column(NVARCHAR(64), default=None, comment="产品类型")
    product_line: Mapped[str | None] = mapped_column(NVARCHAR(32), default=None, comment="产品线: Bench/光伏/Single/HOTSPM")
    plan_start_date: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=None, comment="计划开始日期")
    plan_end_date: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=None, comment="计划结束日期")
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), default=None, comment="创建人ID")
    updated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), default=None, comment="最后编辑人ID")
    # ERP 同步字段
    erp_synced: Mapped[int] = mapped_column(Integer, default=0, comment="是否已同步到金蝶: 0否 1是")
    erp_sync_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=None, comment="最后同步时间")
    erp_sync_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), default=None, comment="最后同步人ID")
    erp_sync_status: Mapped[str | None] = mapped_column(NVARCHAR(32), default=None, comment="同步状态: success/failed/pending")
    erp_error_msg: Mapped[str | None] = mapped_column(NVARCHAR(512), default=None, comment="同步失败错误信息")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ErpSyncLog(Base):
    """ERP 同步日志表"""
    __tablename__ = "erp_sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="PMS 项目档案 ID")
    action: Mapped[str] = mapped_column(NVARCHAR(16), nullable=False, comment="操作: create/update")
    status: Mapped[str] = mapped_column(NVARCHAR(16), nullable=False, comment="success/failed")
    error_msg: Mapped[str | None] = mapped_column(NVARCHAR(1024), default=None, comment="错误信息")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())


class PmsProject(Base):
    """项目表"""
    __tablename__ = "pms_project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    archive_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pms_project_archive.id"), default=None, comment="项目档案ID")
    project_code: Mapped[str] = mapped_column(NVARCHAR(32), unique=True, nullable=False, comment="项目编号")
    project_name: Mapped[str] = mapped_column(NVARCHAR(128), nullable=False, comment="项目名称")
    dept_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_dept.id"), nullable=False, comment="所属部门ID")
    pm_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="项目经理ID")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1进行中 2已完结 3暂停")
    start_date: Mapped[datetime.date | None] = mapped_column(DateTime, default=None, comment="开始日期")
    end_date: Mapped[datetime.date | None] = mapped_column(DateTime, default=None, comment="结束日期")
    budget: Mapped[float | None] = mapped_column(DECIMAL(12, 2), default=None, comment="预算(万元)")
    description: Mapped[str | None] = mapped_column(NVARCHAR(2048), default=None, comment="项目描述")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_project_dept", "dept_id"), Index("idx_project_pm", "pm_id"))


class PmsTask(Base):
    """项目任务/进度表"""
    __tablename__ = "pms_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("pms_project.id"), nullable=False, comment="所属项目ID")
    task_name: Mapped[str] = mapped_column(NVARCHAR(256), nullable=False, comment="任务名称")
    assignee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), default=None, comment="负责人ID")
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="进度百分比 0-100")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1未开始 2进行中 3已完成")
    start_date: Mapped[datetime.date | None] = mapped_column(DateTime, default=None, comment="开始日期")
    due_date: Mapped[datetime.date | None] = mapped_column(DateTime, default=None, comment="截止日期")
    parent_id: Mapped[int] = mapped_column(Integer, default=0, comment="父任务ID，0为顶级")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_task_project", "project_id"), Index("idx_task_assignee", "assignee_id"))


class PmsProgressLog(Base):
    """进度变更记录表"""
    __tablename__ = "pms_progress_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("pms_task.id"), nullable=False, comment="任务ID")
    old_progress: Mapped[int] = mapped_column(Integer, comment="旧进度")
    new_progress: Mapped[int] = mapped_column(Integer, comment="新进度")
    operator_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="操作人ID")
    remark: Mapped[str | None] = mapped_column(NVARCHAR(256), default=None, comment="备注")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
