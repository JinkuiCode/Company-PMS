"""Compile actual serial checks using MSSQL; execute data reads on fresh SQLite.
This does NOT prove real SQL Server collation, metadata grants or lock behavior.
"""
import unittest
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.dialects import mssql
import archive_change_contract
from app.core.database import Base
from app.services.archive_code_unique import lock_codes, require_identity_lock, LOCK_NAME
from app.services.archive_serial_unique import ensure_serial_available, identity_batch_conflicts
from fastapi import HTTPException

class Scalar:
    def __init__(self,value):self.value=value
    def scalar(self):return self.value
class Proxy:
    dialect=SimpleNamespace(name='mssql')
    def __init__(self,c,lock_result=0,collation='BINARY'):
        self.c=c;self.info=c.info;self.statements=[];self.lock_result=lock_result;self.collation=collation
    def get_transaction(self):return self.c.get_transaction()
    def execute(self,statement,parameters=None):
        compiled=statement.compile(dialect=mssql.dialect(),compile_kwargs={'render_postcompile':True})
        self.statements.append((str(compiled),parameters or compiled.params))
        if 'sp_getapplock' in str(statement):return Scalar(self.lock_result)
        if 'collation_name' in str(statement):return Scalar(self.collation)
        return self.c.execute(statement,parameters or {})

class Mssql(unittest.TestCase):
    def test_native_statements_are_bound_and_lock_is_same_transaction_resource(self):
        from archive_serial_namespace_contract import Namespace
        fixture=Namespace();fixture.setUp()
        try:
            with fixture.engine.connect() as c:
                c.begin();p=Proxy(c);lock_codes(p,field_key='serial_no');require_identity_lock(p)
                fixture.occupy(c,'draft',"x'--",'private');fixture.occupy(c,'pending','RESERVED','request')
                for value in ("X'--",'reserved'):
                    with self.assertRaises(HTTPException) as e:ensure_serial_available(p,value)
                    self.assertEqual(e.exception.status_code,409)
                self.assertEqual(identity_batch_conflicts(p,[{'serial_no':'RESERVED'},{'project_code':'PRIVATE'}]),[(0,'serial_no'),(1,'project_code')])
                self.assertEqual(sum('sp_getapplock' in sql for sql,_ in p.statements),1)
                for sql,params in p.statements:
                    self.assertNotIn("x'--",sql)
                    if 'sp_getapplock' in sql:
                        self.assertEqual(params,{'name':LOCK_NAME});self.assertIn("@LockOwner='Transaction'",sql)
                self.assertTrue(any('sys.columns' in sql for sql,_ in p.statements))
        finally:fixture.tearDown()
    def test_busy_unknown_or_invalid_metadata_fail_closed(self):
        engine=create_engine('sqlite://')
        with engine.connect() as c:
            c.begin()
            for result in (-1,-2,-3,-999,None):
                with self.assertRaises(HTTPException) as e:lock_codes(Proxy(c,lock_result=result),field_key='serial_no')
                self.assertEqual(e.exception.detail['code'],'ARCHIVE_SERIAL_BUSY')
        engine.dispose()

if __name__=='__main__':unittest.main(verbosity=2)
