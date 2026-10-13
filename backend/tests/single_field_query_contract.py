import json
import sqlite3
from pathlib import Path
import sys
import unittest
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.stock_detail_reader import StockDetailQuery
from app.services.stock_detail_sources import movement_sql
from app.services.stock_detail_snapshots import snapshot_sql
from app.services.report_filters import query_fields,parse_filters,matches_filters

class SingleFieldQuery(unittest.TestCase):
    def query(self, field='material_code'):
        return StockDetailQuery(material='PFA%_[',material_field=field,organization_ids=[1],
            start_date='2026-10-01',end_date='2026-10-13')

    def test_source_and_opening_use_same_single_field(self):
        for field,column in [('material_code','FNUMBER'),('material_name','FNAME'),('specification','FSPECIFICATION')]:
            with self.subTest(field=field):
                for sql,params in (movement_sql('PRD_PickMtrl',self.query(field),[1]),
                    snapshot_sql(self.query(field),1,date(2026,10,1),1)):
                    self.assertIn(column,sql)
                    self.assertNotIn('ML.FNAME LIKE %s OR ML.FSPECIFICATION LIKE %s',sql)
                    self.assertNotIn('PFA',sql)
                    self.assertEqual(sql.count('%s'),len(params))
                    needles=[p for p in params if isinstance(p,str) and 'pfa' in p.lower()]
                    self.assertEqual(len(needles),1)

    def test_invalid_field_cannot_select_arbitrary_source(self):
        with self.assertRaises(ValueError): self.query('owner_name')

    def test_same_text_in_another_field_does_not_match(self):
        from app.services.stock_detail_material_query import material_predicate
        db=sqlite3.connect(':memory:')
        try:
            db.execute("ATTACH DATABASE ':memory:' AS dbo")
            db.execute('CREATE TABLE dbo.T_BD_MATERIAL(FMATERIALID int,FNUMBER text)')
            db.execute('CREATE TABLE dbo.T_BD_MATERIAL_L(FMATERIALID int,FLOCALEID int,FNAME text,FSPECIFICATION text)')
            db.executemany('INSERT INTO dbo.T_BD_MATERIAL VALUES(?,?)',[(1,'PFA'),(2,'M2'),(3,'M3')])
            db.executemany('INSERT INTO dbo.T_BD_MATERIAL_L VALUES(?,2052,?,?)',[(1,'钢管','10mm'),(2,'PFA','20mm'),(3,'铝管','PFA')])
            for field,identity in [('material_code',1),('material_name',2),('specification',3)]:
                query=self.query(field).model_copy(update={'material':'PFA'})
                sql,params=material_predicate(query)
                translated=sql.replace('%s','?').replace('%%','%').replace(' + ',' || ')
                rows=db.execute('SELECT M.FMATERIALID FROM dbo.T_BD_MATERIAL M WHERE '+translated,params).fetchall()
                self.assertEqual(rows,[(identity,)])
        finally:db.close()

    def test_specification_survives_quantity_normalization(self):
        from app.services.stock_detail_normalize import normalize_movement
        from datetime import datetime
        from decimal import Decimal
        row=dict(organization_id=1,material_id=11,stock_id=20,stock_status_id=1,
            owner_type='BD_OwnerOrg',owner_id=1,keeper_type='BD_KeeperOrg',keeper_id=1,
            bill_id=100,entry_id=101,bill_seq=1,bill_no='DOC001',bill_date=date(2026,10,1),
            created_at=datetime(2026,10,1,8),base_income_qty=Decimal(12),base_issue_qty=Decimal(0))
        unit=dict(unit_id=10,numerator=Decimal(1),denominator=Decimal(1),precision=2)
        result=normalize_movement(row,'STK_TRANSFERDIRECT','in',unit,{'specification':'PFA'},'直接调拨单')
        self.assertEqual(result.get('specification'),'PFA')

    def test_exact_material_operator_does_not_expand_opening_scope(self):
        from app.services.stock_detail_material_query import material_predicate
        query=StockDetailQuery(material='M1',material_field='material_code',material_operator='equals',
            organization_ids=[1],start_date='2026-10-01',end_date='2026-10-13')
        sql,params=material_predicate(query)
        db=sqlite3.connect(':memory:')
        try:
            db.execute('CREATE TABLE material(FNUMBER text)')
            db.executemany('INSERT INTO material VALUES(?)',[('M1',),('M10',),('XM1',)])
            rows=db.execute('SELECT FNUMBER FROM material M WHERE '+sql.replace('%s','?').replace('%%','%').replace(' + ',' || '),params).fetchall()
            self.assertEqual(rows,[('M1',)])
            opening_sql,opening_params=snapshot_sql(query,1,date(2026,10,1),1)
            self.assertIn(sql,opening_sql)
            self.assertEqual(opening_params[-len(params):],params)
        finally:db.close()

    def test_stock_specification_query_is_typed_and_independent(self):
        self.assertIn('specification',[f['field'] for f in query_fields('stock-detail')])
        condition=parse_filters(json.dumps([dict(schemaVersion=2,field='specification',operator='contains',value='PFA')]),'stock-detail')
        self.assertFalse(matches_filters({'material_name':'PFA','specification':'steel'},condition))
        self.assertTrue(matches_filters({'material_name':'steel','specification':'PFA'},condition))

if __name__=='__main__':unittest.main()
