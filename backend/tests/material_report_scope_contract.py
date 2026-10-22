from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch
from contextlib import nullcontext
from types import SimpleNamespace
from pathlib import Path
import tempfile
from threading import Event
import zipfile
from datetime import date,datetime
from decimal import Decimal as D
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.report_filters import parse_filters,sql_conditions,matches_filters,query_fields
from app.services.stock_detail_reader import StockDetailQuery
from app.services.stock_detail_material_query import material_predicate


def condition(field='material_code',values=None):
    return dict(schemaVersion=2,field=field,operator='reference',value=['0007-A','0008-B'] if values is None else values,valueEnd=None)


class MaterialScope(unittest.TestCase):
    def test_material_reference_is_string_membership_for_each_report(self):
        for report,field in [('purchase','material_code'),('inventory','MaterialCode')]:
            self.assertIn('reference',next(f for f in query_fields(report) if f['field']==field)['operators'])
            conditions=parse_filters(json.dumps([condition(field)]),report)
            sql,params=sql_conditions(conditions)
            self.assertIn(' IN ',sql);self.assertEqual([p for p in params if p],['0007-a','0008-b'])
            self.assertTrue(matches_filters({field:' 0008-B '},conditions))
            self.assertFalse(matches_filters({field:'0009'},conditions))

    def test_stock_codes_bound_full_scope_and_legacy_text_is_compatible(self):
        self.assertIn('material_codes',StockDetailQuery.model_fields)
        query=StockDetailQuery(material_codes=['0007-A','0008-B'],organization_ids=[11],start_date='2026-10-01',end_date='2026-10-20')
        sql,params=material_predicate(query)
        self.assertIn(' IN ',sql);self.assertEqual([p for p in params if p],['0007-a','0008-b'])
        from app.services.stock_detail_snapshots import snapshot_sql
        from datetime import date
        snap,snap_params=snapshot_sql(query,11,date(2026,9,30),0)
        self.assertIn(sql,snap);self.assertEqual(snap_params[3:3+len(params)],params)
        old=StockDetailQuery(material='0007',organization_ids=[11],start_date='2026-10-01',end_date='2026-10-20')
        self.assertIn('LIKE',material_predicate(old)[0])

    def test_invalid_or_duplicate_primary_scopes_cannot_fall_back_to_all(self):
        base=dict(organization_ids=[11],start_date='2026-10-01',end_date='2026-10-20')
        for extra in [dict(material_codes=[]),dict(material_codes=['']),dict(material_codes=[7]),dict(material='A',material_codes=['B']),dict(material_codes=['A'],filters=json.dumps([condition()]))]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):StockDetailQuery(**base,**extra)

    def test_purchase_sql_collection_matches_union_of_single_codes_and_overview_counts(self):
        from purchase_reader_contract import ReaderContract,GRANTS
        from app.services.purchase_reader import PurchaseQuery,PurchaseOverviewQuery,list_requests,list_overview
        fixture=ReaderContract();db,connection=fixture.classification_fixture();self.addCleanup(fixture.doCleanups)
        db.execute("INSERT INTO T_BD_MATERIAL(FMATERIALID,FNUMBER) VALUES (10,'0007-A'),(20,'0008-B')")
        for table,column in [('T_PUR_REQENTRY','FENTRYID'),('T_PUR_POORDERENTRY','FENTRYID'),('T_STK_INSTOCKENTRY','FENTRYID')]:
            db.execute(f'UPDATE {table} SET FMATERIALID=20 WHERE {column}>=5')
        def query(codes,overview=False):
            model=PurchaseOverviewQuery if overview else PurchaseQuery
            return model(filters=json.dumps([condition(values=codes)]))
        singles=[list_requests(connection,query([code]),GRANTS) for code in ['0007-A','0008-B']]
        combined=list_requests(connection,query(['0007-A','0008-B']),GRANTS)
        self.assertEqual({r['id'] for r in combined['items']},set().union(*[{r['id'] for r in result['items']} for result in singles]))
        self.assertEqual(combined['total'],sum(r['total'] for r in singles))
        overview=list_overview(connection,query(['0007-A','0008-B'],True),GRANTS)
        self.assertEqual(sum(r['total_lines'] for r in overview['items']),combined['total'])

    def test_stock_multi_material_balances_openings_and_export_equal_per_code(self):
        from app.services.stock_detail_balance import InventoryKey
        from app.services.stock_detail_reader import assemble_page
        from app.services.stock_detail_engine import export_rows,quantity_summary
        keys=[InventoryKey(11,10,20,10000,'BD_OwnerOrg',11,10087),InventoryKey(11,20,21,10000,'BD_OwnerOrg',11,10087)]
        openings={keys[0]:D('5'),keys[1]:D('40')}
        rows=[dict(inventory_key=key,row_id=f'{index}:{n}',bill_date=date(2026,10,n),created_at=datetime(2026,10,n),
            source_order=0,bill_no=f'X{n}',bill_seq=n,material_code=code,income_qty=income,issue_qty=issue)
            for index,(key,code) in enumerate(zip(keys,['0007-A','0008-B'])) for n,income,issue in [(1,D(6),D(0)),(2,D(0),D(4))]]
        labels={key:dict(material_code=code,unit_name='个') for key,code in zip(keys,['0007-A','0008-B'])}
        query=StockDetailQuery(material_codes=['0007-A','0008-B'],organization_ids=[11],start_date='2026-10-01',end_date='2026-10-20',page_size=500)
        combined=assemble_page(query,rows,openings,opening_date=query.start_date,opening_labels=labels)
        per_code=[]
        for key,code in zip(keys,['0007-A','0008-B']):
            selected=[r for r in rows if r['inventory_key']==key]
            result=assemble_page(query.model_copy(update={'material_codes':[code.lower()]}),selected,{key:openings[key]},opening_date=query.start_date,opening_labels=labels)
            per_code.extend(result['items'])
        signature=lambda values:sorted((r['row_id'],r['balance_qty']) for r in values)
        self.assertEqual(signature(combined['items']),signature(per_code))
        self.assertEqual({r['material_code']:r['balance_qty'] for r in combined['items'] if r['bill_seq']==2},{'0007-A':D(7),'0008-B':D(42)})
        dataset=dict(rows=rows,openings=openings,labels=labels)
        exported=list(export_rows(dataset,query.start_date))
        self.assertEqual(len(exported),len(rows)+len(openings))
        self.assertEqual({(r['material_code'],r['balance_qty']) for r in exported if r['bill_seq']==2},{('0007-A',D(7)),('0008-B',D(42))})
        self.assertIsNone(quantity_summary(dataset),'existing heterogeneous-dimension protection must not sum unrelated materials')

    def test_all_stock_movement_sql_uses_same_exact_material_predicate(self):
        from app.services.stock_detail_sources import movement_queries
        query=StockDetailQuery(material_codes=['0007-A','0008-B'],organization_ids=[11],start_date='2026-10-01',end_date='2026-10-20')
        predicate,bound=material_predicate(query)
        for form in ['PRD_PICKMTRL','STK_TRANSFERDIRECT','STK_INVINIT']:
            for _,sql,params in movement_queries(form,query,[11]):
                self.assertIn(predicate,sql)
                for code in ['0007-a','0008-b']:self.assertIn(code,params)

    def test_inventory_sql_filters_all_codes_before_paging_and_scope(self):
        import sqlite3
        from app.services.inventory_reader import InventoryQuery,where_clause
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.execute("ATTACH DATABASE ':memory:' AS dbo")
        db.execute('CREATE TABLE dbo.T_STK_INVENTORY(FID,FSTOCKORGID)')
        db.executemany('INSERT INTO dbo.T_STK_INVENTORY VALUES (?,?)',[(1,11),(2,11),(3,99),(4,11)])
        query=InventoryQuery(filters=json.dumps([condition('MaterialCode')]))
        sql,params=where_clause(query,[11])
        rows=db.execute("SELECT v.FID FROM (SELECT 1 AS FID,'0007-A' AS MaterialCode UNION ALL SELECT 2,'0008-B' UNION ALL SELECT 3,'0007-A' UNION ALL SELECT 4,'OTHER') v"+sql.replace('dbo.','dbo.').replace('%s','?'),params).fetchall()
        self.assertEqual(rows,[(1,),(2,)])

    def test_stock_validation_stays_inside_existing_snapshot_transaction(self):
        from stock_detail_fetch_contract import Connection,FetchContract
        from app.services.stock_detail_fetch import read_dataset
        from app.services.stock_detail_baseline import Baseline
        c=Connection([[{'snapshot_isolation_state':1}],FetchContract().registry(),[]])
        query=StockDetailQuery(material_codes=['0007-A','0008-B'],organization_ids=[11],start_date='2026-10-01',end_date='2026-10-20')
        positions=[]
        with patch('app.services.report_material_reference.require_material_codes',side_effect=lambda *args:positions.append((len(c.cur.calls),c.rollbacks,args[1],args[2]))),patch('app.services.stock_detail_fetch.load_baseline',return_value=Baseline(date(2026,1,1))):
            read_dataset(c,query,[11])
        self.assertEqual(positions,[(2,2,['0007-a','0008-b'],[11])])


