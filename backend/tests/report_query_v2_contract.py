"""Offline report query integration, without credentials or external databases."""
import json
from datetime import date
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import purchase_reader_contract as fixture
from purchase_typed_progress_contract import Connection as ExportConnection, ExportCursor
import re
import sqlite3
import tempfile
import zipfile
from xml.etree import ElementTree as ET
from app.services import purchase_reader as purchase
from app.services.inventory_reader import InventoryQuery, where_clause
from app.services.stock_detail_reader import StockDetailQuery
from app.services.report_filters import matches_filters
from app.services.business_data_scope import ALL_DATA_SCOPE
import purchase_api_contract as api_fixture


class V2Cursor(ExportCursor):
    def execute(self, sql, params=()):
        sql = re.sub(r'CAST\(NULL AS nvarchar\(\d+\)\)', 'NULL', sql, flags=re.I)
        sql = re.sub(r'CAST\((\w+\.\[\w+\]) AS (?:DATE|date)\)', r'date(\1)', sql)
        sql = sql.replace("%s + '%%'", "%s || '%%'").replace("'%%' + %s", "'%%' || %s")
        super().execute(sql.replace('CAST(value AS nvarchar(256))', 'value'), params)

    def fetchmany(self, size):
        return [dict(row) for row in self.cursor.fetchmany(size)]


class Connection(ExportConnection):
    def cursor(self):
        return V2Cursor(self.db)


def condition(field, operator, value=None, **extra):
    return json.dumps([dict(id=1, schemaVersion=2, field=field, operator=operator,
                           value=value, valueEnd=None, **extra)])


def column_condition(field, operator, value=None, **extra):
    return json.dumps([dict(field=field, mode='condition', condition=json.loads(condition(field, operator, value, **extra))[0])])


def column_values(field, values):
    return json.dumps([dict(field=field, mode='values', values=values)])


