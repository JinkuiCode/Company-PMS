"""Owner-only form drafts. All business rules stay in registered adapters."""
import json
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from app.models.form_draft import PmsFormDraft
from app.models.user import SysUser
from app.models.product_line import SysProductLine
from app.schemas.project import ArchiveUpdate, ArchiveCreate
from app.services.authorization import enforce_permission
from app.services.business_data_scope import has_all_business_data
from app.services.product_line_scope import require_line_access
from app.services.field_policy import get_effective_field_policies, MODULE_PROJECT_ARCHIVE
from app.services.archive_quantity import validate_archive_quantity
from app.services.project import _ensure_archive_assignment_allowed, create_archive, ensure_archive_access
from app.services.operation_log import record_operation_log
from app.services.archive_code_unique import ensure_code_available, lock_codes

RESOURCE = 'archive-create'

def _guard(db, context):
    for code in ('project:archive:view', 'project:archive:add'): enforce_permission(context, code)
    user = db.get(SysUser, context['user_id'])
    if not user or user.status != 1: raise HTTPException(403, '账号不可用')
    query = db.query(SysProductLine.id).filter(SysProductLine.is_enabled == 1)
    if not has_all_business_data(context): query = query.filter(SysProductLine.id.in_(context.get('product_line_ids') or []))
    if not query.first(): raise HTTPException(403, '没有可用产品线，无法使用新增档案草稿')
    _ensure_archive_assignment_allowed(db, manager_id=user.id, product_category=None, scope_context=context)


def _policies(db):
    return {i['field_key']: i for i in get_effective_field_policies(db, MODULE_PROJECT_ARCHIVE)['items']}


def _scope(db, context, payload):
    if payload.get('product_line_id') is not None:
        require_line_access(db, context, payload['product_line_id'])
    _ensure_archive_assignment_allowed(db, manager_id=payload.get('manager_id') or context['user_id'],
                                      product_category=None, scope_context=context)


def _invalid(fields):
    return HTTPException(422, {'code':'FIELD_POLICY_VALIDATION_FAILED','fields':fields})


def product_line_options(db, context):
    """Draft choices use local authorized master data, never the ERP directory."""
    _guard(db, context)
    query = db.query(SysProductLine)
    if not has_all_business_data(context):
        query = query.filter(SysProductLine.id.in_(context.get('product_line_ids') or []))
    lines = query.order_by(SysProductLine.sort, SysProductLine.id).all()
    return {'options':[{'value':line.id,'label':line.display_name} for line in lines if line.is_enabled],
            'label_map':{str(line.id):line.display_name for line in lines}}


def _schema_errors(exc):
    result = []
    for error in exc.errors():
        limit = error.get('ctx', {}).get('max_length')
        message = f'最多允许{limit}个字符' if limit else '字段类型或格式不正确'
        result.append({'field_key':str(error['loc'][0]), 'message':message})
    return _invalid(result)


def _clean(db, context, payload, previous=None):
    policies = _policies(db)
    allowed = {key for key in ArchiveUpdate.model_fields if key not in ('expected_version','product_category')
               and key in policies and policies[key]['visible'] and policies[key]['editable']}
    if set(payload) - allowed:
        raise HTTPException(422, '草稿包含未知、隐藏或只读字段，请刷新字段后重试')
    values = dict(payload)
    for key, value in values.items():
        if isinstance(value, (dict,list,bool)): raise _invalid([{'field_key':key, 'message':'字段类型不正确'}])
        if value == '' and key not in ('project_code','project_name','customer','serial_no','remarks','delivery_note','address_detail','project_contact','contact_phone'):
            values[key] = None
    try:
        data = ArchiveUpdate.model_validate(values).model_dump(mode='json', exclude_unset=True)
        validate_archive_quantity(data.get('quantity'))
    except ValidationError as exc:
        raise _schema_errors(exc) from None
    except ValueError as exc: raise _invalid([{'field_key':'quantity','message':str(exc)}]) from None
    missing = [{'field_key':key, 'message':f'请填写{label}'}
               for key, label in (('project_code','项目编号'), ('project_name','项目名称'))
               if not (data.get(key) or '').strip()]
    if data.get('product_line_id') is None:
        missing.append({'field_key':'product_line_id','message':'请选择产品线'})
    if data.get('archive_category') is None:
        missing.append({'field_key':'archive_category','message':'请选择档案类别'})
    if missing: raise _invalid(missing)
    data['project_code'] = data['project_code'].strip()
    if data.get('manager_id') is not None:
        person = db.get(SysUser, data['manager_id'])
        if not person or person.status != 1: raise _invalid([{'field_key':'manager_id','message':'负责人不可用'}])
    _scope(db, context, data)
    previous = previous or {}
    if data.get('product_line_id') is not None and data.get('product_line_id') != previous.get('product_line_id'):
        require_line_access(db, context, data['product_line_id'], selectable=True)
    from app.services.enum_registry import validate_enum_value
    for key, value in data.items():
        code = policies[key].get('enum_code')
        if code and value is not None:
            validate_enum_value(db, code, value, current_value=previous.get(key))
    from app.services.archive_field_linkage import linkage_errors
    errors = linkage_errors(db, previous, data, is_create=not previous)
    if errors: raise _invalid(errors)
    # A draft may retain a now-disabled enum. Formal creation validates enabled values again.
    return data


