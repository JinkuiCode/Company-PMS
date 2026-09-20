"""Transactional outbox. Never repeat an externally ambiguous write automatically."""
import json
import logging
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import case
from app.models.erp_task import ErpSyncTask
from app.models.project import PmsProjectArchive
from app.models.user import SysUser
from app.services.operation_log import record_operation_log
from app.services.erp_execution_lock import archive_execution_lock

MAX_ATTEMPTS = 3
STATUS_LABELS = {'queued': '等待同步', 'running': '同步中', 'success': '同步成功',
                 'failed': '同步失败', 'review': '待核查', 'superseded': '已被新版本替代'}


def event(task, status, message):
    task.status = status
    task.message = str(message)[:1024]
    history = json.loads(task.history or '[]')
    history.append({'time': datetime.now().isoformat(), 'attempt': task.attempts,
                    'status': status, 'message': task.message})
    task.history = json.dumps(history, ensure_ascii=False)


def enqueue(db, archive, operator_id):
    # Called inside the archive write transaction, after locking/flushing the row.
    older = db.query(ErpSyncTask).filter(ErpSyncTask.archive_id == archive.id,
                                        ErpSyncTask.status.in_(['queued', 'failed'])).all()
    for task in older:
        event(task, 'superseded', '已由最新保存版本替代')
    task = ErpSyncTask(archive_id=archive.id, project_code=archive.project_code,
                       project_name=archive.project_name, operator_id=operator_id,
                       status='queued', attempts=0, history='[]')
    archive.erp_sync_status = 'queued'
    archive.erp_error_msg = None
    db.add(task)
    db.flush()
    event(task, 'queued', '保存成功，等待后台同步')
    return task


def run_once(db):
    # Calls have bounded HTTP timeouts. A lost worker is not presumed to have failed remotely.
    stale = db.query(ErpSyncTask).filter(ErpSyncTask.status == 'running',
        ErpSyncTask.started_at < datetime.now() - timedelta(minutes=30)).all()
    for task in stale:
        with archive_execution_lock(db, task.archive_id) as acquired:
            if not acquired:
                continue
            from app.services.project_archive_lifecycle import claim_archive_lifecycle_rows
            rows = claim_archive_lifecycle_rows(db.query(PmsProjectArchive), [task.archive_id])
            db.refresh(task)
            if task.status != 'running':
                db.rollback()
                continue
            newest = db.query(ErpSyncTask.id).filter(ErpSyncTask.archive_id == task.archive_id).order_by(ErpSyncTask.id.desc()).first()
            if newest.id != task.id:
                event(task, 'superseded', '执行进程已结束，已有更新版本，保留旧任务记录')
            else:
                event(task, 'review', '执行中断或超时，需核查金蝶结果')
                if rows:
                    rows[0].erp_sync_status = 'review'
            db.commit()
    candidate = db.query(ErpSyncTask.id, ErpSyncTask.archive_id).filter(ErpSyncTask.status == 'queued',
        ErpSyncTask.next_attempt_at <= datetime.now()).order_by(ErpSyncTask.id).first()
    if not candidate:
        return False
    with archive_execution_lock(db, candidate.archive_id) as acquired:
        if not acquired:
            return False
        return _run_claimed(db, candidate)


