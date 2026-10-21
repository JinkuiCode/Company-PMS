"""Synthetic master-data SQL on in-memory SQLite; no ERP or existing PMS DB."""
from pathlib import Path
import importlib.util
import sqlite3
import re
import sys
import unittest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.business_data_scope import ALL_DATA_SCOPE


class Cursor:
    def __init__(self, shared=0):
        self.db = sqlite3.connect(':memory:',check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("ATTACH DATABASE ':memory:' AS dbo")
        self.db.create_function('CONCAT', -1, lambda *v: ''.join(str(x) for x in v))
        self.db.create_collation('Latin1_General_100_BIN2', lambda a,b: (a>b)-(a<b))
        self.db.executescript('''CREATE TABLE dbo.T_BD_MATERIAL(FMATERIALID INTEGER,FNUMBER TEXT,FUSEORGID INTEGER);
            CREATE TABLE dbo.T_BD_MATERIAL_L(FMATERIALID INTEGER,FNAME TEXT,FLOCALEID INTEGER);
            CREATE TABLE dbo.T_META_BASEDATATYPE(FBASEDATATYPEID TEXT,FSTRATEGYTYPE INTEGER);''')
        self.db.execute('INSERT INTO dbo.T_META_BASEDATATYPE VALUES (?,?)', ('BD_MATERIAL', shared))
        self.calls=[]

    def add(self, code, name, org=11):
        identity=self.db.execute('SELECT COUNT(*) FROM dbo.T_BD_MATERIAL').fetchone()[0]+1
        self.db.execute('INSERT INTO dbo.T_BD_MATERIAL VALUES (?,?,?)',(identity,code,org))
        self.db.execute('INSERT INTO dbo.T_BD_MATERIAL_L VALUES (?,?,2052)',(identity,name))

    def execute(self, sql, params):
        self.calls.append((sql,params))
        self.result=self.db.execute(re.sub(r"\bN'", "'", sql).replace('%s','?'),params)

    def fetchall(self): return [dict(r) for r in self.result.fetchall()]
    def close(self): pass


class Materials(unittest.TestCase):
    def setUp(self):
        module=Path(__file__).resolve().parents[1]/'app/services/report_material_reference.py'
        self.assertTrue(module.exists(), 'shared material reference service is missing')
        from app.services import report_material_reference
        self.service=report_material_reference

    def test_string_normalization_and_rejection(self):
        self.assertEqual(self.service.normalize_codes([' 0007-A ','0007-a','00B']), ['0007-a','00b'])
        for value in [[],[1],[True],[' '],['a\nb'],['x'*257],['a']*1001,'abc']:
            with self.subTest(value=str(value)[:20]),self.assertRaises(HTTPException): self.service.normalize_codes(value)

    def test_scoped_search_is_master_based_and_distinct(self):
        c=Cursor();c.add('0007-A','阀门',11);c.add('0007-A','阀门二',12);c.add('0008-B','未授权',99)
        result=self.service.list_material_candidates(c,'', [11,12],page=1,page_size=50)
        self.assertEqual(result['total'],1);row=result['items'][0]
        self.assertEqual((row['value'],row['code']),('0007-a','0007-A'))
        self.assertIn('2',row['label'])
        self.assertNotIn('INVENTORY',' '.join(sql for sql,_ in c.calls).upper())

    def test_shared_material_does_not_require_an_outside_business_org(self):
        c=Cursor(shared=1);c.add('0007-A','共享物料',99)
        self.assertEqual(self.service.list_material_candidates(c,'',[11])['items'][0]['value'],'0007-a')
        empty=Cursor(shared=1);empty.add('0007-A','共享物料',99)
        self.assertEqual(self.service.list_material_candidates(empty,'',[])['total'],0)
        self.assertEqual(empty.calls,[])

    def test_identity_validation_rejects_missing_or_unauthorized_codes(self):
        c=Cursor();c.add('0007-A','甲',11);c.add('0008-B','乙',99)
        self.assertEqual(self.service.require_material_codes(c,['0007-A'],[11]),['0007-a'])
        for scope,ids in [([11],['0007-a','0008-b']),([],['0007-a']),([11],['missing'])]:
            with self.subTest(scope=scope,ids=ids),self.assertRaises(HTTPException):self.service.require_material_codes(c,ids,scope)

    def test_full_paging_and_ids_are_not_top100(self):
        c=Cursor()
        for i in range(1001):c.add(f'{i:04}-A',f'物料{i}')
        first=self.service.list_material_candidates(c,'',[11],page=1,page_size=500)
        last=self.service.list_material_candidates(c,'',[11],page=3,page_size=500)
        self.assertEqual((first['total'],len(first['items']),first['has_more']),(1001,500,True))
        self.assertEqual(len(last['items']),1)
        self.assertEqual(len(self.service.require_material_codes(c,[f'{i:04}-A' for i in range(1000)],[11])),1000)

    def test_search_and_batch_bind_values_and_keep_diagnostics(self):
        c=Cursor();c.add("A%'--",'阀门');c.add('B','阀门')
        found=self.service.list_material_candidates(c,"%'--",[11])
        self.assertEqual(found['total'],1)
        self.assertTrue(all("%'--" not in sql for sql,_ in c.calls))
        batch=self.service.list_material_candidates(c,'',[11],batch_field='name',batch_values=['阀门','阀门','无'])
        self.assertEqual(batch['batch']['duplicate_count'],1)
        self.assertEqual(batch['batch']['unmatched_values'],['无'])
        self.assertEqual(batch['batch']['ambiguous_values'],['阀门'])
        with self.assertRaises(HTTPException):self.service.list_material_candidates(c,'x',[11],ids=['b'])

    def test_organization_intersection_never_treats_empty_as_all(self):
        f=self.service.material_organizations
        self.assertEqual(f([11,99],[11,12]),[11]);self.assertEqual(f([],[]),[])
        self.assertIs(f([],ALL_DATA_SCOPE),ALL_DATA_SCOPE)
        self.assertEqual(f([11],ALL_DATA_SCOPE),[11])
        with self.assertRaises(HTTPException):f([True],[11])

    def test_ambiguous_comparison_key_is_rejected(self):
        class BadCursor:
            def execute(self,*args):pass
            def fetchall(self):return [{'total':1,'value':'a','code':'A','label':'甲','key_count':2}]
        with self.assertRaises(HTTPException):self.service.list_material_candidates(BadCursor(),'', [11])

    def test_ambiguous_name_batches_fail_explicitly_even_across_frontend_chunks(self):
        c=Cursor();c.add('0007-A','Alpha',11);c.add('0007-A','Beta',12)
        for values in [['Alpha'],['Beta'],['Alpha','Beta']]:
            with self.subTest(values=values),self.assertRaisesRegex(HTTPException,'多个名称|编码'):
                self.service.list_material_candidates(c,'',[11,12],batch_field='name',batch_values=values)
        self.assertEqual(self.service.list_material_candidates(c,'Beta',[11,12])['total'],1,'ordinary character search remains available')


if __name__=='__main__':unittest.main()
