"""Product lines follow requisition organizations, not the project's owner."""
import unittest
from unittest.mock import patch
import purchase_reader_contract as fixtures
import purchase_api_contract as api_fixtures
from app.services import purchase_reader as reader
from app.services.business_data_scope import ALL_DATA_SCOPE


class ProductLineReader(unittest.TestCase):
    def test_project_candidates_follow_selected_organizations_and_exact_validation(self):
        fixture = fixtures.ReaderContract()
        self.addCleanup(fixture.doCleanups)
        db, connection = fixture.classification_fixture()
        db.execute("INSERT INTO T_BAS_ASSISTANTDATAENTRY(FENTRYID,FNUMBER) VALUES ('other','P-2')")
        db.execute('UPDATE T_PUR_REQUISITION SET FAPPLICATIONORGID=200 WHERE FID IN (1,2)')
        db.execute("UPDATE T_PUR_REQENTRY SET F_TWBJ_ASSISTANT_83G='other' WHERE FENTRYID=2")
        selected = reader.PurchaseQuery(organization_ids=[100])
        self.assertEqual(reader.list_options(connection,'project','P-',ALL_DATA_SCOPE,query=selected)['items'],[{'value':'P-1','label':'P-1'}])
        selected = reader.PurchaseQuery(organization_ids=[200])
        self.assertEqual([r['value'] for r in reader.list_options(connection,'project','P-',ALL_DATA_SCOPE,query=selected)['items']],['P-1','P-2'])
        self.assertEqual(reader.list_options(connection,'project','',[reader.OrganizationGrant(100)],query=selected)['items'],[])
        self.assertEqual(reader.list_options(connection,'project','',ALL_DATA_SCOPE,query=reader.PurchaseQuery(organization_ids=[100],project_code='P-2'))['items'],[])

    def test_selected_organization_intersects_authorization_and_exports(self):
        fixture = fixtures.ReaderContract()
        self.addCleanup(fixture.doCleanups)
        db, connection = fixture.classification_fixture()
        db.execute('UPDATE T_PUR_REQUISITION SET FAPPLICATIONORGID=CASE WHEN FID=1 THEN 200 ELSE 100 END')
        query = reader.PurchaseQuery(organization_ids=[200])
        result = reader.list_requests(connection, query, ALL_DATA_SCOPE)
        self.assertEqual([r['id'] for r in result['items']], [1])
        self.assertEqual(reader.list_requests(connection, query, [reader.OrganizationGrant(100)])['total'], 0)
        self.assertEqual(reader.list_requests(connection, query, [])['total'], 0)
        # Both export selection and paged listing use this same base selection.
        with reader.purchase_selection(connection, query, ALL_DATA_SCOPE) as (sql, params):
            selected = reader._rows(connection, sql, params)
        self.assertEqual([r['id'] for r in selected], [1])
        both = reader.PurchaseQuery(organization_ids=[100, 200, 200])
        self.assertEqual(reader.list_requests(connection, both, ALL_DATA_SCOPE)['total'], 9)
        self.assertEqual(reader.list_requests(connection, reader.PurchaseQuery(), ALL_DATA_SCOPE)['total'], 9)

    def test_invalid_organizations_are_rejected(self):
        from pydantic import ValidationError
        for ids in ([0], [-1], ['invalid'], list(range(1, 202))):
            with self.assertRaises(ValidationError):
                reader.PurchaseQuery(organization_ids=ids)


