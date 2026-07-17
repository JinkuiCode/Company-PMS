import datetime

from sqlalchemy import Integer, DateTime, ForeignKey, func, DECIMAL, Index, event, text
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PmsProjectArchive(Base):
    """项目档案表"""
    __tablename__ = "pms_project_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(NVARCHAR(32), unique=True, nullable=False, comment="项目编号")
    project_code_key: Mapped[str] = mapped_column(NVARCHAR(32), nullable=False, comment="项目编号唯一键")
    project_name: Mapped[str] = mapped_column(NVARCHAR(128), nullable=False, comment="项目名称")
    project_name_key: Mapped[str] = mapped_column(NVARCHAR(128), nullable=False, comment="项目名称唯一键")
    customer: Mapped[str | None] = mapped_column(NVARCHAR(128), default=None, comment="客户")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1未启动 2进行中 3已完结 4暂停")
    is_enabled: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        comment="启用状态: 1启用 0禁用",
    )
    manager_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), default=None, comment="负责人ID")
    product_category: Mapped[int | None] = mapped_column(Integer, default=None, comment="产品类别枚举值")
    equipment_series: Mapped[int | None] = mapped_column(Integer, default=None, comment="设备系列枚举值")
    serial_no: Mapped[str | None] = mapped_column(NVARCHAR(64), default=None, comment="序列号")
    serial_no_key: Mapped[str | None] = mapped_column(NVARCHAR(64), default=None, comment="序列号唯一键")
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

    __table_args__ = (
        Index("idx_project_archive_enabled", "is_enabled"),
        Index("ux_pms_project_archive_project_code_key", "project_code_key", unique=True),
        Index("ux_pms_project_archive_project_name_key", "project_name_key", unique=True),
        Index(
            "ux_pms_project_archive_serial_no_key",
            "serial_no_key",
            unique=True,
            sqlite_where=text("serial_no_key IS NOT NULL"),
            mssql_where=text("serial_no_key IS NOT NULL"),
        ),
    )


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
    product_category: Mapped[int | None] = mapped_column(Integer, default=None, comment="产品类别枚举值")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1进行中 2已完结 3暂停")
    start_date: Mapped[datetime.date | None] = mapped_column(DateTime, default=None, comment="开始日期")
    end_date: Mapped[datetime.date | None] = mapped_column(DateTime, default=None, comment="结束日期")
    budget: Mapped[float | None] = mapped_column(DECIMAL(12, 2), default=None, comment="预算(万元)")
    design_progress: Mapped[int | None] = mapped_column(Integer, default=None, comment="设计进度 0-100")
    order_progress: Mapped[int | None] = mapped_column(Integer, default=None, comment="下单进度 0-100")
    kit_progress: Mapped[int | None] = mapped_column(Integer, default=None, comment="齐套进度 0-100")
    frame_progress: Mapped[int | None] = mapped_column(Integer, default=None, comment="框架进度 0-100")
    dryer_progress: Mapped[int | None] = mapped_column(Integer, default=None, comment="dryer 进度 0-100")
    assembly_progress: Mapped[int | None] = mapped_column(Integer, default=None, comment="组装进度 0-100")
    test_progress: Mapped[int | None] = mapped_column(Integer, default=None, comment="测试进度 0-100")
    description: Mapped[str | None] = mapped_column(NVARCHAR(2048), default=None, comment="项目描述")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_project_dept", "dept_id"), Index("idx_project_pm", "pm_id"))


def _clean_identity(value: str | None) -> str:
    return (value or "").strip()


@event.listens_for(PmsProjectArchive, "before_insert")
@event.listens_for(PmsProjectArchive, "before_update")
def _populate_archive_identity_keys(_mapper, _connection, target: PmsProjectArchive) -> None:
    target.project_code = _clean_identity(target.project_code)
    target.project_name = _clean_identity(target.project_name)
    target.serial_no = _clean_identity(target.serial_no) or None
    target.customer = _clean_identity(target.customer) or None
    target.project_code_key = target.project_code.casefold()
    target.project_name_key = target.project_name
    target.serial_no_key = target.serial_no.casefold() if target.serial_no else None


class PmsProjectSheetDetail(Base):
    """项目总表 1:1 明细数据。

    126 个字段由项目总表字段注册表统一定义。这里仅存放人工维护字段，
    引用字段和计算字段由服务层实时组装，避免项目主表持续膨胀。
    """
    __tablename__ = "pms_project_sheet_detail"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("pms_project.id"),
        unique=True,
        nullable=False,
        comment="项目ID",
    )
    detail_data: Mapped[str | None] = mapped_column(NVARCHAR(None), default="{}", comment="人工维护字段 JSON")
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), default=None, comment="创建人ID")
    updated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), default=None, comment="最后编辑人ID")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_project_sheet_detail_project", "project_id"),)


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