def _run_claimed(db, candidate):
    from app.services import kingdee
    claimed = db.query(ErpSyncTask).filter(ErpSyncTask.id == candidate.id,
        ErpSyncTask.status == 'queued').update({'status': 'running', 'started_at': datetime.now()}, synchronize_session=False)
    db.commit()
    if not claimed:
        return True
    task = db.get(ErpSyncTask, candidate.id, populate_existing=True)
    archive = db.get(PmsProjectArchive, task.archive_id, populate_existing=True)
    if not archive or not archive.is_enabled:
        event(task, 'failed', '档案不存在或已禁用，未发送金蝶请求')
        task.finished_at = datetime.now()
        if archive:
            latest_id = db.query(ErpSyncTask.id).filter(ErpSyncTask.archive_id == archive.id).order_by(ErpSyncTask.id.desc()).first()
            if latest_id.id == task.id:
                archive.erp_sync_status = 'failed'
                archive.erp_error_msg = task.message
        db.commit()
        return True
    latest = db.query(ErpSyncTask.id).filter(ErpSyncTask.archive_id == task.archive_id).order_by(ErpSyncTask.id.desc()).first()
    if latest.id != task.id:
        event(task, 'superseded', '已由最新保存版本替代')
        db.commit()
        return True
    task.attempts += 1
    event(task, 'running', '开始执行金蝶登录、保存及提交审核')
    db.commit()
    try:
        result = kingdee.sync_project_archive_to_erp(db, task.archive_id, user_id=task.operator_id, queue_task_id=task.id)
    except HTTPException as exc:
        db.rollback()
        if isinstance(exc.detail, dict) and exc.detail.get('code') == 'ERP_TASK_SUPERSEDED':
            task = db.get(ErpSyncTask, candidate.id, populate_existing=True)
            event(task, 'superseded', '已由最新保存版本替代，未发送外部请求')
            db.commit()
            return True
        result = {'success': False, 'message': '同步前校验失败，请检查档案状态或必填信息'}
        if exc.status_code == 409:
            result['message'] = '档案被其他操作占用，请先核查已有执行结果'
    except Exception:
        db.rollback()
        # Do not expose raw driver errors or retry an unknown external outcome.
        result = {'success': False, 'message': '后台执行异常，需核查金蝶结果'}
        result['ambiguous'] = True
    task = db.get(ErpSyncTask, candidate.id, populate_existing=True)
    archive = db.get(PmsProjectArchive, task.archive_id, populate_existing=True)
    ambiguous = result.get('ambiguous') or (archive and archive.erp_sync_status == 'pending')
    status = 'success' if result['success'] else 'review' if ambiguous else 'failed'
    if status == 'failed' and result.get('retryable') and task.attempts < MAX_ATTEMPTS:
        status = 'queued'
        task.next_attempt_at = datetime.now() + timedelta(seconds=60 * task.attempts)
    event(task, status, result.get('message', '执行结束'))
    task.finished_at = datetime.now()
    newest = db.query(ErpSyncTask.id).filter(ErpSyncTask.archive_id == task.archive_id).order_by(ErpSyncTask.id.desc()).first()
    if archive and newest.id == task.id:
        archive.erp_sync_status = status
        archive.erp_error_msg = None if status == 'success' else task.message
    db.commit()
    return True


def retry(db, task_id, user_id, request=None):
    from app.services.project_archive_lifecycle import claim_archive_lifecycle_rows
    task = db.get(ErpSyncTask, task_id)
    if not task:
        raise HTTPException(404, '同步任务不存在')
    rows = claim_archive_lifecycle_rows(db.query(PmsProjectArchive), [task.archive_id])
    if not rows:
        raise HTTPException(404, '档案不存在')
    archive = rows[0]
    db.refresh(task)
    if task.status != 'failed' or archive.erp_sync_status in ('pending', 'review'):
        raise HTTPException(409, '仅允许重试已确认失败的任务；待核查任务请先核查')
    latest = db.query(ErpSyncTask.id).filter(ErpSyncTask.archive_id == archive.id).order_by(ErpSyncTask.id.desc()).first()
    if latest.id != task.id:
        raise HTTPException(409, '已有更新版本，请处理最新任务')
    if not archive.is_enabled:
        raise HTTPException(409, '禁用档案不能同步')
    new_task = enqueue(db, archive, task.operator_id)
    record_operation_log(db, module='同步管理', action='retry', entity_type='pms_project_archive',
        entity_id=archive.id, entity_name=archive.project_name, operator_id=user_id, request=request,
        summary='管理员重试档案同步', after_data={'task_id': new_task.id, 'previous_task_id': task_id})
    db.commit()
    return {'id': new_task.id}


def inspect_result(db, task_id, user_id, request=None, *, external_request_finished=False):
    task = db.get(ErpSyncTask, task_id)
    if not task:
        raise HTTPException(404, '同步任务不存在')
    with archive_execution_lock(db, task.archive_id) as acquired:
        if not acquired:
            raise HTTPException(409, '原执行进程仍在运行，暂不能核查或重试')
        return _inspect_result(db, task_id, user_id, request, external_request_finished)


