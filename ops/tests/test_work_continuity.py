import importlib.util
from pathlib import Path
import unittest
import json
import sys
import tempfile
import subprocess
spec = importlib.util.spec_from_file_location('continuity', Path(__file__).parents[1]/'check_work_continuity.py')
module = importlib.util.module_from_spec(spec)
class ExitGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): spec.loader.exec_module(module)
    def test_authorized_work_prevents_exit_even_if_another_item_is_blocked(self):
        rows=[{'id':'A','status':'ready','authorization':'approved'}, {'id':'B','status':'blocked_input','blocker':'等待业务真实项目编号','request_state':'already_requested'}]
        allowed, reasons=module.check_exit(rows)
        self.assertFalse(allowed); self.assertTrue(any('A' in s for s in reasons))
    def test_completed_batch_is_not_completed_goal(self):
        allowed,_=module.check_exit([{'id':'A','status':'done','evidence':'verification.json:exit0'}, {'id':'B','status':'in_progress','authorization':'approved'}])
        self.assertFalse(allowed)
    def test_blocked_without_specific_question_or_input_reason_is_invalid(self):
        allowed,_=module.check_exit([{'id':'A','status':'blocked_approval','blocker':'','request_state':''}])
        self.assertFalse(allowed)
    def test_actual_gate_with_existing_request_allows_pause_without_reasking(self):
        allowed,_=module.check_exit([{'id':'A','status':'blocked_approval','blocker':'用户仅批准本地候选，正式部署尚未批准','request_state':'pending','question':'是否批准部署固定的v1.2.0候选？','request_reference':'conversation:explicit-window-request'}])
        self.assertTrue(allowed)
    def test_completed_work_requires_evidence_and_unknown_status_fails_closed(self):
        for row in [{'id':'A','status':'done'},{'id':'A','status':'deferred'}]:
            self.assertFalse(module.check_exit([row])[0])
    def test_vague_already_requested_cannot_turn_work_into_a_blocker(self):
        for state,reason in [('already_requested','等待继续'),('deferred_by_user','待批准')]:
            self.assertFalse(module.check_exit([{'id':'A','status':'blocked_input','blocker':reason,'request_state':state}])[0])
    def test_all_blocked_states_require_specific_request_and_reference(self):
        item={'id':'A','status':'blocked_input','blocker':'等待业务确认的新项目编号、名称和产品线','request_state':'already_requested','required_input':'提供业务确认的项目编号、名称和产品线','request_reference':'conversation:project-sample-request'}
        self.assertTrue(module.check_exit([item])[0])
        for key in ('required_input','request_reference'):
            missing=dict(item);missing.pop(key);self.assertFalse(module.check_exit([missing])[0])
        deferred=dict(item,request_state='deferred_by_user')
        self.assertFalse(module.check_exit([deferred])[0])
        deferred['user_instruction_reference']='conversation:user-explicitly-deferred-sample'
        self.assertTrue(module.check_exit([deferred])[0])
    def test_malformed_ledger_fails_closed(self):
        for rows in (None,{},'tasks',[None]):self.assertFalse(module.check_exit(rows)[0])
    def test_cli_records_rejected_end_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger=Path(directory)/'tasks.json'
            ledger.write_text(json.dumps({'tasks':[{'id':'next','status':'ready','authorization':'approved'}]}))
            result=subprocess.run([sys.executable,str(Path(__file__).parents[1]/'check_work_continuity.py'),'--ledger',str(ledger)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            record=json.loads((Path(directory)/'exit-checks.jsonl').read_text().strip())
            self.assertFalse(record['may_end']);self.assertIn('checked_at',record)
            self.assertEqual(record['active_ids'],['next'])
    def test_all_done_is_valid(self):
        self.assertTrue(module.check_exit([{'id':'A','status':'done','evidence':'checks.json:0'}])[0])
if __name__=='__main__': unittest.main()