class ReportV2(unittest.TestCase):
    def setUp(self):
        self.source = fixture.ReaderContract()
        self.addCleanup(self.source.doCleanups)
        self.db, _ = self.source.classification_fixture()
        self.db.create_function('CONCAT', -1, lambda *args: ''.join(str(v) for v in args if v is not None))
        self.db.create_function('STUFF', 4, lambda s, start, length, replacement: s[:start-1] + replacement + s[start-1+length:] if s and start <= len(s) else None)
        self.db.execute('CREATE TABLE T_ORG_ORGANIZATIONS_L(FORGID,FLOCALEID,FNAME)')
        self.connection = Connection(self.db)

    def test_enum_multi_and_display_name_filter_before_paging(self):
        for operator, value, expected in [('in', ['C'], 9), ('notIn', ['C'], 0),
                                          ('reference', ['C'], 9), ('contains', '审核', 9)]:
            with self.subTest(operator=operator):
                query = purchase.PurchaseQuery(filters=condition('document_status', operator, value), page_size=1)
                result = purchase.list_requests(self.connection, query, ALL_DATA_SCOPE)
                self.assertEqual(result['total'], expected)

    def test_overview_column_filters_run_after_aggregation(self):
        query = purchase.PurchaseOverviewQuery(column_filters=column_condition('complete_lines', 'equals', 1))
        result = purchase.list_overview(self.connection, query, ALL_DATA_SCOPE)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['total_lines'], 9)
        self.assertAlmostEqual(float(result['items'][0]['completion_rate']), 100 / 9)
        query = purchase.PurchaseOverviewQuery(column_filters=column_condition('completion_rate', 'greaterThan', 12))
        self.assertEqual(purchase.list_overview(self.connection, query, ALL_DATA_SCOPE)['total'], 0)

    def test_detail_column_progress_filters_whole_result(self):
        query = purchase.PurchaseQuery(column_filters=column_condition('progress', 'reference', ['complete']), page_size=1)
        result = purchase.list_requests(self.connection, query, fixture.GRANTS)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['id'], 4)

    def test_inventory_v2_and_column_intersection(self):
        query = InventoryQuery(filters=condition('MaterialCode', 'startsWith', '001'),
                               column_filters=column_condition('FBaseQty', 'greaterOrEqual', 0))
        sql, params = where_clause(query, [100])
        self.assertIn('MaterialCode', sql)
        self.assertIn('FBaseQty', sql)
        self.assertEqual(sql.count('%s'), len(params))
        self.assertIn(Decimal(0), params)

    def test_explicit_v1_from_saved_report_plans_keeps_legacy_meaning(self):
        raw = '[{"field":"bill_no","operator":"equals","value":"R4","valueEnd":null,"schemaVersion":1}]'
        query = purchase.PurchaseQuery(filters=raw)
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 1)
        InventoryQuery(filters=raw.replace('bill_no', 'MaterialCode'))

    def test_stock_v2_after_balance_and_required_scope(self):
        args = dict(material='001', organization_ids=[100], start_date='2026-06-01', end_date='2026-06-30')
        query = StockDetailQuery(**args, column_filters=column_condition('bill_no', 'notContains', ' X '))
        self.assertFalse(matches_filters({'bill_no': 'AX'}, query.conditions()))
        self.assertTrue(matches_filters({'bill_no': ' AB '}, query.conditions()))
        for changes in ({'material': ''}, {'organization_ids': []},
                        {'start_date': '2026-07-01'}):
            with self.assertRaises(ValueError):
                StockDetailQuery(**{**args, **changes}, filters=condition('bill_no', 'isEmpty'))

    def test_unknown_versions_fields_and_extra_parameters_rejected(self):
        for model in (purchase.PurchaseQuery, InventoryQuery):
            for changes in ({'column_filters': condition('unknown', 'equals', 'x')},
                            {'filters': '[{"field":"bill_no","operator":"equals","value":"x","schemaVersion":3}]'},
                            {'unrecognized_parameter': 'x'}):
                with self.assertRaises(ValueError):
                    model(**changes)

    def test_project_array_legacy_and_reference_resolution_required(self):
        query = purchase.PurchaseQuery(project_codes=['P-1', 'P-2'])
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 9)
        self.assertEqual(purchase.list_requests(self.connection, purchase.PurchaseQuery(project_code='P-2'), fixture.GRANTS)['total'], 0)
        query = purchase.PurchaseQuery(filters=condition('project_code', 'reference', [17]))
        with self.assertRaises(ValueError):
            purchase.request_query(query, fixture.GRANTS)
        query._project_references = {17: ('P-1', 200)}
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 0)
        query._project_references = {17: ('P-1', 100)}
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 9)

    def test_project_reference_scoped_resolution_rejects_stale_or_foreign(self):
        from app.api import purchase_reports as api
        query = purchase.PurchaseQuery(filters=condition('project_name', 'reference', [17, 18]))
        scoped = Mock()
        scoped.join.return_value = scoped
        scoped.with_entities.return_value = scoped
        scoped.filter.return_value = scoped
        scoped.all.return_value = [(17, 'P-1', 100)]
        with patch.object(api, 'get_scoped_archive_query', return_value=scoped):
            with self.assertRaises(HTTPException) as error:
                api.resolve_project_references(None, {}, query)
            self.assertEqual(error.exception.status_code, 422)
            self.assertEqual(query._project_references, {})
            scoped.all.return_value = [(17, 'P-1', 100), (18, 'P-1', 200)]
            api.resolve_project_references(None, {}, query)
            self.assertEqual(query._project_references, {17: ('P-1', 100), 18: ('P-1', 200)})
        query = purchase.PurchaseQuery(organization_ids=[100], filters=condition('project_code', 'reference', [18]))
        scoped.all.return_value = [(18, 'P-1', 200)]
        with patch.object(api, 'get_scoped_archive_query', return_value=scoped), self.assertRaises(HTTPException):
            api.resolve_project_references(None, {}, query)

    def test_list_and_export_membership_share_column_conditions(self):
        from app.services.report_export_data import purchase_batches
        query = purchase.PurchaseQuery(column_filters=column_condition('progress', 'in', ['complete', 'ordering']), page_size=1)
        listed = purchase.list_requests(self.connection, query, fixture.GRANTS)
        exported = [row['id'] for batch in purchase_batches(self.connection, query, fixture.GRANTS) for row in batch]
        self.assertEqual(listed['total'], 3)
        self.assertEqual(set(exported), {2, 4, 7})

    def test_metadata_advertises_only_implemented_v2_fields(self):
        from app.services.report_filters import query_fields
        fields = {f['field']: f for f in query_fields('purchase')}
        self.assertIn('reference', fields['project_code']['operators'])
        self.assertIn('contains', fields['project_name']['operators'])
        self.assertIn('notIn', fields['document_status']['operators'])
        from app.services.purchase_fields import report_fields
        self.assertEqual(set(fields), {f['key'] for f in report_fields()})
        self.assertIn('completion_rate', {f['field'] for f in query_fields('purchase-overview')})

    def test_pms_labels_filter_before_page_and_share_export_and_candidates(self):
        from app.services.report_column_candidates import purchase_candidates
        from app.services.report_export_data import purchase_batches, overview_batches
        for model in (purchase.PurchaseQuery, purchase.PurchaseOverviewQuery):
            query = model(filters=condition('project_name', 'contains', ' pump '),
                          column_filters=column_values('product_line_name', ['Line A']), page_size=1)
            query._query_labels = {'project_name': {('P-1',100):'Pump One', ('P-1',200):'Secret'},
                                   'product_line_name': {100:'Line A',200:'Line B'}}
            read = purchase.list_overview if model is purchase.PurchaseOverviewQuery else purchase.list_requests
            result = read(self.connection, query, fixture.GRANTS)
            self.assertEqual(result['total'], 1 if model is purchase.PurchaseOverviewQuery else 9)
            candidates = purchase_candidates(self.connection, query, fixture.GRANTS, 'project_name', 'pump', 1, 1)
            self.assertEqual(candidates['items'], [{'value':'Pump One','label':'Pump One'}])
            export = overview_batches if model is purchase.PurchaseOverviewQuery else purchase_batches
            self.assertEqual(sum(len(b) for b in export(self.connection, query, fixture.GRANTS)), result['total'])
            negative = query.model_copy(update={'filters':condition('project_name','notContains','pump')})
            self.assertEqual(read(self.connection, negative, fixture.GRANTS)['total'], 0)

    def test_supplier_and_document_status_column_funnels_use_verified_full_chains(self):
        from app.services.report_column_candidates import purchase_candidates
        from app.services.report_export_data import purchase_batches
        self.db.execute("INSERT INTO T_BD_SUPPLIER_L(FSUPPLIERID,FLOCALEID,FNAME) VALUES (1,2052,'Acme')")
        self.db.execute('UPDATE T_PUR_POORDER SET FSUPPLIERID=1')
        for field, value, expected in [('supplier_name','Acme',8), ('order_statuses','已审核',8), ('stock_statuses','已审核',3)]:
            with self.subTest(field=field):
                query = purchase.PurchaseQuery(column_filters=column_values(field,[value]), page_size=1)
                listed = purchase.list_requests(self.connection, query, fixture.GRANTS)
                self.assertEqual(listed['total'], expected)
                self.assertEqual(listed['items'][0][field], value)
                self.assertEqual(sum(len(b) for b in purchase_batches(self.connection, query, fixture.GRANTS)), expected)
                candidates = purchase_candidates(self.connection, query, fixture.GRANTS, field, '', 1, 1)
                self.assertEqual(candidates['total'], 2)
                self.assertIsNone(candidates['items'][0]['value'])
        # A same-ID source in another organization must not contribute labels.
        self.db.execute('UPDATE T_PUR_POORDER SET FPURCHASEORGID=200 WHERE FID=4')
        query = purchase.PurchaseQuery(filters=condition('supplier_name','equals','Acme'))
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 7)
        query = purchase.PurchaseQuery(column_filters=column_values('stock_statuses',['已审核']))
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 2)

    def test_unconfigured_product_line_and_overview_organization_characters(self):
        self.db.execute("INSERT INTO T_ORG_ORGANIZATIONS_L VALUES(100,2052,'Factory')")
        query = purchase.PurchaseOverviewQuery(column_filters=column_condition('organization_name','startsWith','fac'))
        result = purchase.list_overview(self.connection, query, fixture.GRANTS)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['total_lines'], 9)
        query = purchase.PurchaseQuery(filters=condition('product_line_name','contains','未配置产品线'))
        query._query_labels = {'product_line_name':{}}
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 9)

    def test_supplier_with_progress_has_no_duplicate_workset_columns(self):
        query = purchase.PurchaseQuery(column_filters=column_condition('supplier_name','isEmpty'), progress='complete')
        with purchase.purchase_selection(self.connection, query, fixture.GRANTS):
            columns = [r['name'] for r in self.db.execute('PRAGMA table_info(temp_pms_purchase_base_amounts)')]
            self.assertFalse(any(':' in name for name in columns), columns)

    def test_label_candidate_keyword_is_case_insensitive_with_sensitive_source(self):
        from app.services.report_column_candidates import purchase_candidates
        self.db.execute('PRAGMA case_sensitive_like=ON')
        query = purchase.PurchaseQuery()
        query._query_labels = {'project_name':{('P-1',100):'Pump One'}}
        result = purchase_candidates(self.connection,query,fixture.GRANTS,'project_name','PUMP',1,50)
        self.assertEqual(result['items'],[{'value':'Pump One','label':'Pump One'}])

    def test_overview_top_aggregate_fields_filter_after_full_accounting(self):
        from app.services.report_export_data import overview_batches
        query = purchase.PurchaseOverviewQuery(filters=condition('completion_rate','lessThan',12),
                                               column_filters=column_values('complete_lines',[1]))
        result = purchase.list_overview(self.connection, query, fixture.GRANTS)
        self.assertEqual(result['items'][0]['total_lines'], 9)
        self.assertEqual(sum(len(b) for b in overview_batches(self.connection, query, fixture.GRANTS)), 1)
        query = purchase.PurchaseOverviewQuery(filters=condition('total_lines','greaterThan',9))
        self.assertEqual(purchase.list_overview(self.connection, query, fixture.GRANTS)['total'], 0)
        with self.assertRaises(ValueError):
            purchase.PurchaseQuery(filters=query.filters)

    def test_all_display_labels_character_operators_and_multi_document_cells(self):
        self.db.execute("INSERT INTO T_BD_SUPPLIER_L(FSUPPLIERID,FLOCALEID,FNAME) VALUES(1,2052,'Acme'),(2,2052,'Other')")
        self.db.execute('UPDATE T_PUR_POORDER SET FSUPPLIERID=1')
        self.db.execute("INSERT INTO T_PUR_POORDER(FID,FPURCHASEORGID,FDOCUMENTSTATUS,FCANCELSTATUS,FSUPPLIERID) VALUES(22,100,'B','A',2)")
        self.db.execute('INSERT INTO T_PUR_POORDERENTRY(FENTRYID,FID,FMATERIALID,FBASEUNITID) VALUES(22,22,10,1)')
        self.db.execute("INSERT INTO T_PUR_POORDERENTRY_LK(FENTRYID,FLINKID,FSTABLENAME,FSID,FSBILLID,FBASEUNITQTY) VALUES(22,22,'T_PUR_REQENTRY',2,2,1)")
        for field, target, expected in [('product_line_name','Line A',9), ('project_name','Pump One',9),
                                         ('supplier_name','Acme',7), ('order_statuses','已审核',7), ('stock_statuses','已审核',3)]:
            for operator, value, count in [('equals',target,expected), ('contains',target,expected + (field == 'order_statuses')),
                                            ('startsWith',target,expected), ('endsWith',target,expected + (field == 'order_statuses')),
                                            ('notEquals',target,int(field in {'supplier_name','order_statuses'})),
                                            ('notContains',target,int(field == 'supplier_name')),
                                            ('isEmpty',None,0 if field in {'product_line_name','project_name'} else 6 if field == 'stock_statuses' else 1)]:
                with self.subTest(field=field,operator=operator):
                    query = purchase.PurchaseQuery(filters=condition(field,operator,value), page_size=1)
                    query._query_labels = {'project_name':{('P-1',100):'Pump One'},'product_line_name':{100:'Line A'}}
                    self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], count)
        from app.services.report_column_candidates import purchase_candidates
        query = purchase.PurchaseQuery()
        result = purchase_candidates(self.connection, query, fixture.GRANTS, 'order_statuses', '审核中', 1, 50)
        self.assertEqual(result['items'], [{'value':'审核中、已审核','label':'审核中、已审核'}])
        query = purchase.PurchaseQuery(column_filters=column_values('supplier_name',['多家供应商']))
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['items'][0]['id'], 2)

    def test_v2_text_blank_negative_literal_and_dates(self):
        for op, value, actual, expected in [('notContains', 'x', ' ', False),
                                             ('equals', ' AB ', 'ab', True),
                                             ('contains', '%_[', 'A%_[Z', True)]:
            query = StockDetailQuery(material='M', organization_ids=[1], start_date='2026-06-01',
                end_date='2026-06-30', filters=condition('bill_no', op, value))
            self.assertEqual(matches_filters({'bill_no': actual}, query.conditions()), expected)
        self.db.execute("UPDATE T_PUR_REQUISITION SET FAPPLICATIONDATE='2026-06-01 23:59:59' WHERE FID=4")
        query = purchase.PurchaseQuery(filters=condition('application_date', 'equals', '2026-06-01'),
                                       column_filters=column_condition('progress', 'equals', 'complete'))
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 1)

    def test_source_column_does_not_require_accounting_worksets(self):
        query = purchase.PurchaseQuery(column_filters=column_condition('bill_no', 'equals', 'R4'))
        with purchase.purchase_selection(self.connection, query, fixture.GRANTS) as (sql, _):
            self.assertNotIn('#pms_purchase_report', sql)
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 1)

    def test_column_values_empty_null_numeric_and_dates(self):
        query = purchase.PurchaseQuery(column_filters=column_values('requested', []))
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 0)
        query = purchase.PurchaseQuery(column_filters=column_values('requested', [1]))
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 9)
        query = purchase.PurchaseQuery(column_filters=column_values('application_date', ['2026-01-01']))
        self.assertEqual(purchase.list_requests(self.connection, query, fixture.GRANTS)['total'], 9)
        self.db.execute('UPDATE T_PUR_REQENTRY SET F_TWBJ_ASSISTANT_83G=NULL WHERE FENTRYID=1')
        query = purchase.PurchaseQuery(column_filters=column_values('project_code', [None]))
        self.assertEqual(purchase.list_requests(self.connection, query, ALL_DATA_SCOPE)['total'], 1)
        query = purchase.PurchaseQuery(column_filters=column_values('project_code', [None, 'P-1']))
        self.assertEqual(purchase.list_requests(self.connection, query, ALL_DATA_SCOPE)['total'], 9)
        for raw in (column_values('requested', [True]), json.dumps([
            {'field':'requested','mode':'values','values':[1]}, {'field':'requested','mode':'values','values':[2]}]),
            json.dumps([{'field':'bill_no','mode':'condition','condition':json.loads(condition('material_code','equals','M'))[0]}])):
            with self.assertRaises(ValueError):
                purchase.PurchaseQuery(column_filters=raw)
        with self.assertRaises(ValueError):
            purchase.PurchaseQuery(filters=condition('requested', 'in', [1]))
        for value in ('1e-999999999', '1e-29'):
            with self.assertRaises(ValueError):
                purchase.PurchaseQuery(filters=condition('requested', 'equals', value))
            with self.assertRaises(ValueError):
                purchase.PurchaseQuery(column_filters=column_values('requested', [value]))

    def test_purchase_column_candidates_exclude_self_keep_other_and_page_distinct(self):
        from app.services.report_column_candidates import purchase_candidates
        self.db.execute("UPDATE T_PUR_REQUISITION SET FBILLNO='DUP' WHERE FID IN (1,2)")
        query = purchase.PurchaseQuery(column_filters=json.dumps([
            {'field':'bill_no','mode':'values','values':['R4']},
            {'field':'requested','mode':'values','values':[1]}]), page_size=1)
        result = purchase_candidates(self.connection, query, fixture.GRANTS, 'bill_no', '', 2, 2)
        self.assertEqual(result['total'], 8)
        self.assertEqual([v['value'] for v in result['items']], ['R4', 'R5'])
        self.assertTrue(result['has_more'])
        missing = purchase_candidates(self.connection, query, fixture.GRANTS, 'bill_no', 'missing', 1, 50)
        self.assertEqual(missing['total'], 0)

    def test_overview_candidates_aggregate_before_distinct(self):
        from app.services.report_column_candidates import purchase_candidates
        query = purchase.PurchaseOverviewQuery(column_filters=column_values('total_lines', [100]))
        result = purchase_candidates(self.connection, query, fixture.GRANTS, 'total_lines', '', 1, 50)
        self.assertEqual([Decimal(str(v['value'])) for v in result['items']], [Decimal(9)])

    def test_stock_column_display_preserves_calculation_and_candidates(self):
        from app.services.stock_detail_balance import InventoryKey
        from app.services.stock_detail_reader import assemble_page
        from app.services.stock_detail_engine import export_rows
        from app.services.report_column_candidates import stock_candidates
        key = InventoryKey(1, 11, 20, 1, '', 0, 10)
        rows = [dict(row_id=str(i), inventory_key=key, bill_date=date(2026, 6, i),
                     source_order=0, created_at=datetime(2026, 6, i), bill_no='B'+str(i),
                     bill_seq=i, income_qty=Decimal(income), issue_qty=Decimal(issue))
                for i, income, issue in ((1, 10, 0), (2, 0, 3), (3, 2, 0))]
        dataset = dict(rows=rows, openings={key: Decimal(5)}, labels={})
        query = StockDetailQuery(material='M', organization_ids=[1], start_date='2026-06-01', end_date='2026-06-30',
                                 column_filters=column_values('balance_qty', [12]))
        page = assemble_page(query, rows, dataset['openings'], opening_date=query.start_date)
        self.assertEqual(page['total'], 1)
        self.assertEqual(page['items'][0]['balance_qty'], Decimal(12))
        self.assertEqual(page['openings'], [])
        exported = list(export_rows(dataset, query.start_date, conditions=query.conditions(), column_conditions=query.column_conditions()))
        self.assertEqual([r['bill_no'] for r in exported], ['B2'])
        candidates = stock_candidates(query, dataset, 'balance_qty', '', 1, 50)
        self.assertEqual({Decimal(v['value']) for v in candidates['items']}, {Decimal(5), Decimal(12), Decimal(14), Decimal(15)})

    def test_stock_sort_is_after_full_balance_before_page_and_shared_with_export(self):
        from app.services.stock_detail_balance import InventoryKey
        from app.services.stock_detail_reader import assemble_page
        from app.services.stock_detail_engine import export_rows
        key = InventoryKey(1,11,20,1,'',0,10)
        rows = [dict(row_id=str(i),inventory_key=key,bill_date=date(2026,6,i),source_order=0,
                     created_at=datetime(2026,6,i),bill_no='B'+str(i),bill_seq=i,
                     income_qty=Decimal(income),issue_qty=Decimal(issue))
                for i,income,issue in ((1,10,0),(2,0,3),(3,2,0))]
        args = dict(material='M',organization_ids=[1],start_date='2026-06-01',end_date='2026-06-30')
        query = StockDetailQuery(**args,sort='balance_qty',direction='desc',page=2,page_size=1)
        result = assemble_page(query, rows, {key:Decimal(5)}, opening_date=query.start_date)
        self.assertEqual(result['total'],3)
        self.assertEqual(result['items'][0]['bill_no'],'B3')
        self.assertEqual(result['items'][0]['balance_qty'],Decimal(14))
        dataset = dict(rows=rows,openings={key:Decimal(5)},labels={})
        exported = list(export_rows(dataset, query.start_date, sort=query.sort, direction=query.direction))
        self.assertEqual([r['bill_no'] for r in exported],[None,'B1','B3','B2'])
        self.assertEqual([r['balance_qty'] for r in exported],[Decimal(5),Decimal(15),Decimal(14),Decimal(12)])
        for field in ('bill_date','bill_no','material_code','material_name','stock_name','stock_status_name',
                      'owner_type_name','owner_name','unit_name','bill_name','bill_seq','opening_qty','income_qty','issue_qty'):
            StockDetailQuery(**args,sort=field,direction='asc')
        for extra in ({'sort':'row_id'},{'sort':'bill_no; DROP TABLE x'},{'direction':'random'}):
            with self.assertRaises(ValueError):
                StockDetailQuery(**args,**extra)

    def test_inventory_candidates_distinct_before_paging(self):
        from app.services.inventory_reader import KEYS
        from app.services.report_column_candidates import inventory_candidates
        self.db.execute('CREATE TABLE YD_JIN_INVENTORY (' + ','.join(f'[{k}]' for k in KEYS) + ')')
        self.db.execute('CREATE TABLE T_STK_INVENTORY (FID, FSTOCKORGID)')
        for index, stock in enumerate(['A', 'A', 'B', 'C', 'SECRET']):
            self.db.execute('INSERT INTO YD_JIN_INVENTORY (FID,Stock,FBaseQty) VALUES (?,?,?)', (str(index), stock, index))
            self.db.execute('INSERT INTO T_STK_INVENTORY VALUES (?,?)', (str(index), 200 if stock == 'SECRET' else 100))
        from app.services.inventory_reader import InventoryQuery
        query = InventoryQuery(column_filters=column_values('Stock', ['A']), page_size=1)
        result = inventory_candidates(self.connection, query, [100], 'Stock', '', 2, 1)
        self.assertEqual(result['total'], 3)
        self.assertEqual(result['items'][0]['value'], 'B')

    def test_overview_export_reuses_aggregate_column_scope(self):
        from app.services.report_export_data import overview_batches
        query = purchase.PurchaseOverviewQuery(view='overview', column_filters=column_values('complete_lines', [1]))
        rows = [row for batch in overview_batches(self.connection, query, fixture.GRANTS) for row in batch]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['total_lines'], 9)
        self.assertAlmostEqual(float(rows[0]['completion_rate']), 100 / 9)

    def test_stock_reference_reader_full_pagination_scope_and_identity(self):
        from app.services.stock_detail_reader import list_reference_candidates
        self.db.execute('CREATE TABLE T_BD_STOCK (FSTOCKID,FUSEORGID,FNUMBER)')
        self.db.execute('CREATE TABLE T_BD_STOCK_L (FSTOCKID,FLOCALEID,FNAME)')
        self.db.executemany('INSERT INTO T_BD_STOCK VALUES (?,?,?)', [(10,100,'001'),(20,100,'002'),(30,200,'003')])
        self.db.executemany('INSERT INTO T_BD_STOCK_L VALUES (?,?,?)', [(10,2052,'Same'),(20,2052,'Same'),(30,2052,'Secret')])
        cursor = self.connection.cursor()
        self.addCleanup(cursor.close)
        result = list_reference_candidates(cursor, 'stock', '', [100], page=2, page_size=1)
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['items'][0]['value'], 20)
        self.assertEqual(list_reference_candidates(cursor,'stock','',[100],ids=['20'])['items'][0]['value'], 20)
        with self.assertRaises(HTTPException):
            list_reference_candidates(cursor,'stock','',[100],ids=['30'])
        result = list_reference_candidates(cursor,'stock','',[100],batch_field='name',batch_values=['Same','missing'])
        self.assertEqual(result['batch']['ambiguous_values'], ['Same'])
        self.assertEqual(result['batch']['unmatched_values'], ['missing'])