def _row(db, context, draft_id):
    row = db.query(PmsFormDraft).filter_by(id=str(draft_id), resource=RESOURCE, owner_id=context['user_id']).populate_existing().first()
    if not row or row.status == 'deleted': raise HTTPException(404, '草稿不存在或不可访问')
    _scope(db, context, json.loads(row.payload_json))
    return row


def _view(db, row, *, content=False):
    payload = json.loads(row.payload_json)
    policies = _policies(db)
    visible = {k:v for k,v in payload.items() if k in policies and policies[k]['visible']}
    def local_time(value):
        return value.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    result = {'id':row.id, 'version':row.version, 'status':row.status, 'archive_id':row.archive_id,
              'project_code':visible.get('project_code') or '', 'project_name':visible.get('project_name') or '未命名项目档案',
              'updated_at':local_time(row.updated_at)}
    if content:
        result['payload'] = visible
        warnings = ['部分字段现已隐藏或只读，正式保存前请按当前规则核对'] if any(k not in policies or not policies[k]['visible'] or not policies[k]['editable'] for k in payload) else []
        labels = {}
        from app.models.dict import SysDict, SysDictItem
        for key, value in visible.items():
            if value is None or value == '': continue
            label = None; unavailable = False
            if key == 'product_line_id':
                line = db.get(SysProductLine, value)
                label = line.display_name if line else None
                unavailable = not line or not line.is_enabled
            elif key == 'manager_id':
                person = db.get(SysUser, value)
                label = (person.real_name or person.username) if person else None
                unavailable = not person or person.status != 1
            elif policies[key].get('enum_code'):
                pair = db.query(SysDictItem, SysDict.status).join(SysDict, SysDict.id == SysDictItem.dict_id).filter(
                    SysDict.dict_code == policies[key]['enum_code'], SysDictItem.item_value == str(value)).first()
                label = pair[0].item_label if pair else None
                unavailable = not pair or pair[0].status != 1 or pair[1] != 1
            else: continue
            labels[key] = label or '原选项已不可用'
            if unavailable: warnings.append(f"{policies[key]['label']}的原选项已停用或不可选，正式保存前请重新选择")
        result['warnings'] = warnings
        result['value_labels'] = labels
    return result


def _conflict():
    return HTTPException(409, {'code':'DRAFT_VERSION_CONFLICT','message':'草稿已有更新，请保留本次输入，加载最新版本或另存为新草稿'})


def _claim(db, row, expected_version, **values):
    changed = db.execute(update(PmsFormDraft).where(PmsFormDraft.id == row.id,
        PmsFormDraft.owner_id == row.owner_id, PmsFormDraft.version == expected_version,
        PmsFormDraft.status == 'active').values(version=expected_version+1,updated_at=datetime.utcnow(),**values),
        execution_options={'synchronize_session':False}).rowcount
    if changed != 1: raise _conflict()
    db.expire(row)


