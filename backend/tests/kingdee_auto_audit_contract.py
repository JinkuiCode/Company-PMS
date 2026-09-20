"""Stateful fake Kingdee transport; no external traffic or real credentials."""
import json,unittest
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
import httpx
from kingdee_app_auth_contract import client_with
from app.services import kingdee

class FakeERP:
    def __init__(self,state='A',fail=None,drift=False,no_transition=False):
        self.state=state;self.fail=fail;self.drift=drift;self.no_transition=no_transition;self.calls=[];self.entry='42'
    def __call__(self,req):
        op=str(req.url).split('DynamicFormService.')[1].split('.')[0];self.calls.append(op)
        body=json.loads(req.content);data=json.loads(body['data'])
        if op=='ExecuteBillQuery':
            assert data['FieldKeys']=='FEntryID,FNumber,FDataValue,FDescription,FDocumentStatus'
            assert "FId.FNumber = 'xsxm' AND FNumber = 'TEST'"==data['FilterString']
            return httpx.Response(200,json=[[self.entry,'TEST','TEST','样本',self.state]])
        assert op in ['Submit','Audit']
        assert body['formid']=='BOS_ASSISTANTDATA_DETAIL' and data['Ids']=='42'
        if self.fail==op:return httpx.Response(200,json={'Result':{'ResponseStatus':{'IsSuccess':False,'Errors':[{'Message':'无操作权限 test-app-secret'}]}}})
        if self.fail==op+'Timeout':raise httpx.ReadTimeout('test-app-secret',request=req)
        if self.fail==op+'Malformed':return httpx.Response(200,json={'Result':{}})
        if not self.no_transition:self.state='B' if op=='Submit' else 'C'
        if self.drift:self.entry='OTHER'
        return httpx.Response(200,json={'Result':{'ResponseStatus':{'IsSuccess':True}}})