def _inspect_result(db, task_id, user_id, request, external_request_finished):
    from app.services.kingdee import KingdeeClient
    task = db.get(ErpSyncTask, task_id)
    if not task:
        raise HTTPException(404, '同步任务不存在')
    if task.status != 'review':
        raise HTTPException(409, '仅待核查任务可执行回查')
    client = KingdeeClient()
    try:
        if not client.login():
            raise HTTPException(409, '金蝶登录失败，未改变任务状态')
        row = client.query_assistant_data('BOS_ASSISTANTDATA_DETAIL', 'xsxm', task.project_code, include_status=True)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(409, '回查失败或存在重复编码，仍需人工核查') from None
    finally:
        client.close()
    from app.services.project_archive_lifecycle import claim_archive_lifecycle_rows
    rows = claim_archive_lifecycle_rows(db.query(PmsProjectArchive), [task.archive_id])
    if not rows:
        raise HTTPException(404, '档案不存在')
    archive = rows[0]
    db.refresh(task)
    newest = db.query(ErpSyncTask.id).filter(ErpSyncTask.archive_id == task.archive_id).order_by(ErpSyncTask.id.desc()).first()
    if task.status != 'review' or newest.id != task.id:
        raise HTTPException(409, '任务已发生变化，请刷新后处理最新任务')
    if row:
        archive.erp_synced = 1
    matched = row and row.get('FNumber') == task.project_code and row.get('FDataValue') == task.project_code and row.get('FDescription') == task.project_name and row.get('FDocumentStatus') == 'C'
    if matched:
        event(task, 'success', '回查确认金蝶资料与保存版本一致且已审核')
        archive.erp_synced = 1
        archive.erp_sync_time = datetime.now()
        archive.erp_sync_by = task.operator_id
        archive.erp_sync_status = 'success'
        archive.erp_error_msg = None
    elif external_request_finished:
        event(task, 'failed', '管理员确认金蝶端原请求已结束，回查未达到目标状态，可在排除异常后重试')
        archive.erp_sync_status = 'failed'
        archive.erp_error_msg = task.message
    else:
        event(task, 'review', '回查未达到目标状态，无法确认外部请求已终结；保持待核查，请管理员核实金蝶执行情况')
        archive.erp_sync_status = 'review'
        archive.erp_error_msg = task.message
    record_operation_log(db, module='同步管理', action='verify', entity_type='pms_project_archive',
        entity_id=archive.id, entity_name=archive.project_name, operator_id=user_id, request=request,
        summary='管理员回查金蝶同步结果', after_data={'task_id': task.id, 'status': task.status,
            'external_request_finished_confirmed': external_request_finished})
    db.commit()
    return {'status': task.status, 'message': task.message}


def list_tasks(db, *, page=1, page_size=50, keyword='', status='', operator='', start=None, end=None, archive_id=None, scope_context=None):
    query = db.query(ErpSyncTask, SysUser.real_name, SysUser.username).outerjoin(SysUser, SysUser.id == ErpSyncTask.operator_id)
    if scope_context is not None:
        from app.services.project import get_scoped_archive_query
        query = query.filter(ErpSyncTask.archive_id.in_(get_scoped_archive_query(db, scope_context).with_entities(PmsProjectArchive.id)))
    if keyword:
        query = query.filter(ErpSyncTask.project_code.contains(keyword, autoescape=True) | ErpSyncTask.project_name.contains(keyword, autoescape=True))
    if status:
        query = query.filter(ErpSyncTask.status == status)
    if operator:
        query = query.filter(SysUser.real_name.contains(operator, autoescape=True) | SysUser.username.contains(operator, autoescape=True))
    if start:
        query = query.filter(ErpSyncTask.created_at >= start)
    if end:
        query = query.filter(ErpSyncTask.created_at <= end)
    if archive_id is not None:
        query = query.filter(ErpSyncTask.archive_id == archive_id)
    total = query.count()
    rows = query.order_by(case((ErpSyncTask.status.in_(['failed', 'review']), 0), else_=1), ErpSyncTask.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {'total': total, 'items': [dict(id=t.id, archive_id=t.archive_id, project_code=t.project_code,
        project_name=t.project_name, status=t.status, status_label=STATUS_LABELS[t.status], attempts=t.attempts,
        message=t.message, history=json.loads(t.history or '[]'), operator_name=name or code or '-',
        created_at=t.created_at, started_at=t.started_at, finished_at=t.finished_at) for t, name, code in rows]}


def worker(stop, session_factory):
    logger = logging.getLogger(__name__)
    while not stop.is_set():
        try:
            with session_factory() as db:
                worked = run_once(db)
        except Exception:
            logger.error('ERP queue iteration failed; persisted task will require recovery')
            worked = False
        stop.wait(1 if worked else 5)
