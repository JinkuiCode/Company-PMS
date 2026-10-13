"""Private download-only files with scoped access and bounded type validation."""
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile, BadZipFile
from datetime import datetime
from sqlalchemy import update
from fastapi import HTTPException
from app.core.config import settings
from app.models.feedback import FeedbackReport, FeedbackAttachment, FeedbackFollowup
from app.services.feedback import require_report
from app.services.authorization import enforce_any_permission
from app.services.operation_log import record_operation_log, serialize_model

MAX_SIZE = 10 * 1024 * 1024


def storage_root():
    return Path(settings.FEEDBACK_ATTACHMENT_DIR).resolve()


def validate_file(filename, body):
    if not filename or len(filename) > 200 or any(char in filename for char in ('/', '\\', '\r', '\n', '\0')):
        raise HTTPException(422, '附件名称无效')
    if not body or len(body) > MAX_SIZE:
        raise HTTPException(422, '每个附件须为1字节至10MB')
    extension = Path(filename).suffix.lower()
    checks = {
        '.pdf': ('application/pdf', body.startswith(b'%PDF-')),
        '.png': ('image/png', len(body) >= 33 and body.startswith(b'\x89PNG\r\n\x1a\n') and body[12:16] == b'IHDR'),
        '.jpg': ('image/jpeg', body.startswith(b'\xff\xd8\xff') and body.endswith(b'\xff\xd9')),
        '.jpeg': ('image/jpeg', body.startswith(b'\xff\xd8\xff') and body.endswith(b'\xff\xd9')),
        '.gif': ('image/gif', len(body) >= 13 and body.startswith((b'GIF87a', b'GIF89a'))),
        '.webp': ('image/webp', len(body) >= 20 and body[:4] == b'RIFF' and body[8:12] == b'WEBP'),
        '.xls': ('application/vnd.ms-excel', body.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')),
        '.doc': ('application/msword', body.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')),
    }
    if extension in ('.xlsx', '.docx'):
        try:
            with ZipFile(BytesIO(body)) as archive:
                names = set(archive.namelist())
                valid = len(names) <= 2000 and sum(item.file_size for item in archive.infolist()) <= 50 * 1024 * 1024
                valid = valid and '[Content_Types].xml' in names and ('xl/workbook.xml' if extension == '.xlsx' else 'word/document.xml') in names
                valid = valid and not any(name.lower().endswith('vbaproject.bin') for name in names)
        except BadZipFile:
            valid = False
        checks[extension] = ('application/vnd.openxmlformats-officedocument.' + ('spreadsheetml.sheet' if extension == '.xlsx' else 'wordprocessingml.document'), valid)
    if extension not in checks or not checks[extension][1]:
        raise HTTPException(422, '只支持内容类型相符的图片、PDF、Excel和Word附件')
    return checks[extension][0]


def attach(db, context, report_id, version, filename, body, request=None, submission_id=None):
    row = require_report(db, context, report_id)
    if version != row.version:
        raise HTTPException(409, '提报已变化，请刷新后上传')
    initial_upload = (row.author_id == context['user_id'] and 'feedback:add' in context['permissions']
        and submission_id == row.submission_id and row.status_id == 1
        and (datetime.utcnow() - row.created_at).total_seconds() <= 1800
        and db.query(FeedbackFollowup).filter_by(report_id=row.id).count() == 1)
    if not initial_upload:
        enforce_any_permission(context, ('feedback:supplement', 'feedback:handle'))
    if row.author_id != context['user_id'] and 'feedback:handle' not in context['permissions']:
        raise HTTPException(403, '无权上传该提报附件')
    mime = validate_file(filename, body)
    path = None
    try:
        # Lock the parent before counting so concurrent uploads cannot exceed five.
        changed = db.execute(update(FeedbackReport).where(FeedbackReport.id == row.id, FeedbackReport.version == version).values(version=version + 1, updated_at=datetime.utcnow()), execution_options={'synchronize_session': False})
        if changed.rowcount != 1:
            raise HTTPException(409, '提报已变化，请刷新后上传')
        if db.query(FeedbackAttachment).filter_by(report_id=row.id).count() >= 5:
            raise HTTPException(422, '每张提报最多5个附件')
        name = uuid4().hex
        root = storage_root()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = root / name
        with path.open('xb') as file:
            file.write(body)
        path.chmod(0o600)
        item = FeedbackAttachment(report_id=row.id, uploader_id=context['user_id'], filename=filename, storage_name=name, content_type=mime, size=len(body))
        db.add(item)
        db.flush()
        record_operation_log(db, module='问题提报', action='create', entity_type='pms_feedback_attachment', entity_id=item.id, entity_name=filename, operator_id=context['user_id'], request=request, summary='上传提报附件', after_data=serialize_model(item, exclude={'storage_name'}))
        db.commit()
        return serialize_model(item, exclude={'storage_name'}) | {'version': version + 1}
    except Exception:
        db.rollback()
        if path is not None:
            path.unlink(missing_ok=True)
        raise


def download(db, context, attachment_id):
    item = db.get(FeedbackAttachment, attachment_id)
    if item is None:
        raise HTTPException(404, '附件不存在')
    require_report(db, context, item.report_id)
    path = storage_root() / item.storage_name
    if path.parent != storage_root() or not path.is_file() or path.is_symlink():
        raise HTTPException(404, '附件文件缺失，请联系管理员')
    return path, item.filename, item.content_type
