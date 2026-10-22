"""Archive governance using existing scope, lifecycle locks and transactional writes."""
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from app.models.archive_change import ArchiveChange
from app.models.project import PmsProjectArchive
from app.models.rbac import SysDept
from app.models.user import SysUser
from app.schemas.project import ArchiveUpdate
from app.services.authorization import enforce_permission
from app.services.operation_log import build_operation_log_diff_items, diff_data, record_operation_log, serialize_model


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f'Unsupported business value: {type(value).__name__}')


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=_json_value)


def archive_business_values(archive):
    return {key: getattr(archive, 'business_product_line_id' if key == 'product_line_id' else key)
            for key in ArchiveUpdate.model_fields if key != 'expected_version'}


def archive_business_version(archive):
    return hashlib.sha256(_dump({**archive_business_values(archive), 'is_enabled': archive.is_enabled}).encode()).hexdigest()


def _relation(db, archive, users=None, departments=None):
    owner = users.get(archive.manager_id) if users is not None else db.get(SysUser, archive.manager_id) if archive.manager_id else None
    dept = (departments.get(owner.dept_id) if departments is not None else db.get(SysDept, owner.dept_id)) if owner and owner.dept_id else None
    head = users.get(dept.leader_id) if users is not None and dept else db.get(SysUser, dept.leader_id) if dept and dept.leader_id else None
    if not owner or owner.status != 1 or not dept or dept.status != 1 or not head or head.status != 1:
        return None, None, None
    return owner, dept, head


def archive_edit_context(db, archive, scope, *, users=None, departments=None, pending=None):
    from app.services.archive_maintenance import maintenance_context
    owner, dept, head = _relation(db, archive, users, departments)
    actor = (scope or {}).get('user_id')
    has_action = 'project:archive:edit' in (scope or {}).get('permissions', [])
    related = bool(owner and actor in (owner.id, head.id))
    if pending is None:
        pending = db.query(ArchiveChange.id).filter(ArchiveChange.active_archive_id == archive.id).scalar()
    can_edit = has_action and related and archive.is_enabled == 1 and not pending
    reason = ('项目档案已禁用，仅供查看' if archive.is_enabled != 1 else '有变更申请待处理' if pending else '请先补齐有效项目负责人、所属部门及部门负责人' if not owner
              else '只有项目负责人或其部门负责人可以修改' if not related
              else '当前角色没有项目档案编辑权限' if not has_action else '')
    return dict(can_edit=bool(can_edit), change_mode=('direct' if actor == head.id else 'approval') if can_edit else 'readonly',
                change_version=archive_business_version(archive), approver_id=head.id if head else None,
                approver_name=f'{head.real_name or head.username}（{head.username}）' if head else '',
                pending_change_id=pending or None, edit_reason=reason,
                **maintenance_context(archive, scope, pending))


def archive_edit_contexts(db, archives, scope):
    owner_ids = {a.manager_id for a in archives if a.manager_id}
    users = {u.id:u for u in db.query(SysUser).filter(SysUser.id.in_(owner_ids)).all()} if owner_ids else {}
    dept_ids = {u.dept_id for u in users.values() if u.dept_id}
    departments = {d.id:d for d in db.query(SysDept).filter(SysDept.id.in_(dept_ids)).all()} if dept_ids else {}
    head_ids = {d.leader_id for d in departments.values() if d.leader_id}
    if head_ids:
        users.update({u.id:u for u in db.query(SysUser).filter(SysUser.id.in_(head_ids)).all()})
    ids = [a.id for a in archives]
    pending = {a:c for a,c in db.query(ArchiveChange.active_archive_id,ArchiveChange.id).filter(ArchiveChange.active_archive_id.in_(ids)).all()} if ids else {}
    return {a.id:archive_edit_context(db,a,scope,users=users,departments=departments,pending=pending.get(a.id,0)) for a in archives}


def _check_editor(db, archive, actor, scope):
    enforce_permission(scope or {}, 'project:archive:edit')
    if (scope or {}).get('user_id') != actor:
        raise HTTPException(403, '操作用户不匹配')
    user = db.get(SysUser, actor)
    if not user or user.status != 1:
        raise HTTPException(403, '操作用户已失效')
    owner, dept, head = _relation(db, archive)
    if not owner:
        raise HTTPException(422, detail={'code':'ARCHIVE_APPROVER_MISSING','message':'请先补齐有效项目负责人、所属部门及部门负责人'})
    if actor not in (owner.id, head.id):
        raise HTTPException(403, '只有项目负责人或其部门负责人可以修改')
    return owner, dept, head


