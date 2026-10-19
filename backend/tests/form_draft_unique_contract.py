"""Global code collisions through actual draft and archive write paths."""
import json
import unittest
from uuid import uuid4

from form_draft_contract import Drafts
from app.models.project import PmsProjectArchive
from app.models.operation_log import SysOperationLog


class UniqueDrafts(Drafts):
    def post(self, code, *, draft_id=None, version=None):
        return self.client.post(self.base, json={'id':draft_id or str(uuid4()), 'expected_version':version,
            'payload':{'project_code':code,'project_name':'本次输入','product_line_id':1,'archive_category':2}})

    def assert_code_conflict(self, response):
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(response.json()['detail']['field_key'],'project_code')
        self.assertEqual(response.json()['detail']['code'],'ARCHIVE_UNIQUE_CONFLICT')

    def test_formal_collision_is_case_and_space_normalized_without_leak(self):
        for code in ('APPROVAL-001',' approval-001 '):
            self.assert_code_conflict(self.post(code))
        self.assertEqual(self.db.query(self.Model).count(),0)

    def test_global_other_owner_and_scope_collision_excludes_self(self):
        from app.models.product_line import SysProductLine
        self.db.add(SysProductLine(id=2,source_key='kingdee',organization_id=200,organization_code='002',organization_name='组织乙',display_name='产品线乙',name_key='line-two'))
        self.db.commit();self.actor(self.owner,lines=[1,2])
        a=self.save({'project_code':'PRIVATE-001','project_name':'SECRET-TITLE','product_line_id':2})
        self.save({'project_code':'PRIVATE-001','project_name':'本人继续','product_line_id':2},a['id'],a['version'])
        self.actor(self.other)
        response=self.post(' private-001 ')
        self.assert_code_conflict(response)
        self.assertNotIn('SECRET-TITLE',response.text)
        self.assertNotIn(a['id'],response.text)
        self.assertEqual(self.db.query(self.Model).count(),1)

    def test_rename_conflict_preserves_version_payload_and_audit(self):
        a=self.save({'project_code':'FIRST'})
        b=self.save({'project_code':'SECOND'})
        count=self.db.query(SysOperationLog).count()
        self.assert_code_conflict(self.post('first',draft_id=b['id'],version=b['version']))
        self.db.expire_all()
        row=self.db.get(self.Model,b['id'])
        self.assertEqual(row.version,b['version'])
        self.assertEqual(json.loads(row.payload_json)['project_code'],'SECOND')
        self.assertEqual(self.db.query(SysOperationLog).count(),count)

    def test_rename_and_delete_release_old_code(self):
        a=self.save({'project_code':'OLD'})
        a=self.save({'project_code':'NEW'},a['id'],a['version'])
        self.save({'project_code':'OLD'})
        self.assertEqual(self.client.request('DELETE',f"{self.base}/{a['id']}",json={'expected_version':a['version']}).status_code,200)
        self.save({'project_code':'NEW'})

    def test_direct_archive_create_and_orm_import_cannot_claim_draft_code(self):
        self.save({'project_code':'DRAFT-NEW'})
        response=self.client.post('/api/projects/archives',json=self.complete_payload())
        self.assert_code_conflict(response)
        with self.assertRaises(Exception) as error:
            self.db.add(PmsProjectArchive(project_code='draft-new',project_name='导入路径',erp_sync_policy='manual'))
            self.db.flush()
        self.assertEqual(getattr(error.exception,'status_code',None),409)
        self.db.rollback()
        self.assertEqual(self.db.query(PmsProjectArchive).count(),1)

    def test_formal_rename_rejects_draft_code_but_other_edits_continue(self):
        self.save({'project_code':'RESERVED'})
        original=self.archive.project_code
        self.archive.project_code='reserved'
        with self.assertRaises(Exception) as error:self.db.flush()
        self.assertEqual(getattr(error.exception,'status_code',None),409)
        self.db.rollback();self.db.refresh(self.archive)
        self.assertEqual(self.archive.project_code,original)
        self.archive.project_name='正常维护名称';self.db.commit()
        self.assertEqual(self.archive.project_name,'正常维护名称')


if __name__=='__main__':
    suite=unittest.TestSuite(UniqueDrafts(name) for name in UniqueDrafts.__dict__ if name.startswith('test_'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
