from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.report_export import ReportExportJob
from app.services.authorization import get_current_user_context
from app.services.report_export_jobs import create_job, get_job, public_job, job_file, check_permission

router = APIRouter(prefix='/api/report-exports', tags=['报表导出'])


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    report: Literal['inventory', 'purchase']
    parameters: dict = Field(default_factory=dict)
    columns: list[str] = Field(min_length=1, max_length=100)


@router.post('', status_code=202)
def create(body: ExportRequest, request: Request, db: Session = Depends(get_db), ctx=Depends(get_current_user_context)):
    return public_job(create_job(db, ctx, body.report, body.parameters, body.columns, request))


@router.get('')
def listing(report: Literal['inventory', 'purchase'], db: Session = Depends(get_db), ctx=Depends(get_current_user_context)):
    check_permission(ctx, report)
    rows = db.query(ReportExportJob).filter_by(user_id=ctx['user_id'], report=report).order_by(ReportExportJob.created_at.desc()).limit(20).all()
    return [public_job(row) for row in rows]


@router.get('/{job_id}')
def status(job_id: str, db: Session = Depends(get_db), ctx=Depends(get_current_user_context)):
    return public_job(get_job(db, ctx, job_id))


@router.get('/{job_id}/download')
def download(job_id: str, db: Session = Depends(get_db), ctx=Depends(get_current_user_context)):
    job = get_job(db, ctx, job_id, download=True)
    path = job_file(job)
    if not path.is_file():
        raise HTTPException(410, '文件已清理，请重新导出')
    filename = ('即时库存' if job.report == 'inventory' else '采购进度') + '-' + job.created_at.strftime('%Y%m%d-%H%M%S') + '.xlsx'
    return FileResponse(path, filename=filename,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
