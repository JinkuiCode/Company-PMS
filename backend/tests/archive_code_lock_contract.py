"""Two real SQLite connections and the production SQL Server lock contract."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from sqlalchemy import create_engine
from app.services.archive_code_unique import ensure_code_available, lock_codes, LOCK_NAME


class CodeLock(unittest.TestCase):
    def setUp(self):
        self.folder=TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.engine=create_engine('sqlite:///'+str(Path(self.folder.name)/'isolated.db'))
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as c:
            c.exec_driver_sql('CREATE TABLE pms_project_archive (id INTEGER PRIMARY KEY, project_code_key TEXT UNIQUE)')
            c.exec_driver_sql('CREATE TABLE pms_form_draft (id TEXT PRIMARY KEY, resource TEXT, status TEXT, payload_json TEXT)')

    def test_concurrent_saves_cannot_both_claim_code(self):
        for first_kind,second_kind in [('draft','draft'),('draft','archive'),('archive','draft')]:
            with self.subTest(first=first_kind,second=second_kind):
                code=first_kind+'-'+second_kind
                with self.engine.connect() as first:
                    ensure_code_available(first,code)
                    if first_kind=='draft':
                        first.exec_driver_sql("INSERT INTO pms_form_draft VALUES (?,?,?,?)",(code,'archive-create','active',json.dumps({'project_code':code})))
                    else:
                        first.exec_driver_sql('INSERT INTO pms_project_archive(project_code_key) VALUES (?)',(code,))
                    started=Event()
                    def second_save():
                        with self.engine.connect() as second:
                            started.set()
                            try:
                                ensure_code_available(second,code.upper())
                                return 'unexpected-success'
                            except HTTPException as error:
                                return error.status_code,error.detail['code']
                    with ThreadPoolExecutor(max_workers=1) as workers:
                        pending=workers.submit(second_save)
                        self.assertTrue(started.wait(2))
                        self.assertFalse(pending.done())
                        first.commit()
                        self.assertEqual(pending.result(3),(409,'ARCHIVE_UNIQUE_CONFLICT'))

    def test_rollback_releases_namespace_without_leaving_claim(self):
        with self.engine.connect() as first:
            ensure_code_available(first,'ROLLED-BACK')
            first.exec_driver_sql("INSERT INTO pms_form_draft VALUES ('rollback','archive-create','active',?)",(json.dumps({'project_code':'ROLLED-BACK'}),))
            first.rollback()
        with self.engine.connect() as second:
            ensure_code_available(second,'rolled-back')

    def test_mssql_application_lock_is_transaction_owned_and_fail_closed(self):
        for result in (0,1,-1,-2,-3,-999,None):
            connection=Mock(dialect=SimpleNamespace(name='mssql'))
            connection.info={}
            connection.get_transaction.return_value=SimpleNamespace(is_active=True)
            connection.execute.return_value.scalar.return_value=result
            if result is None or result<0:
                with self.assertRaises(HTTPException) as failure:lock_codes(connection)
                self.assertEqual(failure.exception.status_code,409)
                self.assertEqual(failure.exception.detail['code'],'ARCHIVE_CODE_BUSY')
            else:lock_codes(connection)
            statement,parameters=connection.execute.call_args.args
            self.assertIn("@LockOwner='Transaction'",str(statement))
            self.assertIn("@LockMode='Exclusive'",str(statement))
            self.assertIn('@LockTimeout=1000',str(statement))
            self.assertEqual(parameters,{'name':LOCK_NAME})

    def test_mssql_comparison_uses_bound_unicode_values(self):
        from sqlalchemy.dialects import mssql
        from sqlalchemy import select,literal
        statement=select(literal(1)).where(literal('code').in_(['ＦＯＯ',"x'--"]))
        compiled=statement.compile(dialect=mssql.dialect(),compile_kwargs={'render_postcompile':True})
        self.assertNotIn("x'--",str(compiled))
        self.assertIn("x'--",compiled.params.values())


if __name__=='__main__':unittest.main()
