"""Serial namespace: formal archives, active drafts and valid pending changes.

No reservation cache: pending JSON is the durable reservation. Callers keep the
existing archive identity transaction lock until commit/rollback.
"""
import json
import re
from fastapi import HTTPException
from sqlalchemy import Integer, column, literal, or_, select, table, text, union_all, and_
from sqlalchemy.dialects.mssql import NVARCHAR
from app.models.form_draft import PmsFormDraft
from app.services.archive_code_unique import require_identity_lock

ARCHIVES = table('pms_project_archive', column('id'), column('serial_no_key', NVARCHAR(64)))
CHANGES = table('pms_archive_change', column('id'), column('archive_id'), column('active_archive_id'),
                column('status'), column('updates_json'))


def serial_key(value):
    if value is not None and not isinstance(value, str):
        raise _unavailable()
    return (value or '').strip().casefold()


def _unavailable():
    return HTTPException(503, {'code':'ARCHIVE_SERIAL_UNAVAILABLE','field_key':'serial_no',
        'message':'序列号占用暂时无法核对，请稍后重试或联系管理员；本次输入已保留'})


def serial_conflict():
    return HTTPException(409, {'code':'ARCHIVE_UNIQUE_CONFLICT','field_key':'serial_no',
        'message':'序列号已存在或已被草稿、待审批变更占用，请更换序列号'})


def read_serial_payload(encoded):
    try:
        payload = json.loads(encoded)
        if not isinstance(payload, dict): raise ValueError('object required')
        serial_key(payload.get('serial_no'))
        return payload
    except (ValueError, TypeError):
        raise _unavailable() from None


def _collation(connection):
    if connection.dialect.name == 'mssql':
        name = connection.execute(text('''SELECT collation_name FROM sys.columns
            WHERE object_id=OBJECT_ID(:table_name) AND name=:column_name'''),
            {'table_name':'pms_project_archive','column_name':'serial_no_key'}).scalar()
        if not name or not re.fullmatch(r'[A-Za-z0-9_]+', name): raise _unavailable()
        return name
    if connection.dialect.name == 'sqlite':
        ddl = connection.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:name"),
                                 {'name':'pms_project_archive'}).scalar()
        match = re.search(r'\bserial_no_key\b[^,]*', ddl or '', re.I)
        if not match: raise _unavailable()
        collate = re.search(r'\bCOLLATE\s+[\"`\[]?([A-Za-z0-9_]+)', match.group(), re.I)
        return collate.group(1) if collate else 'BINARY'
    raise _unavailable()


def ensure_serial_available(connection, value, *, exclude_archive_id=None, exclude_draft_id=None):
    """Never return record identity or contents from another user's scope."""
    require_identity_lock(connection)
    key = serial_key(value)
    if not key: return
    query = select(ARCHIVES.c.id).where(ARCHIVES.c.serial_no_key == key)
    if exclude_archive_id is not None: query = query.where(ARCHIVES.c.id != exclude_archive_id)
    if connection.execute(query.limit(1)).first(): raise serial_conflict()
    drafts = PmsFormDraft.__table__
    query = select(drafts.c.payload_json).where(drafts.c.resource=='archive-create',drafts.c.status=='active')
    if exclude_draft_id is not None: query = query.where(drafts.c.id != str(exclude_draft_id))
    keys = [serial_key(read_serial_payload(encoded).get('serial_no')) for encoded in connection.execute(query).scalars()]
    query = select(CHANGES.c.archive_id,CHANGES.c.active_archive_id,CHANGES.c.status,CHANGES.c.updates_json,
                   ARCHIVES.c.id.label('formal_id')).select_from(
        CHANGES.outerjoin(ARCHIVES,ARCHIVES.c.id==CHANGES.c.archive_id)).where(
        or_(CHANGES.c.status==2,CHANGES.c.active_archive_id.is_not(None)))
    for row in connection.execute(query):
        if row.status != 2 or row.active_archive_id != row.archive_id or row.formal_id is None:
            raise _unavailable()
        keys.append(serial_key(read_serial_payload(row.updates_json).get('serial_no')))
    keys = [candidate for candidate in keys if candidate]
    # Literal comparison uses the FORMAL COLUMN's collation, not database default.
    comparator = literal(key, type_=NVARCHAR(64)).collate(_collation(connection))
    for offset in range(0,len(keys),400):
        if connection.execute(select(literal(1)).where(comparator.in_(keys[offset:offset+400]))).first():
            raise serial_conflict()