def _audit(db, context, row, action, request=None):
    # Do not replicate a private form's content into global audit logs.
    record_operation_log(db, module='项目档案草稿', action=action, entity_type='pms_form_draft', entity_id=row.id,
        entity_name='本人新增档案草稿', operator_id=context['user_id'],request=request,
        summary={'draft_save':'保存新增档案草稿','draft_delete':'删除新增档案草稿','draft_convert':'草稿转为正式档案'}[action],
        after_data={'version':row.version,'status':row.status,'archive_id':row.archive_id})


def list_drafts(db, context, page=1, page_size=50):
    _guard(db, context)
    # Scope filtering happens before pagination/count; never expose inaccessible titles.
    rows = db.query(PmsFormDraft).filter_by(owner_id=context['user_id'],resource=RESOURCE,status='active').order_by(PmsFormDraft.updated_at.desc(),PmsFormDraft.id).all()
    visible=[]
    for row in rows:
        try: _scope(db, context, json.loads(row.payload_json))
        except HTTPException: continue
        visible.append(row)
    return {'items':[_view(db,r) for r in visible[(page-1)*page_size:page*page_size]], 'total':len(visible)}


def get_draft(db, context, draft_id):
    _guard(db, context)
    return _view(db,_row(db,context,draft_id),content=True)


def save_draft(db, context, data, request=None):
    _guard(db, context)
    existing = db.get(PmsFormDraft,str(data.id))
    if existing: existing = _row(db,context,data.id)
    payload = _clean(db,context,data.payload,json.loads(existing.payload_json) if existing else None)
    if existing:
        policies=_policies(db)
        # Re-saving the visible editable projection must not erase protected history.
        retained={key:value for key,value in json.loads(existing.payload_json).items()
                  if key not in policies or not policies[key]['visible'] or not policies[key]['editable']}
        payload={**retained,**payload}
    encoded = json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    if len(encoded.encode('utf-8')) > 65536: raise HTTPException(422,'草稿内容过大')
    row = db.get(PmsFormDraft,str(data.id))
    try:
        ensure_code_available(db.connection(), payload.get('project_code'), exclude_draft_id=data.id)
        if row:
            row = _row(db,context,data.id)
            if row.status != 'active': raise _conflict()
            if data.expected_version is None:
                if row.version == 1 and row.payload_json == encoded: return _view(db,row,content=True)
                raise _conflict()
            _claim(db,row,data.expected_version,payload_json=encoded,product_line_id=payload.get('product_line_id'))
        else:
            if data.expected_version is not None: raise _conflict()
            row=PmsFormDraft(id=str(data.id),owner_id=context['user_id'],resource=RESOURCE,payload_json=encoded,
                             product_line_id=payload.get('product_line_id'),version=1,status='active')
            db.add(row);db.flush()
        _audit(db,context,row,'draft_save',request)
        db.commit();db.refresh(row)
        return _view(db,row,content=True)
    except IntegrityError:
        db.rollback()
        # An overlapping initial POST can only recover the exact same owner's payload.
        row = _row(db,context,data.id)
        if data.expected_version is None and row.version == 1 and row.status == 'active' and row.payload_json == encoded:
            return _view(db,row,content=True)
        raise _conflict() from None
    except Exception:
        db.rollback();raise


def delete_draft(db, context, draft_id, version, request=None):
    _guard(db,context)
    try:
        row=_row(db,context,draft_id)
        _claim(db,row,version,status='deleted')
        _audit(db,context,row,'draft_delete',request);db.commit()
        return {'msg':'草稿已删除'}
    except Exception: db.rollback();raise


def submit_draft(db, context, draft_id, version, request=None):
    _guard(db,context)
    try:
        lock_codes(db.connection())
        row=_row(db,context,draft_id)
        if row.status == 'used':
            ensure_archive_access(db,row.archive_id,context)
            return {'id':row.archive_id,'msg':'该草稿已保存为正式档案','replayed':True}
        _claim(db,row,version,status='used')
        payload=_clean(db,context,json.loads(row.payload_json))
        try: data=ArchiveCreate.model_validate(payload)
        except ValidationError as exc:
            raise _schema_errors(exc) from None
        result=create_archive(db,data,context['user_id'],request=request,scope_context=context,commit=False)
        row.archive_id=result['id']
        _audit(db,context,row,'draft_convert',request)
        db.commit()
        return result
    except Exception: db.rollback();raise