def _check_version(archive, expected):
    if not expected or expected != archive_business_version(archive):
        raise HTTPException(409, detail={'code':'ARCHIVE_CHANGE_CONFLICT','message':'档案已变化，请刷新后重试，草稿不会覆盖新数据'})


def _ensure_no_active(db, archive_id):
    if db.query(ArchiveChange.id).filter(ArchiveChange.active_archive_id == archive_id).first():
        raise HTTPException(409, detail={'code':'ARCHIVE_CHANGE_PENDING','message':'该档案已有待处理变更申请'})


def _locked_archive(db, archive_id, scope, *, reject_pending=True, identity=True):
    from app.services.project import _claim_enabled_archive_for_write
    if identity:
        from app.services.archive_code_unique import lock_codes
        lock_codes(db.connection(), field_key='serial_no')
    return _claim_enabled_archive_for_write(db,archive_id,scope,action_label='修改档案',reject_pending=reject_pending)


def _preview_locked(db, archive, data, actor, scope):
    from app.services.project import apply_archive_updates
    _,dept,head = _check_editor(db,archive,actor,scope)
    _check_version(archive,data.expected_version)
    _ensure_no_active(db,archive.id)
    updates = apply_archive_updates(db,archive.id,data.updates,actor,scope_context=scope,archive=archive,dry_run=True)
    current = archive_business_values(archive)
    updates = {key:value for key,value in updates.items() if current.get(key) != value}
    if not updates:
        raise HTTPException(422, '尚未修改业务字段')
    diff = build_operation_log_diff_items(diff_data(current,{**current,**updates}),entity_type='pms_project_archive',entity_id=str(archive.id),db=db)
    return dict(updates=updates,differences=diff,approver_id=head.id,department_id=dept.id,
                approver_name=f'{head.real_name or head.username}（{head.username}）',
                mode='direct' if actor == head.id else 'approval',expected_version=data.expected_version)


def preview_archive_change(db, archive_id, data, actor, *, scope_context):
    try:
        return _preview_locked(db,_locked_archive(db,archive_id,scope_context),data,actor,scope_context)
    finally:
        db.rollback()


def direct_archive_update(db,archive_id,data,actor,*,request=None,scope_context=None):
    from app.services.project import apply_archive_updates
    try:
        from app.services.project import lock_archive_identity_update
        lock_archive_identity_update(db, data)
        archive = _locked_archive(db,archive_id,scope_context,identity=False)
        _,_,head = _check_editor(db,archive,actor,scope_context)
        _check_version(archive,data.expected_version)
        _ensure_no_active(db,archive.id)
        if actor != head.id:
            raise HTTPException(409,detail={'code':'ARCHIVE_APPROVAL_REQUIRED','message':'项目负责人修改需提交变更审批'})
        result = apply_archive_updates(db,archive_id,data,actor,request=request,scope_context=scope_context,archive=archive,commit=False)
        db.commit()
        return {**result,'mode':'direct'}
    except Exception:
        db.rollback();raise


def _change_result(row):
    return dict(id=row.id,status=row.status,version=row.version,approver_id=row.approver_id,
                opinion=row.opinion,decided_at=row.decided_at,msg='变更状态已更新')


def submit_archive_change(db,archive_id,data,actor,*,request=None,scope_context=None):
    try:
        archive = _locked_archive(db,archive_id,scope_context,reject_pending=False)
        enforce_permission(scope_context or {},'project:archive:edit')
        user=db.get(SysUser,actor)
        if not user or user.status!=1 or (scope_context or {}).get('user_id')!=actor:raise HTTPException(403,'操作用户已失效或不匹配')
        request_hash=hashlib.sha256(_dump({'archive_id':archive_id,'updates':data.updates.model_dump(exclude_unset=True,exclude={'expected_version'}),
            'expected_version':data.expected_version,'reason':data.reason}).encode()).hexdigest()
        existing = db.query(ArchiveChange).filter_by(author_id=actor,submission_id=str(data.submission_id)).first()
        if existing:
            if existing.archive_id != archive_id or existing.request_hash!=request_hash:
                raise HTTPException(409,'提交标识已用于另一项变更')
            db.rollback()
            return _change_result(existing)
        if archive.erp_sync_status in ('pending','review'):
            from app.services.project import _archive_operation_pending_conflict
            raise _archive_operation_pending_conflict()
        proposal = _preview_locked(db,archive,data,actor,scope_context)
        if proposal['mode'] != 'approval':
            raise HTTPException(409,'部门负责人修改应直接保存生效')
        row=ArchiveChange(archive_id=archive_id,active_archive_id=archive_id,submission_id=str(data.submission_id),request_hash=request_hash,author_id=actor,
            approver_id=proposal['approver_id'],department_id=proposal['department_id'],base_version=data.expected_version,
            updates_json=_dump(proposal['updates']),differences_json=_dump(proposal['differences']),reason=data.reason,status=2)
        db.add(row);db.flush()
        record_operation_log(db,module='项目档案变更',action='submit',entity_type='pms_archive_change',entity_id=row.id,
            entity_name=archive.project_code,operator_id=actor,request=request,summary=f'提交档案变更：{archive.project_code}',after_data=serialize_model(row))
        db.commit();return _change_result(row)
    except IntegrityError as exc:
        db.rollback();raise HTTPException(409,'该档案已有活动申请或重复提交，请刷新') from exc
    except Exception:
        db.rollback();raise