class ReferenceOptionsV2(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api import purchase_reports
        from app.core.database import get_db
        from app.services.authorization import get_current_user_context
        from app.models.project import PmsProjectArchive
        self.source = api_fixture.ReportApiContract()
        self.source.setUp()
        self.addCleanup(self.source.doCleanups)
        self.db = self.source.db
        line = self.source.line()
        self.ctx = dict(user_id=7, data_scope=1, product_line_ids=[line.id], permissions=['report:purchase:view'])
        self.db.add_all([PmsProjectArchive(project_code='001', project_name='Same', manager_id=7, business_product_line_id=line.id),
                         PmsProjectArchive(project_code='002', project_name='Same', manager_id=7, business_product_line_id=line.id),
                         PmsProjectArchive(project_code='003', project_name='Same', manager_id=8, business_product_line_id=line.id)])
        self.db.commit()
        app = FastAPI()
        app.include_router(purchase_reports.router)
        from app.api import inventory_reports, stock_detail_reports
        app.include_router(inventory_reports.router)
        app.include_router(stock_detail_reports.router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user_context] = lambda: self.ctx
        self.client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def test_batch_exact_names_paged_identity_and_current_scope(self):
        response = self.client.get('/api/reports/purchase/reference-options', params={
            'field': 'project_name', 'exact_values': json.dumps(['Same', 'missing', 'Same']), 'page_size': 1})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['batch']['unmatched_values'], ['missing'])
        self.assertEqual(result['batch']['ambiguous_values'], ['Same'])
        self.assertEqual(result['batch']['duplicate_count'], 1)
        self.assertEqual(len(result['items']), 1)
        self.assertIsInstance(result['items'][0]['value'], int)
        self.assertEqual(result['items'][0]['organization_id'], 100)

    def test_database_allowlist_labels_and_visible_names_share_pair_identity(self):
        from app.api import purchase_reports as api
        from app.services.purchase_query_labels import resolve_query_labels
        query = purchase.PurchaseQuery(filters=condition('project_name','equals','Same'),
                                       column_filters=column_values('product_line_name',['100']))
        resolve_query_labels(self.db, self.ctx, query)
        self.assertEqual(query._query_labels['product_line_name'], {100:'100'})
        self.assertEqual(query._query_labels['project_name'], {('001',100):'Same',('002',100):'Same'})
        rows = [{'project_code':'001','organization_id':100}, {'project_code':'001','organization_id':200}]
        api.enrich_project_names(self.db, self.ctx, rows)
        self.assertEqual(rows[0]['project_name'], 'Same')
        self.assertIsNone(rows[1]['project_name'])

    def test_http_labels_filter_and_candidates_use_full_source_not_visible_page(self):
        from contextlib import nullcontext
        from app.api import purchase_reports as api
        source = fixture.ReaderContract()
        self.addCleanup(source.doCleanups)
        original, _ = source.classification_fixture()
        original.execute("UPDATE T_BAS_ASSISTANTDATAENTRY SET FNUMBER='001'")
        original.execute("INSERT INTO T_BD_SUPPLIER_L(FSUPPLIERID,FLOCALEID,FNAME) VALUES(1,2052,'Acme')")
        original.execute('UPDATE T_PUR_POORDER SET FSUPPLIERID=1')
        original.execute('CREATE TABLE T_ORG_ORGANIZATIONS_L(FORGID,FLOCALEID,FNAME)')
        original.commit()
        erp = sqlite3.connect(':memory:', check_same_thread=False)
        erp.row_factory = sqlite3.Row
        original.backup(erp)
        erp.create_function('CONCAT',-1,lambda *args: ''.join(str(v) for v in args if v is not None))
        erp.create_function('STUFF',4,lambda s,start,length,replacement: s[:start-1]+replacement+s[start-1+length:] if s and start<=len(s) else None)
        self.addCleanup(erp.close)
        with patch.object(api,'purchase_connection',return_value=nullcontext(Connection(erp))):
            for field,value,count in [('product_line_name','100',9),('project_name','Same',9),
                                       ('supplier_name','Acme',8),('order_statuses','已审核',8),('stock_statuses','已审核',3)]:
                with self.subTest(field=field):
                    params = {'filters':condition(field,'equals',value), 'page_size':1}
                    listed = self.client.get('/api/reports/purchase', params=params)
                    self.assertEqual(listed.status_code,200,listed.text)
                    self.assertEqual(listed.json()['total'], count)
                    self.assertEqual(listed.json()['items'][0][field], value)
                    candidates = self.client.get('/api/reports/purchase/column-options', params={'field':field,'keyword':value,'parameters':json.dumps(params)})
                    self.assertEqual(candidates.status_code,200,candidates.text)
                    self.assertEqual(candidates.json()['items'], [{'value':value,'label':value}])
            from app.services import report_export_jobs as jobs
            from app.services.report_export_data import write_report
            self.ctx['permissions'].append('report:purchase:export')
            parameters = dict(view='overview',filters=condition('project_name','equals','Same'),
                              column_filters=column_values('complete_lines',[1]))
            with patch.object(jobs,'scope_signature',return_value='fixture'):
                job = jobs.create_job(self.db,self.ctx,'purchase',parameters,
                                      ['project_name','product_line_name','total_lines','complete_lines'])
            self.assertEqual(json.loads(job.parameters)['view'],'overview')
            with tempfile.TemporaryDirectory() as folder, \
                 patch('app.services.report_export_data.purchase_connection',return_value=nullcontext(Connection(erp))):
                path = Path(folder)/'overview.xlsx'
                write_report(self.db,job,self.ctx,path,lambda count: None)
                with zipfile.ZipFile(path) as archive:
                    workbook = archive.read('xl/workbook.xml').decode()
                    self.assertIn('采购总进度',workbook)
                    self.assertNotIn('订单明细',workbook)
                    xml = archive.read('xl/worksheets/sheet1.xml').decode()
                    self.assertIn('Same',xml)
                    self.assertIn('100',xml)
                    root = ET.fromstring(xml)
                    self.assertEqual(len(root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')),2)
            from app.models.product_line import SysProductLine
            line = SysProductLine(source_key='kingdee',organization_id=200,organization_code='200',
                                  organization_name='200',display_name='200',name_key='200')
            self.db.add(line)
            self.db.commit()
            self.ctx['product_line_ids'].append(line.id)
            erp.execute('UPDATE T_PUR_REQUISITION SET FAPPLICATIONORGID=200 WHERE FID=1')
            listed = self.client.get('/api/reports/purchase',params={'filters':condition('project_name','isEmpty')})
            self.assertEqual(listed.status_code,200,listed.text)
            self.assertEqual(listed.json()['total'],1)
            self.assertIsNone(listed.json()['items'][0]['project_name'])

    def test_exact_codes_keep_zero_and_cannot_bypass_organization(self):
        path = '/api/reports/purchase/reference-options'
        self.assertEqual(self.client.get(path, params={'field':'project_code','exact_values':'["001"]'}).json()['total'], 1)
        self.assertEqual(self.client.get(path, params={'field':'project_code','exact_values':'["01"]'}).json()['total'], 0)
        self.assertEqual(self.client.get(path, params={'field':'project_code','organization_ids':200}).json()['total'], 0)
        for values in ('[1]', '[]', '["A\\tB"]', 'null'):
            self.assertEqual(self.client.get(path, params={'field':'project_code', 'exact_values':values}).status_code, 422)
        self.ctx['permissions'] = []
        self.assertEqual(self.client.get(path, params={'field':'project_code'}).status_code, 403)

    def test_project_reference_restore_validates_selected_ids(self):
        path = '/api/reports/purchase/reference-options'
        item = self.client.get(path, params={'field':'project_code', 'exact_values':'["002"]'}).json()['items'][0]
        response = self.client.get(path, params={'field':'project_code','ids':item['value']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['value'] for r in response.json()['items']], [item['value']])
        self.assertEqual(response.json()['items'][0]['lineName'], '100')
        self.assertEqual(self.client.get(path, params={'field':'project_code','ids':999}).status_code, 422)

    def test_column_candidate_api_guards_and_invalid_fields(self):
        self.ctx['permissions'] = ['report:purchase:view', 'report:inventory:view', 'report:stock-detail:list', 'report:stock-detail:view']
        for path in ('purchase/column-options', 'purchase/overview/column-options', 'inventory/column-options', 'stock-detail/column-options'):
            response = self.client.get('/api/reports/' + path, params={'field':'unknown'})
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get('/api/reports/stock-detail/column-options', params={'field':'bill_no'}).status_code, 422)
        self.ctx['permissions'] = []
        for path in ('purchase/column-options', 'purchase/overview/column-options', 'inventory/column-options', 'stock-detail/column-options'):
            self.assertEqual(self.client.get('/api/reports/' + path, params={'field':'bill_no'}).status_code, 403)

    def test_purchase_candidate_http_keeps_submitted_keyword_separate(self):
        from contextlib import nullcontext
        from app.api import purchase_reports as api
        source = fixture.ReaderContract()
        self.addCleanup(source.doCleanups)
        original, _ = source.classification_fixture()
        original.commit()
        erp = sqlite3.connect(':memory:', check_same_thread=False)
        erp.row_factory = sqlite3.Row
        original.backup(erp)
        self.addCleanup(erp.close)
        parameters = dict(keyword='R', column_filters=column_values('bill_no', ['R3']))
        with patch.object(api, 'purchase_connection', return_value=nullcontext(Connection(erp))):
            response = self.client.get('/api/reports/purchase/column-options', params={
                'field':'bill_no', 'keyword':'R4', 'parameters':json.dumps(parameters), 'page_size':1})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['total'], 1)
        self.assertEqual(response.json()['items'][0]['value'], 'R4')

    def test_stock_summary_display_filters_after_complete_calculation(self):
        from app.api import stock_detail_reports as api
        from app.services.stock_detail_balance import InventoryKey
        from contextlib import nullcontext
        key = InventoryKey(1, 11, 20, 1, '', 0, 10)
        rows = [dict(row_id='1', inventory_key=key, bill_date=date(2026,6,1), source_order=0,
                     created_at=datetime(2026,6,1), bill_no='B', bill_seq=1, income_qty=Decimal(10), issue_qty=Decimal(0))]
        dataset = dict(rows=rows, openings={key:Decimal(5)}, labels={})
        query = StockDetailQuery(material='M', organization_ids=[100], start_date='2026-06-01', end_date='2026-06-30',
                                 column_filters=column_values('balance_qty',[5]))
        self.ctx['permissions'] = ['report:stock-detail:list', 'report:stock-detail:view']
        with patch.object(api,'purchase_connection',return_value=nullcontext(object())), patch.object(api,'read_dataset',return_value=dataset):
            response = self.client.get('/api/reports/stock-detail', params=query.model_dump(mode='json', exclude_none=True))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()['summary'])
        self.assertEqual(response.json()['total'], 0)
        self.assertEqual(response.json()['openings'][0]['balance_qty'], '5')

    def test_stock_reference_http_forwards_paging_and_ids(self):
        from app.api import stock_detail_reports as api
        from contextlib import nullcontext
        self.ctx['permissions'] = ['report:stock-detail:list','report:stock-detail:view']
        connection = Mock()
        with patch.object(api, 'purchase_connection', return_value=nullcontext(connection)), \
             patch.object(api, 'list_reference_candidates', return_value={'items':[{'value':20,'code':'001','label':'Stock'}], 'total':1,'has_more':False}) as read:
            response = self.client.get('/api/reports/stock-detail/options', params={'field':'stock','organization_ids':100,'page':1,'page_size':50,'ids':20})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], 1)
        self.assertEqual(read.call_args.kwargs['ids'], ['20'])

    def test_stock_sort_http_metadata_candidates_and_export_pipeline(self):
        from app.api import stock_detail_reports as api
        from app.services.stock_detail_balance import InventoryKey
        from app.services.report_export_data import write_report
        from contextlib import nullcontext
        key = InventoryKey(1,11,20,1,'',0,10)
        rows = [dict(row_id=str(i),inventory_key=key,bill_date=date(2026,6,i),source_order=0,
                     created_at=datetime(2026,6,i),bill_no=bill,bill_seq=i,
                     income_qty=Decimal(income),issue_qty=Decimal(issue))
                for i,bill,income,issue in ((1,'Z',10,0),(2,'A',0,3),(3,'B',2,0))]
        dataset = dict(rows=rows,openings={key:Decimal(5)},labels={})
        self.ctx['permissions'] = ['report:stock-detail:list','report:stock-detail:view','report:stock-detail:export']
        metadata = self.client.get('/api/reports/stock-detail/metadata')
        self.assertEqual(metadata.status_code,200)
        self.assertIn('balance_qty',metadata.json()['sort_fields'])
        self.assertEqual(metadata.json()['default_sort'],{'sort':'bill_date','direction':'asc'})
        parameters = dict(material='M',organization_ids=[100],start_date='2026-06-01',end_date='2026-06-30',sort='bill_no',direction='asc',page_size=1)
        with patch.object(api,'purchase_connection',return_value=nullcontext(object())), patch.object(api,'read_dataset',return_value=dataset):
            response = self.client.get('/api/reports/stock-detail',params=parameters)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['items'][0]['bill_no'],'A')
            self.assertEqual(response.json()['items'][0]['balance_qty'],'12')
            candidates = self.client.get('/api/reports/stock-detail/column-options',params={'field':'balance_qty','parameters':json.dumps(parameters)})
            self.assertEqual(candidates.status_code,200,candidates.text)
            self.assertEqual({Decimal(r['value']) for r in candidates.json()['items']},{Decimal(5),Decimal(12),Decimal(14),Decimal(15)})
        main = Mock()
        job = SimpleNamespace(report='stock-detail',parameters=json.dumps(parameters),columns='["bill_no","balance_qty"]')
        with tempfile.TemporaryDirectory() as folder, patch('app.services.report_export_data.ReportWorkbook') as book, \
             patch('app.services.report_export_data.purchase_connection',return_value=nullcontext(object())), \
             patch('app.services.stock_detail_fetch.read_dataset',return_value=dataset):
            book.return_value.__enter__.return_value.sheet.return_value = main
            write_report(self.db,job,self.ctx,Path(folder)/'stock.xlsx',lambda count: None)
        self.assertEqual([call.args[0]['bill_no'] for call in main.append.call_args_list],[None,'A','B','Z'])
        self.assertEqual([call.args[0]['balance_qty'] for call in main.append.call_args_list],[Decimal(5),Decimal(12),Decimal(14),Decimal(15)])

if __name__ == '__main__':
    unittest.main()