class AutoAuditContract(unittest.TestCase):
    def run_flow(self,erp,readonly=False):
        with client_with(erp,K3_READ_ONLY=readonly) as c:return c.ensure_assistant_data_audited('BOS_ASSISTANTDATA_DETAIL','xsxm','TEST','样本',expected_entry_id='42')
    def test_created_transitions_and_verifies_audited(self):
        e=FakeERP();self.assertTrue(self.run_flow(e)['success']);self.assertEqual(e.calls,['ExecuteBillQuery','Submit','ExecuteBillQuery','Audit','ExecuteBillQuery'])
    def test_submitted_skips_submit(self):
        e=FakeERP('B');self.assertTrue(self.run_flow(e)['success']);self.assertNotIn('Submit',e.calls)
    def test_already_audited_does_not_repeat_operations(self):
        e=FakeERP('C');self.assertTrue(self.run_flow(e)['success']);self.assertEqual(e.calls,['ExecuteBillQuery'])
    def test_readonly_blocks_all_requests(self):
        e=FakeERP();self.assertFalse(self.run_flow(e,True)['success']);self.assertEqual(e.calls,[])
    def test_submit_failure_stops_and_redacts(self):
        e=FakeERP(fail='Submit');r=self.run_flow(e);self.assertFalse(r['success']);self.assertNotIn('Audit',e.calls);self.assertNotIn('test-app-secret',r['message'])
    def test_audit_failure_is_not_success(self):
        e=FakeERP(fail='Audit');self.assertFalse(self.run_flow(e)['success']);self.assertEqual(e.calls.count('Audit'),1)
    def test_timeout_no_retry_and_ambiguous(self):
        for stage in ['Submit','Audit']:
            e=FakeERP(fail=stage+'Timeout')
            with self.assertRaises(kingdee.KingdeeSaveOutcomeAmbiguous):self.run_flow(e)
            self.assertEqual(e.calls.count(stage),1)
    def test_malformed_operation_response_is_ambiguous(self):
        e=FakeERP(fail='SubmitMalformed')
        with self.assertRaises(kingdee.KingdeeSaveOutcomeAmbiguous):self.run_flow(e)
    def test_unknown_status_no_write(self):
        e=FakeERP('UNKNOWN');self.assertFalse(self.run_flow(e)['success']);self.assertEqual(e.calls,['ExecuteBillQuery'])
    def test_response_success_without_state_change_is_not_success(self):
        e=FakeERP(no_transition=True);self.assertFalse(self.run_flow(e)['success']);self.assertNotIn('Audit',e.calls)
    def test_id_change_stops_before_next_operation(self):
        e=FakeERP(drift=True)
        try:r=self.run_flow(e);self.assertFalse(r['success'])
        except kingdee.KingdeeSaveOutcomeAmbiguous:pass
        self.assertNotIn('Audit',e.calls)
    def test_name_mismatch_not_approved(self):
        e=FakeERP('C')
        with client_with(e) as c:r=c.ensure_assistant_data_audited('BOS_ASSISTANTDATA_DETAIL','xsxm','TEST','不同名称',expected_entry_id='42')
        self.assertFalse(r['success']);self.assertEqual(e.calls,['ExecuteBillQuery'])
    def test_save_to_first_read_identity_change_stops(self):
        e=FakeERP('C');e.entry='43'
        with client_with(e) as c:
            with self.assertRaises(kingdee.KingdeeSaveOutcomeAmbiguous):
                c.ensure_assistant_data_audited('BOS_ASSISTANTDATA_DETAIL','xsxm','TEST','样本',expected_entry_id='42')
        self.assertEqual(e.calls,['ExecuteBillQuery'])
    def test_sync_passes_saved_id_and_requires_audit(self):
        for saved, expected_success in [({'Id':'42'},True), ({},False), ({'Id':'43'},False)]:
            a=SimpleNamespace(id=9,project_code='TEST',project_name='样本',erp_synced=0,erp_sync_status='pending')
            c=MagicMock();c.login.return_value=True;c.query_assistant_data.return_value={'FEntryID':'42'}
            c.save_assistant_data.return_value={'success':True,'data':saved}
            c.ensure_assistant_data_audited.return_value={'success':True}
            query=MagicMock();query.populate_existing.return_value.filter.return_value.first.return_value=a
            with patch.object(kingdee,'claim_archive_for_sync',return_value=(a,{})),patch.object(kingdee,'get_scoped_archive_query',return_value=query),patch.object(kingdee,'serialize_model',return_value={}),patch.object(kingdee,'record_operation_log'),patch.object(kingdee,'KingdeeClient',return_value=c):
                r=kingdee.sync_project_archive_to_erp(MagicMock(),9,user_id=5)
            self.assertEqual(r['success'],expected_success)
            if expected_success:
                self.assertEqual(a.erp_sync_status,'success');self.assertEqual(c.ensure_assistant_data_audited.call_args.kwargs['expected_entry_id'],'42')
                self.assertEqual(c.save_assistant_data.call_args.kwargs['project_name'],'样本')
                self.assertNotIn('description',c.save_assistant_data.call_args.kwargs)
            else:
                self.assertEqual(a.erp_sync_status,'pending');c.ensure_assistant_data_audited.assert_not_called()
    def test_only_saved_cannot_mark_sync_success(self):
        a=SimpleNamespace(id=9,project_code='TEST',project_name='样本',erp_synced=0,erp_sync_status='pending')
        c=MagicMock();c.login.return_value=True;c.query_assistant_data.return_value=None;c.save_assistant_data.return_value={'success':True,'data':{'Id':'42'}};c.ensure_assistant_data_audited.return_value={'success':False,'message':'保存已完成，但审核失败'}
        db=MagicMock()
        with patch.object(kingdee,'claim_archive_for_sync',return_value=(a,{})),patch.object(kingdee,'get_scoped_archive_query'),patch.object(kingdee,'serialize_model',return_value={}),patch.object(kingdee,'record_operation_log') as log,patch.object(kingdee,'KingdeeClient',return_value=c):r=kingdee.sync_project_archive_to_erp(db,9,user_id=5)
        self.assertFalse(r['success']);self.assertEqual(a.erp_sync_status,'failed');self.assertEqual(a.erp_synced,1);self.assertEqual(log.call_args.kwargs['status'],'failed');self.assertIn('审核',log.call_args.kwargs['error_msg'])
        # Saved external identity must block renumbering/deletion even before audit succeeds.
if __name__=='__main__':unittest.main()