def _request_and_archive(db,change_id,scope):
    from app.services.project import ensure_archive_access
    row=db.get(ArchiveChange,change_id)
    if not row:raise HTTPException(404,'变更申请不存在或无权访问')
    archive=ensure_archive_access(db,row.archive_id,scope)
    return row,archive


def _lock_request(db,row,scope):
    # All mutation paths lock archive first, then request, in the same order.
    archive=_locked_archive(db,row.archive_id,scope,reject_pending=False)
    row=db.query(ArchiveChange).filter(ArchiveChange.id==row.id).with_hint(ArchiveChange,'WITH (UPDLOCK, ROWLOCK, HOLDLOCK)',dialect_name='mssql').with_for_update().populate_existing().one()
    return row,archive


def decide_archive_change(db,change_id,data,actor,*,request=None,scope_context=None):
    from app.services.project import apply_archive_updates
    try:
        row,archive=_request_and_archive(db,change_id,scope_context)
        row,archive=_lock_request(db,row,scope_context)
        target=3 if data.decision=='approve' else 4
        if row.status==target:
            enforce_permission(scope_context or {},'project:archive:edit')
            department=db.get(SysDept,row.department_id)
            user=db.get(SysUser,actor)
            if not user or user.status!=1 or (scope_context or {}).get('user_id')!=actor or actor!=row.approver_id or not department or department.status!=1 or department.leader_id!=actor:
                raise HTTPException(403,'当前用户已不是此申请的有效审批人')
            db.rollback();return _change_result(row)
        _,dept,head=_check_editor(db,archive,actor,scope_context)
        if actor!=row.approver_id or actor!=head.id or dept.id!=row.department_id:
            raise HTTPException(403,'当前用户已不是此申请的有效审批人')
        if row.status!=2 or row.version!=data.expected_version:
            raise HTTPException(409,'申请已处理或版本已变化，请刷新')
        if target==4 and not data.opinion.strip():raise HTTPException(422,'请填写退回原因')
        before=serialize_model(row)
        if target==3:
            if archive.erp_sync_status in ('pending','review'):
                from app.services.project import _archive_operation_pending_conflict
                raise _archive_operation_pending_conflict()
            _check_version(archive,row.base_version)
            from app.services.archive_serial_unique import read_serial_payload
            updates = read_serial_payload(row.updates_json)
            # End only this reservation inside the SAME locked transaction. Any
            # validation/flush/log failure rolls it back along with formal writes.
            row.status=target;row.active_archive_id=None;db.flush()
            apply_archive_updates(db,archive.id,ArchiveUpdate(**updates),actor,request=request,scope_context=scope_context,archive=archive,commit=False)
        row.status=target;row.active_archive_id=None;row.version+=1;row.opinion=data.opinion.strip();row.decided_at=datetime.now()
        record_operation_log(db,module='项目档案变更',action='approve' if target==3 else 'reject',entity_type='pms_archive_change',entity_id=row.id,
            entity_name=archive.project_code,operator_id=actor,request=request,summary=f'{"通过" if target==3 else "退回"}档案变更：{archive.project_code}',before_data=before,after_data=serialize_model(row))
        db.commit();return _change_result(row)
    except Exception:db.rollback();raise


def withdraw_archive_change(db,change_id,data,actor,*,request=None,scope_context=None):
    try:
        enforce_permission(scope_context or {},'project:archive:edit')
        row,archive=_request_and_archive(db,change_id,scope_context)
        row,archive=_lock_request(db,row,scope_context)
        if row.author_id!=actor:raise HTTPException(403,'只有原提交人可以撤回')
        if row.status==5:db.rollback();return _change_result(row)
        if row.status!=2 or row.version!=data.expected_version:raise HTTPException(409,'申请已处理或版本已变化，请刷新')
        before=serialize_model(row);row.status=5;row.active_archive_id=None;row.version+=1;row.decided_at=datetime.now()
        record_operation_log(db,module='项目档案变更',action='withdraw',entity_type='pms_archive_change',entity_id=row.id,
            entity_name=archive.project_code,operator_id=actor,request=request,summary=f'撤回档案变更：{archive.project_code}',before_data=before,after_data=serialize_model(row))
        db.commit();return _change_result(row)
    except Exception:db.rollback();raise


