"""Stream scoped archive change history using the standard Excel writer."""
import os
from pathlib import Path
import tempfile
from fastapi import HTTPException
from app.services.archive_change import archive_change_query, serialize_archive_changes
from app.services.authorization import enforce_permission
from app.services.operation_log import record_operation_log
from app.services.report_workbook import ReportWorkbook

FIELDS={'project_code':'项目编号','author_name':'提交人','approver_name':'审批人',
        'reason':'变更原因','status':'审批状态','created_at':'申请时间','updated_at':'更新时间','opinion':'审批意见'}


def create_archive_change_export(db,data,scope,request=None):
    for permission in ('project:archive:view','project:archive:export'):
        enforce_permission(scope,permission)
    if data.parameters or data.column_filters or any(key not in FIELDS for key in data.columns):
        raise HTTPException(422,'导出字段或参数无效；当前页漏斗不参与后台导出')
    query=archive_change_query(db,scope,filters=data.filters,sort=data.sort)
    from app.models.dict import SysDict,SysDictItem
    labels={int(value):label for value,label in db.query(SysDictItem.item_value,SysDictItem.item_label).join(SysDict,SysDict.id==SysDictItem.dict_id).filter(SysDict.dict_code=='archive_change_status')}
    descriptor,path=tempfile.mkstemp(suffix='.xlsx');os.close(descriptor)
    count=0
    try:
        with ReportWorkbook(path) as book:
            sheet=book.sheet('档案变更',[(key,FIELDS[key]) for key in data.columns])
            batch=[]
            def append_batch():
                for item in serialize_archive_changes(db,batch,scope):
                    item['status']=labels.get(item['status'],str(item['status']))
                    sheet.append(item)
            for row in query.yield_per(500):
                batch.append(row);count+=1
                if len(batch)==500:
                    append_batch();batch=[]
            if batch:append_batch()
        record_operation_log(db,module='项目档案变更',action='export',entity_type='business_list_export',
            entity_name='档案变更',operator_id=scope['user_id'],request=request,summary=f'导出档案变更 {count} 条',
            after_data={'rows':count,'columns':data.columns})
        db.commit()
        return path,'项目档案变更.xlsx'
    except Exception:
        db.rollback();Path(path).unlink(missing_ok=True);raise
