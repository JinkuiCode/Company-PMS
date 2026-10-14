import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.schema import CreateIndex
from sqlalchemy.dialects import mssql
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
TMP=tempfile.TemporaryDirectory();os.environ['DB_DIALECT']='sqlite';os.environ['SQLITE_DB_PATH']=str(Path(TMP.name)/'unused.db')
from app.core.database import Base
import app.models.init_db
from app.models.archive_change import ArchiveChange
from app.models.database_revision import PmsDatabaseRevision
from app.models.user import SysUser
from app.models.project import PmsProjectArchive,PmsProject,PmsTask
from app.services.archive_governance_migration import upgrade_archive_governance,REVISION


class GovernanceUpgrade(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        ArchiveChange.__table__.drop(self.engine)
        with self.engine.begin() as c:
            columns={row['name'] for row in inspect(c).get_columns('pms_project_archive')}
            for name in ('plan_start_date','plan_end_date'):
                if name not in columns:c.exec_driver_sql(f'ALTER TABLE pms_project_archive ADD {name} DATETIME NULL')
            c.execute(PmsDatabaseRevision.__table__.insert().values(id=1,revision='2026-10-12-feedback-02'))
            c.execute(SysUser.__table__.insert().values(id=1,username='original',real_name='原人员',password_hash='unchanged',status=1))
            c.execute(PmsProjectArchive.__table__.insert().values(id=1,project_code='OLD',project_code_key='old',project_name='历史',manager_id=1))
            c.execute(PmsProject.__table__.insert().values(id=1,project_code='OLD',project_name='历史',archive_id=1,dept_id=1,pm_id=1,start_date=datetime(2026,1,1),end_date=datetime(2026,12,1)))
            c.execute(PmsTask.__table__.insert().values(id=1,project_id=1,task_name='原计划',start_date=datetime(2026,2,1)))
            c.exec_driver_sql("UPDATE pms_project_archive SET plan_start_date='2026-01-01',plan_end_date='2026-12-01' WHERE id=1")
            if 'governance_legacy' in {row['name'] for row in inspect(c).get_columns('pms_project_archive')}:
                c.exec_driver_sql('ALTER TABLE pms_project_archive DROP COLUMN governance_legacy')
    def tearDown(self):self.engine.dispose()
    def test_bounded_upgrade_preserves_users_and_manager_and_removes_only_archive_plans(self):
        upgrade_archive_governance(self.engine)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT revision FROM pms_database_revision')).scalar(),REVISION)
            self.assertEqual(c.execute(text('SELECT manager_id FROM pms_project_archive')).scalar(),1)
            self.assertEqual(c.execute(text('SELECT governance_legacy FROM pms_project_archive')).scalar(),1)
            self.assertEqual(c.execute(text('SELECT password_hash FROM sys_user')).scalar(),'unchanged')
            self.assertIn('2026-01-01',c.execute(text('SELECT start_date FROM pms_project')).scalar())
            self.assertIn('2026-12-01',c.execute(text('SELECT end_date FROM pms_project')).scalar())
            self.assertIn('2026-02-01',c.execute(text('SELECT start_date FROM pms_task')).scalar())
            cutoff=c.execute(text("SELECT required_effective_at FROM sys_business_field_policy WHERE module_code='project_archive' AND field_key='archive_category'")).scalar()
        columns={row['name'] for row in inspect(self.engine).get_columns('pms_project_archive')}
        self.assertNotIn('plan_start_date',columns);self.assertNotIn('plan_end_date',columns)
        self.assertTrue(inspect(self.engine).has_table('pms_archive_change'))
        upgrade_archive_governance(self.engine)
        with self.engine.connect() as c:self.assertEqual(c.execute(text("SELECT required_effective_at FROM sys_business_field_policy WHERE module_code='project_archive' AND field_key='archive_category'")).scalar(),cutoff)

    def test_followup_preserves_original_times_and_does_not_remark_new_records(self):
        from app.services.archive_governance_migration import install_archive_governance,_drop_archive_plan_columns
        from sqlalchemy.orm import Session
        with self.engine.begin() as c:
            ArchiveChange.__table__.create(c)
            db=Session(bind=c);install_archive_governance(db);db.close()
            _drop_archive_plan_columns(c)
            c.execute(text("UPDATE pms_database_revision SET revision='2026-10-14-archive-governance-01'"))
            original=c.execute(text('SELECT created_at,updated_at FROM pms_project_archive')).one()
        upgrade_archive_governance(self.engine)
        with self.engine.begin() as c:
            self.assertEqual(c.execute(text('SELECT created_at,updated_at FROM pms_project_archive')).one(),original)
            self.assertEqual(c.execute(text('SELECT governance_legacy FROM pms_project_archive')).scalar(),1)
            c.execute(PmsProjectArchive.__table__.insert().values(project_code='NEW',project_code_key='new'))
        upgrade_archive_governance(self.engine)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT governance_legacy FROM pms_project_archive WHERE project_code='NEW'")).scalar(),0)
    def test_failure_rolls_back_ddl_and_revision(self):
        with patch('app.services.archive_governance_migration.install_archive_governance',side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError,'injected'):upgrade_archive_governance(self.engine)
        self.assertFalse(inspect(self.engine).has_table('pms_archive_change'))
        self.assertIn('plan_start_date',{row['name'] for row in inspect(self.engine).get_columns('pms_project_archive')})
        with self.engine.connect() as c:self.assertEqual(c.execute(text('SELECT revision FROM pms_database_revision')).scalar(),'2026-10-12-feedback-02')
    def test_mssql_active_index_is_filtered(self):
        index=next(index for index in ArchiveChange.__table__.indexes if index.name=='uq_archive_change_active')
        ddl=str(CreateIndex(index).compile(dialect=mssql.dialect()))
        self.assertIn('UNIQUE',ddl);self.assertIn('WHERE active_archive_id IS NOT NULL',ddl)
    def test_failure_after_marker_update_restores_original_schema_and_values(self):
        with self.engine.connect() as c:
            original=c.execute(text('SELECT manager_id,created_at,updated_at FROM pms_project_archive')).one()
        with patch('app.services.archive_governance_migration._verify',side_effect=RuntimeError('after-marker')):
            with self.assertRaisesRegex(RuntimeError,'after-marker'):upgrade_archive_governance(self.engine)
        self.assertNotIn('governance_legacy',{row['name'] for row in inspect(self.engine).get_columns('pms_project_archive')})
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT manager_id,created_at,updated_at FROM pms_project_archive')).one(),original)
            self.assertEqual(c.execute(text('SELECT revision FROM pms_database_revision')).scalar(),'2026-10-12-feedback-02')
    def test_target_version_refuses_invalid_active_index_and_enum(self):
        upgrade_archive_governance(self.engine)
        with self.engine.begin() as c:
            c.exec_driver_sql('DROP INDEX uq_archive_change_active')
            c.exec_driver_sql('CREATE UNIQUE INDEX uq_archive_change_active ON pms_archive_change(active_archive_id)')
        with self.assertRaisesRegex(RuntimeError,'活动.*索引'):upgrade_archive_governance(self.engine)
    def test_active_index_cannot_add_a_predicate_that_excludes_pending(self):
        upgrade_archive_governance(self.engine)
        with self.engine.begin() as c:
            c.exec_driver_sql('DROP INDEX uq_archive_change_active')
            c.exec_driver_sql('CREATE UNIQUE INDEX uq_archive_change_active ON pms_archive_change(active_archive_id) WHERE active_archive_id IS NOT NULL AND status=3')
        with self.assertRaisesRegex(RuntimeError,'活动.*索引'):upgrade_archive_governance(self.engine)

if __name__=='__main__':unittest.main()