class ProductLineApi(unittest.TestCase):
    def test_disabled_lines_are_not_selectable_and_http_candidates_keep_scope(self):
        from contextlib import nullcontext
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.core.database import get_db
        from app.services.authorization import get_current_user_context
        from app.models.product_line import SysProductLine
        api = self.api()
        line = self.line()
        disabled=SysProductLine(source_key='kingdee',organization_id=200,organization_code='200',organization_name='旧组织',display_name='停用产品线',name_key='disabled',is_enabled=0)
        hidden=SysProductLine(source_key='kingdee',organization_id=300,organization_code='300',organization_name='其他组织',display_name='其他产品线',name_key='other',is_enabled=1)
        self.db.add_all([disabled,hidden]); self.db.flush()
        ctx={'permissions':['report:purchase:view'],'product_line_ids':[line.id,disabled.id]}
        self.assertEqual(api.metadata(self.db,ctx)['organizations'],[{'value':100,'label':'100'}])
        app=FastAPI(); app.include_router(api.router)
        app.dependency_overrides[get_db]=lambda:self.db
        app.dependency_overrides[get_current_user_context]=lambda:ctx
        with TestClient(app) as client, patch.object(api,'purchase_connection',return_value=nullcontext(object())), patch.object(api,'list_options',return_value={'items':[],'has_more':False}) as read:
            response=client.get('/api/reports/purchase/options?field=project&keyword=P-&organization_ids=100&project_code=P-1')
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(read.call_args.kwargs['query'].organization_ids,[100])
            self.assertEqual(read.call_args.kwargs['query'].project_code,'P-1')
            self.assertEqual([g.organization_id for g in read.call_args.args[3]],[100,200])
            self.assertEqual(client.get('/api/reports/purchase/options?field=project&organization_ids=-1').status_code,422)

    def setUp(self):
        self.fixture = api_fixtures.ReportApiContract()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db = self.fixture.db

    def api(self):
        return self.fixture.api()

    def line(self):
        return self.fixture.line()

    def test_metadata_exposes_only_authorized_product_lines(self):
        api = self.api()
        line = self.line()
        line.display_name = '8吋半导体'
        self.db.flush()
        result = api.metadata(db=self.db, ctx={'product_line_ids': [line.id]})
        self.assertEqual(result['organizations'], [{'value': 100, 'label': '8吋半导体'}])
        self.assertEqual(api.metadata(db=self.db, ctx={'product_line_ids': []})['organizations'], [])
        self.assertTrue(any(f['key'] == 'product_line_name' for f in result['fields']))
        fields = {field['key']: field for field in result['fields']}
        self.assertEqual(fields['product_line_name']['group'], '项目信息')
        self.assertEqual(fields['product_line_name']['group'], fields['project_code']['group'])

    def test_names_follow_requisition_org_and_preserve_unconfigured_data(self):
        api = self.api()
        self.assertTrue(hasattr(api, 'enrich_product_lines'))
        line = self.line()
        line.display_name = '8吋半导体'
        self.db.flush()
        rows = [{'project_code': 'A', 'organization_id': 100},
                {'project_code': 'A', 'organization_id': 200}]
        with patch.object(api, '_rows', return_value=[{'id': 200, 'name': '领创'}]):
            api.enrich_product_lines(self.db, object(), rows)
        self.assertEqual(rows[0]['product_line_name'], '8吋半导体')
        self.assertEqual(rows[1]['product_line_name'], '领创（未配置产品线）')
        self.assertEqual(api.public_row(rows[1])['product_line_name'], '领创（未配置产品线）')

    def test_export_workbook_labels_all_sheets_and_uses_selected_org(self):
        import json
        import tempfile
        import zipfile
        from pathlib import Path
        from contextlib import nullcontext
        from types import SimpleNamespace
        from purchase_typed_progress_contract import Connection
        from app.services.report_export_data import write_report
        source = fixtures.ReaderContract()
        self.addCleanup(source.doCleanups)
        erp, _ = source.classification_fixture()
        erp.execute('UPDATE T_PUR_REQUISITION SET FAPPLICATIONORGID=200 WHERE FID<>4')
        line = self.line()
        line.display_name = '8吋半导体'
        self.db.flush()
        query = reader.PurchaseQuery(organization_ids=[100])
        job = SimpleNamespace(report='purchase', parameters=query.model_dump_json(),
                              columns=json.dumps(['bill_no', 'product_line_name']))
        with tempfile.TemporaryDirectory() as folder, \
                patch('app.services.report_export_data.purchase_connection', return_value=nullcontext(Connection(erp))), \
                patch('app.api.purchase_reports.project_scope', return_value=ALL_DATA_SCOPE), \
                patch('app.api.purchase_reports.enrich_project_names'):
            path = Path(folder) / 'out.xlsx'
            write_report(self.db, job, {}, path, lambda n: None)
            with zipfile.ZipFile(path) as archive:
                sheets = [archive.read(f'xl/worksheets/sheet{i}.xml').decode() for i in (1, 2, 3)]
            for sheet in sheets:
                self.assertIn('产品线', sheet)
                self.assertIn('8吋半导体', sheet)
            self.assertIn('R4', sheets[0])
            self.assertNotIn('R1', sheets[0])

    def test_http_multiselect_is_parsed_and_retained(self):
        from contextlib import nullcontext
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.core.database import get_db
        from app.services.authorization import get_current_user_context
        api = self.api()
        app = FastAPI()
        app.include_router(api.router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user_context] = lambda: {'permissions': ['report:purchase:view']}
        with TestClient(app) as client, \
                patch.object(api, 'purchase_connection', return_value=nullcontext(object())), \
                patch.object(api, 'list_requests', return_value={'items': [], 'total': 0}) as call:
            response = client.get('/api/reports/purchase?organization_ids=100&organization_ids=200')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(call.call_args.args[1].organization_ids, [100, 200])


if __name__ == '__main__':
    unittest.main()
