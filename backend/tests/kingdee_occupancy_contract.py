"""User-actionable lock conflicts, without retries or lost business errors."""
import unittest
from unittest.mock import patch,MagicMock
import httpx
from kingdee_app_auth_contract import client_with
from app.services import kingdee

GUIDANCE='请在金蝶端退出当前单据后，再次点击 PMS 的“同步”'
CONFLICT='“I0001”使用业务单据：“辅助资料”业务操作-“[辅助资料-TEST-修改]”冲突，请稍候再使用。'

class OccupancyContract(unittest.TestCase):
    def invoke(self, operation, message):
        calls=[]
        def transport(req):
            calls.append(str(req.url))
            return httpx.Response(200,json={'Result':{'ResponseStatus':{'IsSuccess':False,'Errors':[{'Message':message}]}}})
        with client_with(transport) as c:
            if operation=='Save':result=c.save_assistant_data('BOS_ASSISTANTDATA_DETAIL','xsxm','TEST','样本')
            else:result=c._operate_assistant_data(operation,'BOS_ASSISTANTDATA_DETAIL','42')
        self.assertFalse(result['success']);self.assertEqual(len(calls),1)
        return result['message']
    def test_conflict_names_owner_and_exact_recovery_action(self):
        for op in ['Save','Submit','Audit']:
            with self.subTest(op=op):
                msg=self.invoke(op,CONFLICT)
                self.assertIn(GUIDANCE,msg);self.assertIn('I0001',msg);self.assertIn('占用',msg)
                if op!='Save':self.assertIn('保存已完成',msg)
    def test_explicit_document_occupancy_without_owner_does_not_invent_owner(self):
        msg=self.invoke('Save','当前单据已被其他用户占用')
        self.assertIn(GUIDANCE,msg);self.assertNotIn('I0001',msg)
    def test_other_business_errors_are_not_misdiagnosed(self):
        for raw in ['名称已存在','没有审核权限','字段值与规则冲突','业务操作与当前单据状态冲突']:
            msg=self.invoke('Save',raw)
            self.assertIn(raw,msg);self.assertNotIn(GUIDANCE,msg)
    def test_occupancy_details_are_redacted(self):
        msg=self.invoke('Audit',CONFLICT+' test-app-secret')
        self.assertIn(GUIDANCE,msg);self.assertNotIn('test-app-secret',msg)
    def test_batch_summary_displays_occupancy_guidance_and_owner(self):
        message=self.invoke('Save',CONFLICT)
        with patch.object(kingdee,'sync_project_archive_to_erp',return_value={'success':False,'message':message}) as sync,patch.object(kingdee,'record_operation_log'):
            result=kingdee.batch_sync_project_archives(MagicMock(),[42],user_id=5)
        self.assertIn(GUIDANCE,result['message']);self.assertIn('I0001',result['message'])
        self.assertEqual(result['failed_count'],1);sync.assert_called_once()

if __name__=='__main__':unittest.main()