def identity_batch_conflicts(connection, proposals):
    """Bounded same-transaction batch check; never one namespace scan per row."""
    require_identity_lock(connection)
    from app.services.archive_code_unique import ARCHIVES as CODES
    draft_keys = {'project_code': [], 'serial_no': []}
    drafts = PmsFormDraft.__table__
    for encoded in connection.execute(select(drafts.c.payload_json).where(
            drafts.c.resource=='archive-create',drafts.c.status=='active')).scalars():
        payload=read_serial_payload(encoded)
        for field in draft_keys:
            value=payload.get(field)
            if value is not None and not isinstance(value,str):raise _unavailable()
            if value and value.strip():draft_keys[field].append(value.strip().casefold())
    query=select(CHANGES.c.archive_id,CHANGES.c.active_archive_id,CHANGES.c.status,CHANGES.c.updates_json,
                 ARCHIVES.c.id.label('formal_id')).select_from(CHANGES.outerjoin(ARCHIVES,ARCHIVES.c.id==CHANGES.c.archive_id)).where(or_(CHANGES.c.status==2,CHANGES.c.active_archive_id.is_not(None)))
    for row in connection.execute(query):
        if row.status!=2 or row.active_archive_id!=row.archive_id or row.formal_id is None:raise _unavailable()
        key=serial_key(read_serial_payload(row.updates_json).get('serial_no'))
        if key:draft_keys['serial_no'].append(key)
    conflicts=set()
    for field,formal in [('project_code',CODES),('serial_no',ARCHIVES)]:
        rows=[(slot,serial_key(value.get(field)),value.get('archive_id')) for slot,value in enumerate(proposals) if value.get(field)]
        if not rows:continue
        collation=_collation(connection) if field=='serial_no' else None
        for offset in range(0,len(rows),150):
            c=union_all(*[select(literal(slot).label('slot'),literal(key,type_=NVARCHAR(64)).label('key'),literal(aid,type_=Integer()).label('archive_id')) for slot,key,aid in rows[offset:offset+150]]).subquery()
            comparison=getattr(formal.c,field+'_key')==c.c.key
            q=select(c.c.slot).select_from(c.join(formal,and_(comparison,or_(c.c.archive_id.is_(None),formal.c.id!=c.c.archive_id))))
            conflicts.update((slot,field) for slot in connection.execute(q).scalars())
            for start in range(0,len(draft_keys[field]),300):
                occupied=union_all(*[select(literal(key,type_=NVARCHAR(64)).label('key')) for key in draft_keys[field][start:start+300]]).subquery()
                key=c.c.key.collate(collation) if collation else c.c.key
                q=select(c.c.slot).select_from(c.join(occupied,key==occupied.c.key))
                conflicts.update((slot,field) for slot in connection.execute(q).scalars())
            # Compare across all bounded chunks, including width/accent-equivalent
            # candidates whose Python-normalized strings are different.
            if field=='serial_no':
                for other_offset in range(offset,len(rows),150):
                    other=union_all(*[select(literal(slot).label('slot'),literal(value,type_=NVARCHAR(64)).label('key')) for slot,value,_ in rows[other_offset:other_offset+150]]).subquery()
                    q=select(c.c.slot,other.c.slot).where(c.c.slot<other.c.slot,c.c.key.collate(collation)==other.c.key)
                    for left,right in connection.execute(q):conflicts.update({(left,field),(right,field)})
    return sorted(conflicts)
