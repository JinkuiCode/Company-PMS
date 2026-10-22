import unittest,json
from sqlalchemy import insert
from fastapi import HTTPException
from offline_archive_import_contract import ImportContract
from app.models.project import PmsProjectArchive
from app.models.archive_change import ArchiveChange
from app.services.offline_archive_import import apply_import,rollback_import

class SerialImports(ImportContract):
    def test_pending_request_prevents_batch_deleting_its_formal_archive(self):
        result=apply_import(self.db,self.payload,self.uid,self.scope)
        archive=self.db.query(PmsProjectArchive).first()
        self.db.execute(insert(ArchiveChange).values(archive_id=archive.id,active_archive_id=archive.id,submission_id='synthetic',request_hash='h',author_id=self.uid,approver_id=self.uid,department_id=1,base_version='v',updates_json=json.dumps({'serial_no':'RESERVED'}),differences_json='[]',reason='合成',status=2));self.db.commit()
        with self.assertRaises(HTTPException) as error:rollback_import(self.db,result['batch_id'],self.uid,self.scope)
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),2)
        self.assertEqual(self.db.query(ArchiveChange).count(),1)

if __name__=='__main__':
    suite=unittest.TestSuite(SerialImports(n) for n in SerialImports.__dict__ if n.startswith('test_'))
    result=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(not result.wasSuccessful())
