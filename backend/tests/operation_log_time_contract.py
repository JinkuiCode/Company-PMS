"""Log reads and date predicates share the business clock; storage is unchanged."""
import sys
import unittest
import datetime as dt
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import system_list_query_contract as fixture
from app.models.operation_log import SysOperationLog
from app.services import operation_log
from app.services.document_history import get_document_history


class LogTime(unittest.TestCase):
    setUp = fixture.SystemListQueryContract.setUp
    tearDown = fixture.SystemListQueryContract.tearDown

    def samples(self):
        self.db.query(SysOperationLog).delete()
        self.ctx['permissions'].append('project:archive:view')
        times = [(14,15,59,59),(14,16,0,0),(15,0,10,0),(15,15,59,59),(15,16,0,0)]
        for name, (day,hour,minute,second) in zip(('previous','start','middle','end','next'), times):
            self.db.add(SysOperationLog(module='项目档案', action='update',
                entity_type='pms_project_archive',entity_id=str(self.visible.id),
                summary=name,entity_name=name,created_at=dt.datetime(2026,10,day,hour,minute,second)))
        self.db.commit()
        return {r.id:r.created_at for r in self.db.query(SysOperationLog)}

    def names(self, **params):
        return {r['entity_name'] for r in operation_log.get_operation_logs(self.db,**params)['items']}

    def test_display_and_document_history_convert_once_without_changing_storage(self):
        before=self.samples()
        audit=operation_log.get_operation_logs(self.db)
        first=next(r for r in audit['items'] if r['entity_name']=='start')
        actual=dt.datetime.fromisoformat(str(first['created_at']))
        self.assertEqual(actual,dt.datetime(2026,10,15,tzinfo=dt.timezone(dt.timedelta(hours=8))))
        doc=get_document_history(self.db,'archive',self.visible.id,self.ctx)
        row=next(r for r in doc['items'] if r['id']==first['id'])
        self.assertEqual(row['created_at'],actual)
        self.db.expire_all()
        self.assertEqual({r.id:r.created_at for r in self.db.query(SysOperationLog)},before)

    def test_business_date_conditions_cover_the_complete_local_day(self):
        self.samples()
        for op,expected in [('equals',{'start','middle','end'}),('notEquals',{'previous','next'}),
                            ('lessThan',{'previous'}),('greaterThan',{'next'})]:
            self.assertEqual(self.names(filters=[fixture.condition('created_at',op,'2026-10-15')]),expected,op)

    def test_business_date_candidates_and_column_selection_agree(self):
        self.samples()
        result=operation_log.get_operation_log_column_values(self.db,field='created_at')
        self.assertEqual([(r['value'],r['count']) for r in result['items']],
            [('2026-10-14',1),('2026-10-15',3),('2026-10-16',1)])
        self.assertEqual(self.names(column_filters=[fixture.values('created_at','2026-10-15')]),{'start','middle','end'})

    def test_naive_business_and_explicit_timezone_bounds_match(self):
        self.samples()
        start=dt.datetime(2026,10,15);end=dt.datetime(2026,10,15,23,59,59)
        for zone in (None,dt.timezone(dt.timedelta(hours=8))):
            self.assertEqual(self.names(start_time=start.replace(tzinfo=zone),end_time=end.replace(tzinfo=zone)),{'start','middle','end'})
        zone=dt.timezone(dt.timedelta(hours=8))
        self.assertEqual(self.names(start_time=start.replace(tzinfo=zone).astimezone(dt.timezone.utc),
            end_time=end.replace(tzinfo=zone).astimezone(dt.timezone.utc)),{'start','middle','end'})

    def test_mssql_date_expression_keeps_existing_database_clock(self):
        db=SimpleNamespace(get_bind=lambda:SimpleNamespace(dialect=SimpleNamespace(name='mssql')))
        self.assertTrue(operation_log.operation_log_columns(db)['created_at'][0].compare(SysOperationLog.created_at.__clause_element__()))

    def test_aware_display_is_not_converted_twice_and_mssql_output_is_untouched(self):
        from app.services.operation_log_time import display_time,query_time
        value=dt.datetime(2026,10,15,12,tzinfo=dt.timezone(dt.timedelta(hours=8)))
        self.assertEqual(display_time(self.db,value),value)
        db=SimpleNamespace(get_bind=lambda:SimpleNamespace(dialect=SimpleNamespace(name='mssql')))
        naive=value.replace(tzinfo=None)
        self.assertIs(display_time(db,naive),naive)
        self.assertIs(query_time(db,naive),naive)


if __name__=='__main__':unittest.main()
