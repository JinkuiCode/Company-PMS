"""Import provenance is separate from editable business fields."""
import datetime
from sqlalchemy import Integer, DateTime, ForeignKey, func, JSON, text
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class ArchiveImportBatch(Base):
    __tablename__="pms_archive_import_batch"
    id: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    content_hash: Mapped[str]=mapped_column(NVARCHAR(64),nullable=False,unique=True)
    source_file_hash: Mapped[str | None]=mapped_column(NVARCHAR(64),nullable=True)
    status: Mapped[str]=mapped_column(NVARCHAR(24),nullable=False,default="applied")
    row_count: Mapped[int]=mapped_column(Integer,nullable=False)
    created_by: Mapped[int]=mapped_column(Integer,nullable=False)
    created_at: Mapped[datetime.datetime]=mapped_column(DateTime,server_default=func.now())
class ArchiveImportRow(Base):
    __tablename__="pms_archive_import_row"
    id: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    batch_id: Mapped[int]=mapped_column(Integer,ForeignKey("pms_archive_import_batch.id"),nullable=False,index=True)
    source_id: Mapped[str]=mapped_column(NVARCHAR(64),nullable=False,unique=True)
    source_sheet: Mapped[str]=mapped_column(NVARCHAR(128),nullable=False)
    source_row: Mapped[int]=mapped_column(Integer,nullable=False)
    archive_id: Mapped[int]=mapped_column(Integer,nullable=False,index=True)
    original_code: Mapped[str]=mapped_column(NVARCHAR(32),nullable=False)
    snapshot_hash: Mapped[str]=mapped_column(NVARCHAR(64),nullable=False)
    operation: Mapped[str]=mapped_column(NVARCHAR(16),nullable=False,default="created",server_default=text("'created'"),comment="导入动作: created新增/updated补充/unchanged保留")
    before_values: Mapped[dict | None]=mapped_column(JSON,nullable=True,comment="补充字段的导入前值，仅用于安全回退")
