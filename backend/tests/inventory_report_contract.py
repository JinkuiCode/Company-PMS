import importlib.util
import json
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
import app.models.init_db
from app.models.product_line import SysProductLine
from app.models.rbac import SysRole, SysMenu, SysRoleMenu
from app.services.authorization import get_current_user_context


class Cursor:
    def __init__(self):
        self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
    def fetchone(self):
        return {'total': 51}
    def fetchall(self):
        if 'AS value' in self.calls[-1][0]:
            return [{'value':'原材料仓'}]
        return [{'FID': 'x', 'FBaseQty': Decimal('-12.30'), 'MaterialName': '=1+1'}]
    def close(self):
        pass


class Connection:
    def __init__(self):
        self.c = Cursor()
    def cursor(self):
        return self.c


class InventoryContract(unittest.TestCase):
    def reader(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.inventory_reader'), '库存读取器尚未实现')
        from app.services import inventory_reader
        return inventory_reader

    def test_schema_has_all_view_columns_and_decimal_quantity(self):
        r = self.reader()
        self.assertEqual([f['key'] for f in r.report_fields()], ['FID','Organization','Stock','MaterialCode','MaterialName','FSPECIFICATION','Brand','Material','SupplierNumber','FBaseQty','Unit'])
        self.assertEqual(r.public_row({'FID':'x','FBaseQty':Decimal('999999.99'),'secret':'no'})['FBaseQty'], '999999.99')
        self.assertNotIn('secret', r.public_row({'secret':'no'}))

    def test_scope_before_pagination_and_parameterized_wildcards(self):
        r = self.reader(); c = Connection()
        q = r.InventoryQuery(keyword="%_[x]' OR 1=1--", page=2, page_size=50,
            filters=json.dumps([{'field':'FBaseQty','operator':'between','value':-2,'valueEnd':5}]))
        result = r.list_inventory(c, q, [200292])
        self.assertEqual(result['total'],51)
        for sql, params in c.c.calls:
            self.assertIn('FSTOCKORGID',sql)
            self.assertIn(200292, params)
            self.assertNotIn('OR 1=1--',sql)
        self.assertEqual(c.c.calls[-1][1][-2:],(50,50))
        self.assertIn('ESCAPE',c.c.calls[-1][0])

    def test_bad_columns_operators_numbers_and_ranges_are_rejected(self):
        from pydantic import ValidationError
        r = self.reader()
        for conditions in ([{'field':'x;drop table x','operator':'equals','value':'x'}],
                [{'field':'Brand','operator':'greaterThan','value':'x'}],
                [{'field':'FBaseQty','operator':'equals','value':'NaN'}],
                [{'field':'FBaseQty','operator':'between','value':3,'valueEnd':1}]):
            with self.assertRaises(ValidationError):
                r.InventoryQuery(filters=json.dumps(conditions))
        for args in ({'sort':'DROP'}, {'page_size':501}, {'filters':'{}'}, {'filters':'['}, {'filters':'[]'*10000}):
            with self.assertRaises(ValidationError):r.InventoryQuery(**args)

    def test_empty_grants_never_issue_sql_and_foreign_org_is_empty(self):
        r = self.reader(); c = Connection()
        self.assertEqual(r.list_inventory(c,r.InventoryQuery(),[])['total'],0)
        self.assertEqual(c.c.calls,[])
        self.assertEqual(r.list_inventory(c,r.InventoryQuery(organization_id=42),[1])['total'],0)
        self.assertEqual(c.c.calls,[])

    def test_candidate_queries_use_same_scope_and_literal_keyword(self):
        r = self.reader(); c = Connection()
        r.list_options(c,'Stock','%', [12])
        sql, params = c.c.calls[0]
        self.assertIn('FSTOCKORGID',sql);self.assertIn(12,params)
        self.assertIn('%~%%',params)


class InventoryApiContract(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('app.api.inventory_reports'), '库存接口尚未实现')
        from app.api import inventory_reports
        self.api=inventory_reports
        engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
        Base.metadata.create_all(engine); self.db=Session(engine)
        self.addCleanup(engine.dispose);self.addCleanup(self.db.close)
        self.db.add(SysProductLine(id=7,source_key='kingdee',organization_id=200292,organization_code='X',organization_name='原名称',display_name='重命名',name_key='重命名'))
        self.db.commit()
        self.ctx={'user_id':1,'permissions':['report:inventory:view'],'product_line_ids':[7]}
        self.app=FastAPI();self.app.include_router(self.api.router)
        self.app.dependency_overrides[get_db]=lambda:self.db
        self.app.dependency_overrides[get_current_user_context]=lambda:self.ctx
        self.client=TestClient(self.app,raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def test_all_routes_are_guarded(self):
        self.ctx['permissions']=[]
        for url in ('','/metadata','/options?field=Stock','/export'):
            self.assertEqual(self.client.get('/api/reports/inventory'+url).status_code,403)

    def test_empty_scope_does_not_contact_erp(self):
        self.ctx['product_line_ids']=[]
        with patch.object(self.api,'purchase_connection') as connection:
            response=self.client.get('/api/reports/inventory')
            self.assertEqual(response.status_code,200);self.assertEqual(response.json()['total'],0)
            self.assertEqual(self.client.get('/api/reports/inventory/options?field=Stock').json()['items'],[])
            connection.assert_not_called()

    def test_metadata_names_are_source_fields_not_user_renames(self):
        data=self.client.get('/api/reports/inventory/metadata').json()
        self.assertEqual(len(data['fields']),11)
        self.assertEqual(data['organizations'][0]['value'],200292)
        self.assertEqual(data['organizations'][0]['label'],'重命名')

    def test_errors_are_sanitized_and_input_validated(self):
        with patch.object(self.api,'purchase_connection',side_effect=RuntimeError('PRIVATE_SECRET')):
            r=self.client.get('/api/reports/inventory')
            self.assertEqual(r.status_code,503);self.assertNotIn('PRIVATE_SECRET',r.text)
        self.assertEqual(self.client.get('/api/reports/inventory?sort=unknown').status_code,422)

    def test_export_scope_limit_formula_and_log(self):
        self.assertEqual(self.client.get('/api/reports/inventory/export').status_code,403)
        self.ctx['permissions'].append('report:inventory:export')
        @contextmanager
        def conn():yield object()
        data={'total':1,'items':[{'FID':'a','MaterialName':'=1+1','FBaseQty':Decimal('-2.30')}]}
        with patch.object(self.api,'purchase_connection',conn),patch.object(self.api,'list_inventory',return_value=data) as read,patch.object(self.api,'record_operation_log') as log:
            r=self.client.get('/api/reports/inventory/export?page=2')
            self.assertEqual(r.status_code,200);self.assertIn("'=1+1",r.text)
            self.assertEqual(read.call_args.args[2],[200292]);self.assertEqual(read.call_args.args[1].page,1)
            self.assertEqual(log.call_count,1)
            read.return_value={'total':501,'items':[]};log.reset_mock()
            self.assertEqual(self.client.get('/api/reports/inventory/export').status_code,422);log.assert_not_called()
            self.ctx['permissions']=['report:inventory:export']
            self.assertEqual(self.client.get('/api/reports/inventory/export').status_code,403)

    def test_menu_migration_does_not_restore_revoked_permissions(self):
        from app.services.inventory_migration import initialize_inventory_report
        self.db.add(SysRole(id=1,role_name='管理员',role_code='admin'));self.db.commit()
        initialize_inventory_report(self.db)
        view=self.db.query(SysMenu).filter_by(permission_code='report:inventory:view').one()
        self.assertEqual(self.db.query(SysRoleMenu).filter_by(role_id=1,menu_id=view.id).count(),1)
        self.db.query(SysRoleMenu).filter_by(role_id=1,menu_id=view.id).delete();self.db.commit()
        initialize_inventory_report(self.db)
        self.assertEqual(self.db.query(SysRoleMenu).filter_by(role_id=1,menu_id=view.id).count(),0)
        from app.services.role_home import validate_role_home
        ids=[x.menu_id for x in self.db.query(SysRoleMenu).filter_by(role_id=1)] + [view.id]
        validate_role_home(self.db,view.parent_id,ids)

    def test_catalog_has_inventory_fields(self):
        from app.services.field_catalog import build_field_catalog
        fields=[x for x in build_field_catalog() if x['module']=='inventory_report']
        self.assertEqual(len(fields),11)
        self.assertTrue(all(x['storage_table']=='YD_JIN_INVENTORY' and not x['editable'] for x in fields))


if __name__=='__main__':unittest.main()
