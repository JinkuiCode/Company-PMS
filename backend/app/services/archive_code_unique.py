"""One transaction-scoped code namespace for archives and active create drafts."""
import json

from fastapi import HTTPException
from sqlalchemy import column, literal, select, table, text
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.exc import OperationalError

from app.models.form_draft import PmsFormDraft

# A lightweight Core projection avoids a circular import from the archive mapper.
ARCHIVES = table('pms_project_archive', column('id'), column('project_code_key', NVARCHAR(32)))
# Backward-compatible resource shared by all archive identity mutations.
LOCK_NAME = 'pms:archive-create:project-code'
_HELD = 'pms_archive_identity_transaction'


def _busy():
    return HTTPException(409, {'code':'ARCHIVE_CODE_BUSY', 'field_key':'project_code',
        'message':'项目编号正在保存，请稍后重试；本次输入已保留'})


def _identity_busy(field_key):
    if field_key != 'serial_no': return _busy()
    return HTTPException(409, {'code':'ARCHIVE_SERIAL_BUSY','field_key':'serial_no',
        'message':'序列号正在保存，请稍后重试；本次输入已保留'})


def identity_lock_held(connection):
    transaction = connection.get_transaction()
    return bool(transaction is not None and transaction.is_active
                and connection.info.get(_HELD) is transaction)


def require_identity_lock(connection):
    if not identity_lock_held(connection):
        raise HTTPException(503, {'code':'ARCHIVE_IDENTITY_LOCK_REQUIRED',
            'message':'档案保存入口暂不可用，请联系管理员；本次输入已保留'})


def lock_codes(connection, *, field_key='project_code'):
    """Keep the lock through the caller's commit/rollback, not merely this check."""
    if identity_lock_held(connection): return
    if connection.dialect.name == 'mssql':
        result = connection.execute(text('''
            DECLARE @result int;
            EXEC @result = sys.sp_getapplock @Resource=:name,
                @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=1000;
            SELECT @result;
        '''), {'name':LOCK_NAME}).scalar()
        if result is None or result < 0:
            raise _identity_busy(field_key)
    elif connection.dialect.name == 'sqlite':
        # SQLAlchemy autobegin may precede sqlite3's actual transaction. Start a
        # write transaction before reading either namespace; an existing write
        # transaction already owns SQLite's cross-process writer lock.
        try:
            if not connection.connection.driver_connection.in_transaction:
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            else:
                # A driver transaction may only be a deferred reader. Acquire
                # the writer lock without changing a row before namespace reads.
                connection.exec_driver_sql('UPDATE pms_project_archive SET id=id WHERE 0')
        except OperationalError as exc:
            if 'locked' in str(exc.orig).lower() or 'busy' in str(exc.orig).lower():
                raise _identity_busy(field_key) from None
            raise
    else:
        raise RuntimeError('Unsupported project-code database')
    connection.info[_HELD] = connection.get_transaction()


def ensure_code_available(connection, code, *, exclude_draft_id=None, exclude_archive_id=None, check_archives=True):
    """Global existence check only; never return another record's private data."""
    lock_codes(connection)
    key = (code or '').strip().casefold()
    if not key:
        raise HTTPException(422, {'code':'ARCHIVE_FIELD_REQUIRED','field_key':'project_code','message':'项目编号不能为空'})
    existing = select(ARCHIVES.c.id).where(ARCHIVES.c.project_code_key == key)
    if exclude_archive_id is not None:
        existing = existing.where(ARCHIVES.c.id != exclude_archive_id)
    # Formal-to-formal writes retain their existing database unique constraint
    # and IntegrityError contract (including initial-import handling).
    conflict = check_archives and connection.execute(existing.limit(1)).first() is not None
    if not conflict:
        drafts = PmsFormDraft.__table__
        query = select(drafts.c.payload_json).where(drafts.c.resource == 'archive-create', drafts.c.status == 'active')
        if exclude_draft_id is not None:
            query = query.where(drafts.c.id != str(exclude_draft_id))
        keys = []
        for encoded in connection.execute(query).scalars():
            try:
                value = json.loads(encoded).get('project_code')
                if value is not None and not isinstance(value, str):
                    raise ValueError('Invalid draft identity')
                if value and value.strip():
                    keys.append(value.strip().casefold())
            except (ValueError, AttributeError, TypeError):
                raise HTTPException(503, '草稿编号暂时无法核对，请稍后重试或联系管理员') from None
        # Database comparison retains the archive unique index's collation
        # semantics, including SQL Server width/accent rules. Bound values only.
        for offset in range(0, len(keys), 400):
            if connection.execute(select(literal(1)).where(literal(key).in_(keys[offset:offset+400]))).first():
                conflict = True
                break
    if conflict:
        raise HTTPException(409, {'code':'ARCHIVE_UNIQUE_CONFLICT','field_key':'project_code',
            'message':'项目编号已存在，请更换编号'})
