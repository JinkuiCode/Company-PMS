from tempfile import TemporaryDirectory
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter, Depends, Query, Request, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.authorization import require_permission
from app.services import feedback as service, feedback_attachments as files, feedback_mail as mail
from app.schemas.feedback import FeedbackCreate, FeedbackHandle, FeedbackSupplement
from app.models.feedback import FeedbackFollowup
from app.services.report_workbook import ReportWorkbook
from app.services.operation_log import record_operation_log

router = APIRouter(prefix='/api/feedback', tags=['问题提报'])


@router.get('')
def list_reports(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
                 filters: str | None = Query(None, max_length=65536), sort: str | None = Query(None, max_length=8192),
                 mine: bool = False, status_id: int | None = Query(None, ge=0, le=6),
                 db: Session = Depends(get_db), context=Depends(require_permission('feedback:view'))):
    return service.list_reports(db, context, page=page, page_size=page_size, filters=filters, sort=sort, mine=mine, status_id=status_id)


@router.get('/statistics')
def statistics(mine: bool = False, db: Session = Depends(get_db), context=Depends(require_permission('feedback:view'))):
    return service.statistics(db, context, mine)


@router.get('/export')
def export(request: Request, filters: str | None = Query(None, max_length=65536), mine: bool = False,
           status_id: int | None = Query(None, ge=0, le=6), db: Session = Depends(get_db),
           context=Depends(require_permission('feedback:export'))):
    query = service.filtered_query(db, context, filters, mine=mine, status_id=status_id)
    headers = [('report_no', '提报编号'), ('title', '标题'), ('type_id', '类型'), ('module_id', '涉及模块'),
               ('category_name', '具体类别'), ('impact_id', '影响程度'), ('status_id', '处理状态'),
               ('author_name', '提报人'), ('handler_name', '处理人'), ('created_at', '提报时间'),
               ('description', '详细说明'), ('steps', '复现步骤'), ('expected_result', '期望结果'), ('opinion', '最新处理意见'), ('outcome_id','处理结论'), ('cause_id','处理归因')]
    directory = TemporaryDirectory(prefix='pms-feedback-export-')
    path = Path(directory.name) / 'feedback.xlsx'
    labels = {key: service.enum_labels(db, code) for key, code in service.ENUM_FIELDS.items()}
    labels.update({key:service.enum_labels(db, code) for key, code in [('outcome_id','feedback_outcome'), ('cause_id','feedback_cause')]})
    count = 0
    try:
        with ReportWorkbook(path) as writer:
            main = writer.sheet('问题提报', headers)
            detail = writer.sheet('跟进记录', [(key, label) for key, label in [('report_no','提报编号'), ('action','动作'), ('actor','操作人'), ('description','说明'), ('status','状态'), ('outcome','处理结论'), ('cause','处理归因'), ('created_at','时间')]])
            for row in query.yield_per(500):
                data = service.output(db, row)
                for key, mapping in labels.items():
                    data[key] = mapping.get(data[key], data[key])
                main.append(data)
                for event in db.query(FeedbackFollowup).filter_by(report_id=row.id).order_by(FeedbackFollowup.id):
                    detail.append(dict(report_no=row.report_no, action={'create':'提交','handle':'处理','supplement':'补充'}.get(event.action,event.action),
                        actor=db.get(service.SysUser, event.actor_id).real_name, description=event.description,
                        status=labels['status_id'].get(event.status_id,event.status_id), outcome=labels['outcome_id'].get(event.outcome_id,''), cause=labels['cause_id'].get(event.cause_id,''), created_at=service.business_time(event.created_at).replace(tzinfo=None)))
                count += 1
        record_operation_log(db, module='问题提报', action='export', entity_type='pms_feedback_report', operator_id=context['user_id'], request=request, summary=f'导出提报及跟进：{count}条')
        db.commit()
    except Exception:
        directory.cleanup()
        raise
    def chunks():
        try:
            with path.open('rb') as file:
                while body := file.read(65536):
                    yield body
        finally:
            directory.cleanup()
    return StreamingResponse(chunks(), background=BackgroundTask(directory.cleanup), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote('问题提报.xlsx'), 'Cache-Control': 'no-store'})


@router.post('')
def create(data: FeedbackCreate, request: Request, db: Session = Depends(get_db), context=Depends(require_permission('feedback:add'))):
    return service.create_report(db, context, data, request)


@router.get('/{report_id}')
def detail(report_id: int, db: Session = Depends(get_db), context=Depends(require_permission('feedback:view'))):
    return service.get_report(db, context, report_id)


@router.post('/{report_id}/handling')
def handle(report_id: int, data: FeedbackHandle, request: Request, db: Session = Depends(get_db), context=Depends(require_permission('feedback:handle'))):
    return service.handle_report(db, context, report_id, data, request)


@router.post('/{report_id}/supplements')
def supplement(report_id: int, data: FeedbackSupplement, request: Request, db: Session = Depends(get_db), context=Depends(require_permission('feedback:supplement'))):
    return service.supplement_report(db, context, report_id, data, request)


@router.post('/{report_id}/attachments')
async def attachment(report_id: int, request: Request, version: int = Form(..., ge=1), file: UploadFile = File(...), submission_id: str | None = Form(None, max_length=36), db: Session = Depends(get_db), context=Depends(require_permission('feedback:view'))):
    try:
        body = await file.read(files.MAX_SIZE + 1)
        return await run_in_threadpool(files.attach, db, context, report_id, version, file.filename, body, request, submission_id)
    finally:
        await file.close()


@router.get('/attachments/{attachment_id}/download')
def download(attachment_id: int, db: Session = Depends(get_db), context=Depends(require_permission('feedback:view'))):
    path, filename, mime = files.download(db, context, attachment_id)
    return FileResponse(path, filename=filename, media_type=mime, headers={'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff', 'Content-Security-Policy':"sandbox"})


@router.post('/notifications/{notice_id}/retry')
def retry(notice_id: int, request: Request, db: Session = Depends(get_db), context=Depends(require_permission('feedback:notification:retry'))):
    return mail.retry(db, context, notice_id, request)
