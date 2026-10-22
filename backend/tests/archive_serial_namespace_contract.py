"""Transaction guard, three-way contention and native collation on disposable SQLite."""
import json
import tempfile
import unittest
from pathlib import Path
from sqlalchemy import create_engine, insert, text, update
from sqlalchemy.orm import Session
from fastapi import HTTPException
import archive_change_contract
from app.core.database import Base
from app.models.project import PmsProjectArchive
from app.models.form_draft import PmsFormDraft
from app.models.archive_change import ArchiveChange
from app.services.archive_code_unique import lock_codes, LOCK_NAME


class Namespace(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.engine=create_engine('sqlite:///'+str(Path(self.tmp.name)/'isolated.db'),connect_args={'timeout':0.02})
        Base.metadata.create_all(self.engine)
    def tearDown(self):self.engine.dispose();self.tmp.cleanup()
    def formal(self,connection,code,serial):
        return connection.execute(insert(PmsProjectArchive).values(project_code=code,project_code_key=code.casefold(),serial_no=serial,serial_no_key=serial.strip().casefold())).inserted_primary_key[0]
    def occupy(self,connection,kind,serial,code):
        if kind=='formal':self.formal(connection,code,serial)
        elif kind=='draft':connection.execute(insert(PmsFormDraft).values(id=code,owner_id=1,resource='archive-create',payload_json=json.dumps({'project_code':code,'serial_no':serial}),status='active'))
        else:
            aid=self.formal(connection,code+'-formal','OLD-'+code)
            connection.execute(insert(ArchiveChange).values(archive_id=aid,active_archive_id=aid,submission_id=code,request_hash='hash',author_id=1,approver_id=2,department_id=1,base_version='v',updates_json=json.dumps({'serial_no':serial}),differences_json='[]',reason='合成',status=2))
    def test_raw_orm_insert_and_identity_update_fail_closed_without_outer_lock(self):
        with Session(self.engine) as db:
            db.add(PmsProjectArchive(project_code='RAW',project_name='合成'))
            with self.assertRaises(HTTPException) as e:db.flush()
            self.assertEqual(e.exception.detail['code'],'ARCHIVE_IDENTITY_LOCK_REQUIRED');db.rollback()
            lock_codes(db.connection());row=PmsProjectArchive(project_code='VALID',serial_no='ONE');db.add(row);db.commit()
            row.serial_no='TWO'
            with self.assertRaises(HTTPException) as e:db.flush()
            self.assertEqual(e.exception.detail['code'],'ARCHIVE_IDENTITY_LOCK_REQUIRED');db.rollback()
            row.project_name='非身份更新';db.commit()
    def test_two_connections_all_reservation_kinds_commit_rollback_and_busy(self):
        from app.services.archive_serial_unique import ensure_serial_available
        for kind in ('formal','draft','pending'):
            for committed in (False,True):
                serial=f'{kind}-{committed}'
                with self.subTest(kind=kind,committed=committed),self.engine.connect() as a,self.engine.connect() as b:
                    lock_codes(a);ensure_serial_available(a,serial);self.occupy(a,kind,serial,serial)
                    with self.assertRaises(HTTPException) as e:lock_codes(b,field_key='serial_no')
                    self.assertEqual(e.exception.detail['code'],'ARCHIVE_SERIAL_BUSY');b.rollback()
                    a.commit() if committed else a.rollback()
                    lock_codes(b)
                    if committed:
                        with self.assertRaises(HTTPException) as e:ensure_serial_available(b,serial.upper())
                        self.assertEqual(e.exception.detail['field_key'],'serial_no')
                    else:ensure_serial_available(b,serial)
                    b.rollback()
    def test_lock_marker_does_not_survive_commit_rollback_or_pool_reuse(self):
        from app.services.archive_code_unique import require_identity_lock
        with self.engine.connect() as c:
            lock_codes(c);require_identity_lock(c);c.commit();c.begin()
            with self.assertRaises(HTTPException):require_identity_lock(c)
            lock_codes(c);c.rollback();c.begin()
            with self.assertRaises(HTTPException):require_identity_lock(c)
        with self.engine.connect() as c:
            c.begin()
            with self.assertRaises(HTTPException):require_identity_lock(c)
    def test_existing_deferred_read_transaction_must_acquire_real_writer_lock(self):
        with self.engine.connect() as reader,self.engine.connect() as writer:
            reader.exec_driver_sql('BEGIN')
            reader.execute(text('SELECT count(*) FROM pms_project_archive')).scalar()
            lock_codes(writer,field_key='serial_no')
            with self.assertRaises(HTTPException) as e:lock_codes(reader,field_key='serial_no')
            self.assertEqual(e.exception.detail['code'],'ARCHIVE_SERIAL_BUSY')
            reader.rollback();writer.rollback()

    def test_damaged_pending_json_or_active_state_fails_closed(self):
        from app.services.archive_serial_unique import ensure_serial_available
        with self.engine.connect() as c:
            lock_codes(c);self.occupy(c,'pending','SAFE','one');c.commit()
            for changes in ({'updates_json':'[]'},{'updates_json':'{"serial_no":17}'},{'updates_json':'{}','status':3},{'updates_json':'{}','status':2,'active_archive_id':None}):
                lock_codes(c);c.execute(update(ArchiveChange).values(**changes))
                with self.assertRaises(HTTPException) as e:ensure_serial_available(c,'OTHER')
                self.assertEqual(e.exception.status_code,503);c.rollback()
    def test_column_collation_is_used_for_json_reservations(self):
        from app.services.archive_serial_unique import ensure_serial_available
        with self.engine.connect() as c:
            # Synthetic alternative collation distinguishes internal underscores;
            # width/accent behavior is delegated to the actual database collation.
            c.connection.driver_connection.create_collation('SERIAL_TEST',lambda a,b:(a.replace('_','')>b.replace('_',''))-(a.replace('_','')<b.replace('_','')))
            ddl=c.scalar(text("SELECT sql FROM sqlite_master WHERE name='pms_project_archive'"))
            c.execute(text('DROP TABLE pms_project_archive'))
            ddl=ddl.replace('serial_no_key NVARCHAR(64)','serial_no_key NVARCHAR(64) COLLATE SERIAL_TEST')
            self.assertIn('COLLATE SERIAL_TEST',ddl);c.exec_driver_sql(ddl);c.commit()
            lock_codes(c);self.occupy(c,'draft','A_B','COLLATE');c.commit();lock_codes(c)
            with self.assertRaises(HTTPException) as e:ensure_serial_available(c,'ab')
            self.assertEqual(e.exception.status_code,409)
            from app.services.archive_serial_unique import identity_batch_conflicts
            proposals=[{'serial_no':('X_Y' if i==0 else 'xy' if i==150 else 'unique-'+str(i))} for i in range(151)]
            self.assertEqual(identity_batch_conflicts(c,proposals),[(0,'serial_no'),(150,'serial_no')])


if __name__=='__main__':unittest.main(verbosity=2)
