"""Persistent, owner-scoped export jobs. ERP reads never use the upgrade identity."""
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from app.models.report_export import ReportExportJob
from app.services.authorization import enforce_permission, build_authorization_context
from app.services.erp_execution_lock import archive_execution_lock
from app.services.operation_log import record_operation_log

EXPORT_ROOT = Path(__file__).resolve().parents[3] / '.runtime' / 'report-exports'
TTL = timedelta(hours=24)


def check_permission(ctx, report):
    if report not in ('inventory', 'purchase'):
        raise HTTPException(422, '未知报表')
    enforce_permission(ctx, f'report:{report}:view')
    enforce_permission(ctx, f'report:{report}:export')


def fields_for(report):
    if report == 'inventory':
        from app.services.inventory_fields import report_fields
    else:
        from app.services.purchase_fields import report_fields
    return report_fields()


def scope_signature(db, ctx, report):
    from app.services.business_data_scope import has_all_business_data
    if has_all_business_data(ctx):
        scope = {'all_business_data': True}
    elif report == 'inventory':
        from app.api.inventory_reports import scoped_lines
        scope = sorted((r.id, r.organization_id) for r in scoped_lines(db, ctx))
    else:
        from app.api.purchase_reports import project_scope
        scope = sorted((r.project_code, r.organization_id) for r in project_scope(db, ctx))
    return hashlib.sha256(json.dumps(scope, ensure_ascii=True).encode()).hexdigest()


def create_job(db, ctx, report, parameters, columns, request=None):
    check_permission(ctx, report)
    from app.services.inventory_reader import InventoryQuery
    from app.services.purchase_reader import PurchaseQuery
    from pydantic import ValidationError
    try:
        query = (InventoryQuery if report == 'inventory' else PurchaseQuery).model_validate(parameters)
    except ValidationError:
        raise HTTPException(422, '导出筛选参数无效') from None
    allowed = {field['key'] for field in fields_for(report)}
    if not columns or len(columns) != len(set(columns)) or not set(columns) <= allowed:
        raise HTTPException(422, '导出字段无效，请刷新报表后重试')
    with archive_execution_lock(db, 'report-export-create') as acquired:
        if not acquired:
            raise HTTPException(429, '任务提交繁忙，请稍后重试')
        if db.query(ReportExportJob).filter(ReportExportJob.user_id == ctx['user_id'],
                ReportExportJob.status.in_(['queued', 'running'])).first():
            raise HTTPException(409, '已有导出任务执行中，请等待完成')
        job = ReportExportJob(id=uuid4().hex, user_id=ctx['user_id'], report=report,
            parameters=query.model_dump_json(), columns=json.dumps(columns),
            scope_hash=scope_signature(db, ctx, report), status='queued', processed=0)
        db.add(job)
        record_operation_log(db, module='报表导出', action='export', entity_type='report_export',
            operator_id=ctx['user_id'], request=request, summary='提交后台导出任务',
            after_data={'report': report, 'job_id': job.id, 'filters': query.model_dump(mode='json')}, commit=False)
        db.commit()
        return job


def get_job(db, ctx, job_id, *, download=False):
    job = db.get(ReportExportJob, job_id)
    if not job or job.user_id != ctx['user_id']:
        raise HTTPException(404, '导出任务不存在')
    check_permission(ctx, job.report)
    if download:
        if scope_signature(db, ctx, job.report) != job.scope_hash:
            raise HTTPException(403, '数据权限已变化，请重新导出')
        if job.status != 'success' or not job.finished_at or datetime.now()-job.finished_at > TTL:
            raise HTTPException(409, '文件尚未生成或已过期，请重新导出')
    return job


def job_file(job):
    # IDs are generated internally, never a path from a request.
    if len(job.id) != 32 or any(c not in '0123456789abcdef' for c in job.id):
        raise ValueError('Invalid export identifier')
    return EXPORT_ROOT / f'{job.id}.xlsx'


def public_job(job):
    return {key: getattr(job, key) for key in ('id', 'report', 'status', 'processed', 'message', 'created_at', 'finished_at')}


def validate_execution(db, job):
    db.expire_all()
    ctx = build_authorization_context(db, job.user_id)
    check_permission(ctx, job.report)
    if scope_signature(db, ctx, job.report) != job.scope_hash:
        raise HTTPException(403, '数据权限或项目归属已变化，请重新导出')
    return ctx


def run_next(db, stop):
    # Reuse the existing cross-process MSSQL/SQLite mutex with a separate resource name.
    with archive_execution_lock(db, 'report-export-worker') as acquired:
        if not acquired:
            return
        for stale in db.query(ReportExportJob).filter(ReportExportJob.status == 'running').all():
            stale.status = 'failed'
            stale.message = '服务重启中断导出，请重新提交'
            stale.finished_at = datetime.now()
            job_file(stale).unlink(missing_ok=True)
        for expired in db.query(ReportExportJob).filter(ReportExportJob.status == 'success',
                ReportExportJob.finished_at < datetime.now()-TTL).all():
            job_file(expired).unlink(missing_ok=True)
            expired.status = 'expired'
        db.commit()
        job = db.query(ReportExportJob).filter_by(status='queued').order_by(ReportExportJob.created_at, ReportExportJob.id).first()
        if not job:
            return
        job.status = 'running'
        db.commit()
        EXPORT_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = job_file(job)
        try:
            from app.services.report_export_data import write_report

            def checkpoint(processed):
                if stop.is_set():
                    raise RuntimeError('export interrupted')
                ctx = validate_execution(db, job)
                job.processed = processed
                db.commit()
                return ctx

            ctx = checkpoint(0)
            write_report(db, job, ctx, path, checkpoint)
            checkpoint(job.processed)
            path.chmod(0o600)
            job.status = 'success'
            job.message = '导出完成，文件保留24小时'
        except Exception as error:
            db.rollback()
            path.unlink(missing_ok=True)
            job.status = 'failed'
            job.message = (str(error.detail) if isinstance(error, HTTPException) else
                '导出失败或查询超时，未提供不完整文件；请重试，持续失败请联系管理员')[:512]
        job.finished_at = datetime.now()
        record_operation_log(db, module='报表导出', action='export', entity_type='report_export',
            operator_id=job.user_id, summary=job.message,
            after_data={'job_id': job.id, 'status': job.status, 'row_count': job.processed}, commit=False)
        db.commit()


def worker(stop, session_factory):
    import logging
    while not stop.is_set():
        try:
            with session_factory() as db:
                run_next(db, stop)
        except Exception:
            logging.getLogger(__name__).error('Report export worker cycle failed; retrying without exposing data-source details')
        stop.wait(3)