def archive_change_query(db,scope,*,status=None,filters=None,sort=None):
    from app.services.project import get_scoped_archive_query
    scoped=get_scoped_archive_query(db,scope).with_entities(PmsProjectArchive.id).subquery()
    query=db.query(ArchiveChange).filter(ArchiveChange.archive_id.in_(scoped.select()))
    query=query.filter(or_(ArchiveChange.author_id==scope['user_id'],ArchiveChange.approver_id==scope['user_id']))
    if status is not None:query=query.filter(ArchiveChange.status==status)
    from app.services.list_query import apply_list_query
    from app.services.business_list_query import compile_business_query
    from app.services.query_conditions import build_query_clause
    from app.models.dict import SysDict, SysDictItem
    columns={key:(getattr(ArchiveChange,key),'text') for key in ('reason','opinion')}
    columns['project_code']=(select(PmsProjectArchive.project_code).where(PmsProjectArchive.id==ArchiveChange.archive_id).scalar_subquery(),'text')
    for key in ('author_name','approver_name'):
        columns[key]=(select(SysUser.real_name).where(SysUser.id==getattr(ArchiveChange,key.replace('_name','_id'))).scalar_subquery(),'text')
    for key in ('created_at','updated_at'):columns[key]=(getattr(ArchiveChange,key),'date')
    columns['status']=(ArchiveChange.status,'number')
    labels={int(value):label for value,label in db.query(SysDictItem.item_value,SysDictItem.item_label).join(SysDict,SysDict.id==SysDictItem.dict_id).filter(SysDict.dict_code=='archive_change_status')}
    fields={key:{'kind':'enum_number' if key=='status' else kind,'labels':labels if key=='status' else {}} for key,(_,kind) in columns.items()}
    for condition in compile_business_query(fields,filters):
        kind=fields[condition.field]['kind']
        value=condition.value
        if kind=='enum_number' and value is not None:value=[int(item) for item in value] if isinstance(value,list) else int(value)
        item={'schemaVersion':2,'operator':condition.operator,'value':value.isoformat() if hasattr(value,'isoformat') else value,
              'valueEnd':condition.valueEnd.isoformat() if hasattr(condition.valueEnd,'isoformat') else condition.valueEnd}
        clause=columns[condition.field][0].in_([]) if condition.operator=='in' and value==[] else build_query_clause(columns[condition.field][0],kind,item,membership=True)
        query=query.filter(clause)
    return apply_list_query(query,columns,[],sort,(ArchiveChange.id.desc(),),unified_kinds={key:field['kind'] for key,field in fields.items()})


def list_archive_changes(db,scope,*,page=1,page_size=50,status=None,filters=None,sort=None):
    query=archive_change_query(db,scope,status=status,filters=filters,sort=sort)
    total=query.count();rows=query.offset((page-1)*page_size).limit(page_size).all()
    return {'total':total,'items':serialize_archive_changes(db,rows,scope)}


def serialize_archive_changes(db,rows,scope):
    archives={a.id:a for a in db.query(PmsProjectArchive).filter(PmsProjectArchive.id.in_({r.archive_id for r in rows})).all()} if rows else {}
    users={u.id:u for u in db.query(SysUser).filter(SysUser.id.in_({user_id for r in rows for user_id in (r.author_id,r.approver_id)})).all()} if rows else {}
    contexts=archive_edit_contexts(db,list(archives.values()),scope)
    items=[]
    for row in rows:
        archive=archives[row.archive_id];author=users.get(row.author_id);head=users.get(row.approver_id)
        context=contexts[row.archive_id]
        items.append({**_change_result(row),'archive_id':row.archive_id,'project_code':archive.project_code,
            'author_name':author.real_name if author else '', 'approver_name':head.real_name if head else '',
            'reason':row.reason,'opinion':row.opinion,'created_at':row.created_at,'updated_at':row.updated_at,
            'differences':json.loads(row.differences_json),'updates':json.loads(row.updates_json),
            'can_approve':row.status==2 and context['approver_id']==row.approver_id==scope['user_id'] and 'project:archive:edit' in scope['permissions'],
            'can_withdraw':row.status==2 and row.author_id==scope['user_id'] and 'project:archive:edit' in scope['permissions']})
    return items
