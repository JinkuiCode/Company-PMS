from pathlib import Path
import sys
import json
import unittest
from contextlib import contextmanager, ExitStack
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.database import get_db
from app.services.authorization import get_current_user_context
from app.api import purchase_reports as purchase, inventory_reports as inventory, stock_detail_reports as stock
from material_reference_contract import Cursor


class MaterialApi(unittest.TestCase):
    def setUp(self):
        self.cursor=Cursor();self.cursor.add('0007-A','合成物料',11);self.cursor.add('OUT','越界',99)
        self.ctx={'user_id':7,'permissions':[],'product_line_ids':[1]}
        app=FastAPI()
        for api in (purchase,inventory,stock):app.include_router(api.router)
        app.dependency_overrides[get_db]=lambda:None
        app.dependency_overrides[get_current_user_context]=lambda:self.ctx
        self.client=TestClient(app,raise_server_exceptions=False);self.addCleanup(self.client.close)
        @contextmanager
        def connection():
            class Connection:
                def cursor(inner):return self.cursor
            yield Connection()
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for api in (purchase,inventory,stock):
            self.stack.enter_context(patch.object(api,'purchase_connection',connection))
            self.stack.enter_context(patch.object(api,'authorized_organizations',return_value=[11]))
        self.paths=[('/api/reports/purchase/material-reference-options',['report:purchase:view'],{}),
            ('/api/reports/inventory/material-reference-options',['report:inventory:view'],{}),
            ('/api/reports/stock-detail/options',['report:stock-detail:list','report:stock-detail:view'],{'field':'material','organization_ids':11})]

    def test_each_consumer_uses_its_own_existing_permissions(self):
        for url,permissions,params in self.paths:
            self.ctx['permissions']=permissions
            response=self.client.get(url,params={**params,'page':1})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['items'][0]['value'],'0007-a')
            self.ctx['permissions']=[]
            self.assertEqual(self.client.get(url,params={**params,'page':1}).status_code,403)

    def test_stock_requires_both_list_and_view(self):
        for perms in [['report:stock-detail:list'],['report:stock-detail:view']]:
            self.ctx['permissions']=perms
            self.assertEqual(self.client.get(self.paths[2][0],params=self.paths[2][2]).status_code,403)

    def test_empty_scope_is_not_all_and_invalid_ids_fail(self):
        for url,permissions,params in self.paths:
            self.ctx['permissions']=permissions
            with ExitStack() as stack:
                for api in (purchase,inventory,stock):stack.enter_context(patch.object(api,'authorized_organizations',return_value=[]))
                result=self.client.get(url,params={**params,'page':1})
                self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['total'],0)
                self.assertEqual(self.client.get(url,params={**params,'page':1,'ids':'0007-a'}).status_code,422)

    def test_missing_stock_line_and_foreign_material_cannot_bypass(self):
        self.ctx['permissions']=self.paths[2][1]
        self.assertEqual(self.client.get(self.paths[2][0],params={'field':'material','page':1}).status_code,422)
        for url,permissions,params in self.paths:
            self.ctx['permissions']=permissions
            self.assertEqual(self.client.get(url,params={**params,'page':1,'ids':'OUT'}).status_code,422)

    def test_empty_scope_report_references_are_rejected_not_silently_dropped(self):
        cases=[('/api/reports/purchase',self.paths[0][1],{'filters':json.dumps([dict(schemaVersion=2,field='material_code',operator='reference',value=['0007-a'])])}),
            ('/api/reports/inventory',self.paths[1][1],{'filters':json.dumps([dict(schemaVersion=2,field='MaterialCode',operator='reference',value=['0007-a'])])}),
            ('/api/reports/stock-detail',self.paths[2][1],dict(material_codes=['0007-a'],organization_ids=[11],start_date='2026-10-01',end_date='2026-10-20'))]
        with ExitStack() as stack:
            for api in (purchase,inventory,stock):stack.enter_context(patch.object(api,'authorized_organizations',return_value=[]))
            for url,permissions,params in cases:
                self.ctx['permissions']=permissions
                response=self.client.get(url,params=params)
                self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.cursor.calls,[])

    def test_old_inventory_text_conditions_do_not_require_material_identity_validation(self):
        from app.services.inventory_reader import InventoryQuery
        from app.services.report_material_reference import validate_reference_query
        query=InventoryQuery(filters=json.dumps([dict(field='MaterialCode',operator='contains',value='0007')]))
        try:validate_reference_query(None,query,[11])
        except Exception as error:self.fail(f'legacy text query must stay valid: {error}')


if __name__=='__main__':unittest.main()
