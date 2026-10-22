"""Explicit draft administration. Never creates archives or invokes ERP."""
import json
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import update
from app.models.form_draft import PmsFormDraft
from app.models.user import SysUser
from app.models.product_line import SysProductLine
from app.services.authorization import enforce_permission
from app.services.business_data_scope import has_all_business_data
from app.services.product_line_scope import require_line_access
from app.services.project import get_child_dept_ids
from app.services.operation_log import record_operation_log
from app.services import form_drafts as drafts

PERMISSION='project:archive:draft:manage'

def _guard(db,context):
    for code in ('project:archive:view',PERMISSION):enforce_permission(context,code)
    user=db.get(SysUser,context['user_id'])
    if not user or user.status!=1:raise HTTPException(403,'账号不可用')

def _person_access(db,context,person_id):
    if has_all_business_data(context):return
    scope=context.get('data_scope',1)
    person=db.get(SysUser,person_id) if person_id else None
    if not person:raise HTTPException(404,'草稿不存在或不可访问')
    if scope==1 and person_id!=context['user_id']:raise HTTPException(404,'草稿不存在或不可访问')
    if scope in (2,3):
        dept=context.get('dept_id')
        allowed=([dept] if scope==2 else get_child_dept_ids(db,dept)) if dept else []
        # Disabled employees retain their department for scoped cleanup.
        if person.dept_id not in allowed:raise HTTPException(404,'草稿不存在或不可访问')
    elif scope not in (1,4):raise HTTPException(404,'草稿不存在或不可访问')

def _scope(db,context,row):
    if row.product_line_id is None:raise HTTPException(404,'草稿尚未归属产品线，请由本人补选后处理')
    require_line_access(db,context,row.product_line_id)
    _person_access(db,context,row.owner_id)
    _person_access(db,context,json.loads(row.payload_json).get('manager_id') or row.owner_id)

def require_draft(db,context,draft_id):
    _guard(db,context)
    row=db.query(PmsFormDraft).filter(PmsFormDraft.id==str(draft_id),PmsFormDraft.resource==drafts.RESOURCE,
        PmsFormDraft.status=='active').populate_existing().first()
    if not row:raise HTTPException(404,'草稿不存在或不可访问')
    _scope(db,context,row)
    return row

def _name(db,user_id):
    user=db.get(SysUser,user_id)
    return (user.real_name or user.username) if user else '人员已不可用'

def view(db,row,content=False):
    result=drafts._view(db,row,content=content)
    line=db.get(SysProductLine,row.product_line_id)
    person=db.get(SysUser,row.owner_id)
    result.update(product_line_id=row.product_line_id,creator_name=_name(db,row.owner_id),creator_enabled=bool(person and person.status==1),
                  product_line_name=line.display_name if line else '产品线已不可用')
    if content:
        payload=result['payload'];labels=result['value_labels']
        def display(key,value):
            if value is None or value=='':return '-'
            if key in labels:return labels[key]
            if isinstance(value,bool):return '是' if value else '否'
            return str(value)
        result['fields']=[{'key':key,'label':policy['label'],'display':display(key,payload[key])}
                          for key,policy in drafts._policies(db).items() if key in payload]
        from app.services.archive_log_presentation import ARCHIVE_FORM_ORDER
        order={key:index for index,key in enumerate(ARCHIVE_FORM_ORDER)}
        result['fields'].sort(key=lambda item:order.get(item['key'],len(order)))
        result['fields'].append({'key':'creator_name','label':'创建人','display':result['creator_name']+('' if result['creator_enabled'] else '（已停用）')})
    return result

def list_drafts(db,context,*,page=1,page_size=50,project_code=None,project_name=None,owner_id=None,product_line_id=None):
    _guard(db,context)
    query=db.query(PmsFormDraft).filter_by(resource=drafts.RESOURCE,status='active')
    if not has_all_business_data(context):query=query.filter(PmsFormDraft.product_line_id.in_(context.get('product_line_ids') or []))
    if owner_id is not None:query=query.filter(PmsFormDraft.owner_id==owner_id)
    if product_line_id is not None:query=query.filter(PmsFormDraft.product_line_id==product_line_id)
    visible=[];policies=drafts._policies(db)
    # JSON field filtering is dialect-neutral; scope precedes pagination/count.
    for row in query.order_by(PmsFormDraft.updated_at.desc(),PmsFormDraft.id).all():
        try:_scope(db,context,row)
        except HTTPException:continue
        payload=json.loads(row.payload_json)
        if project_code and (not policies.get('project_code',{}).get('visible') or project_code.casefold() not in (payload.get('project_code') or '').casefold()):continue
        if project_name and (not policies.get('project_name',{}).get('visible') or project_name.casefold() not in (payload.get('project_name') or '').casefold()):continue
        visible.append(row)
    return {'items':[view(db,row) for row in visible[(page-1)*page_size:page*page_size]],'total':len(visible)}

def delete_draft(db,context,draft_id,version,request=None):
    try:
        from app.services.archive_code_unique import lock_codes
        lock_codes(db.connection(), field_key='serial_no')
        row=require_draft(db,context,draft_id)
        before={'owner_id':row.owner_id,'status':row.status,'version':row.version}
        changed=db.execute(update(PmsFormDraft).where(PmsFormDraft.id==row.id,PmsFormDraft.owner_id==row.owner_id,
            PmsFormDraft.version==version,PmsFormDraft.status=='active').values(status='deleted',version=version+1,
                updated_at=datetime.utcnow()),execution_options={'synchronize_session':False}).rowcount
        if changed!=1:raise drafts._conflict()
        db.expire(row)
        record_operation_log(db,module='项目档案草稿',action='draft_delete',entity_type='pms_form_draft',entity_id=row.id,
            entity_name='新增档案草稿',operator_id=context['user_id'],request=request,summary='管理人员删除新增档案草稿',
            before_data=before,after_data={'owner_id':row.owner_id,'status':row.status,'version':row.version})
        db.commit();return {'msg':'草稿已删除'}
    except Exception:db.rollback();raise