class MaterialExportScope(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.core.database import Base
        import app.models.init_db
        from material_reference_contract import Cursor
        self.engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(self.engine)
        self.db=Session(self.engine);self.addCleanup(self.engine.dispose);self.addCleanup(self.db.close)
        self.c=Cursor();self.c.add('0007-A','甲');self.c.add('0008-B','乙')
        self.connection=SimpleNamespace(cursor=lambda:self.c)
        self.ctx={'user_id':7,'permissions':['report:inventory:view','report:inventory:export']}

    def test_legacy_inventory_text_export_does_not_open_material_connection(self):
        from app.services import report_export_jobs as jobs
        with patch.object(jobs,'scope_signature',return_value='scope'),patch('app.services.purchase_connection.purchase_connection') as connect:
            job=jobs.create_job(self.db,self.ctx,'inventory',{'filters':json.dumps([dict(field='MaterialCode',operator='contains',value='0007')])},['MaterialCode'])
            self.assertEqual(job.status,'queued');connect.assert_not_called()

    def test_create_worker_and_workbook_retain_collection_and_run_once(self):
        from app.services import report_export_jobs as jobs
        from app.services.report_material_reference import validate_reference_query
        captured=[]
        def batches(connection,query,organizations):
            validate_reference_query(connection,query,organizations)
            captured.append(query.conditions()[0].value)
            yield [dict(MaterialCode=code) for code in query.conditions()[0].value]
        with tempfile.TemporaryDirectory() as folder,patch.object(jobs,'EXPORT_ROOT',Path(folder)),patch.object(jobs,'scope_signature',return_value='scope'),patch.object(jobs,'build_authorization_context',return_value=self.ctx),patch('app.api.inventory_reports.authorized_organizations',return_value=[11]),patch('app.services.inventory_reader.resolve_product_lines'),patch('app.services.purchase_connection.purchase_connection',return_value=nullcontext(self.connection)),patch('app.services.report_export_data.purchase_connection',return_value=nullcontext(self.connection)),patch('app.services.report_export_data.inventory_batches',batches):
            params={'filters':json.dumps([condition('MaterialCode')])}
            job=jobs.create_job(self.db,self.ctx,'inventory',params,['MaterialCode'])
            with self.assertRaises(Exception):jobs.create_job(self.db,self.ctx,'inventory',params,['MaterialCode'])
            jobs.run_next(self.db,Event());self.assertEqual(job.status,'success',job.message)
            self.assertEqual(captured,[['0007-a','0008-b']]);self.assertEqual(job.processed,2)
            self.assertEqual(json.loads(job.parameters)['filters'],params['filters'])
            with zipfile.ZipFile(jobs.job_file(job)) as archive:
                xml=archive.read('xl/worksheets/sheet1.xml').decode()
                self.assertIn('0007-a',xml);self.assertIn('0008-b',xml)
            jobs.run_next(self.db,Event());self.assertEqual(len(captured),1)

    def test_deleted_reference_between_submission_and_execution_fails_without_partial_file(self):
        from app.services import report_export_jobs as jobs
        from app.services.report_material_reference import validate_reference_query
        def batches(connection,query,organizations):
            validate_reference_query(connection,query,organizations)
            yield []
        with tempfile.TemporaryDirectory() as folder,patch.object(jobs,'EXPORT_ROOT',Path(folder)),patch.object(jobs,'scope_signature',return_value='scope'),patch.object(jobs,'build_authorization_context',return_value=self.ctx),patch('app.api.inventory_reports.authorized_organizations',return_value=[11]),patch('app.services.inventory_reader.resolve_product_lines'),patch('app.services.purchase_connection.purchase_connection',return_value=nullcontext(self.connection)),patch('app.services.report_export_data.purchase_connection',return_value=nullcontext(self.connection)),patch('app.services.report_export_data.inventory_batches',batches):
            job=jobs.create_job(self.db,self.ctx,'inventory',{'filters':json.dumps([condition('MaterialCode')])},['MaterialCode'])
            self.c.db.execute("DELETE FROM dbo.T_BD_MATERIAL WHERE FNUMBER='0008-B'")
            jobs.run_next(self.db,Event())
            self.assertEqual(job.status,'failed');self.assertFalse(jobs.job_file(job).exists())


if __name__=='__main__':unittest.main()
