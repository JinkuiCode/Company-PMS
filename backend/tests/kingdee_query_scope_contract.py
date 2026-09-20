"""金蝶辅助资料查询范围契约；内存传输，不访问真实金蝶。"""
import json
import sqlite3
import unittest
import httpx
from kingdee_app_auth_contract import client_with

class QueryScopeContract(unittest.TestCase):
    def query_rows(self, category, code, records):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE rows(category TEXT, FEntryID INTEGER, FNumber TEXT, FDataValue TEXT, FDescription TEXT)')
        db.executemany('INSERT INTO rows VALUES (?,?,?,?,?)', records)
        def respond(req):
            query = json.loads(json.loads(req.content)['data'])
            predicate = query['FilterString'].replace('FId.FNumber', 'category')
            self.assertEqual(query['FieldKeys'], 'FEntryID,FNumber,FDataValue,FDescription')
            rows = db.execute('SELECT FEntryID,FNumber,FDataValue,FDescription FROM rows WHERE '+predicate+' LIMIT '+str(min(int(query['Limit']), int(query['TopRowCount'])))).fetchall()
            return httpx.Response(200, json=rows)
        try:
            with client_with(respond) as client:
                return client.query_assistant_data('BOS_ASSISTANTDATA_DETAIL', category, code)
        finally:
            db.close()

    def test_same_code_in_other_category_is_not_selected(self):
        row = self.query_rows('xsxm', 'TEST', [('other', 11, 'TEST', 'TEST', '其他类别'), ('xsxm', 22, 'TEST', 'TEST', '销售项目')])
        self.assertEqual(row['FEntryID'], 22)

    def test_other_category_only_means_target_absent(self):
        self.assertIsNone(self.query_rows('xsxm', 'TEST', [('other', 11, 'TEST', 'TEST', '其他类别')]))

    def test_quotes_are_literal_for_both_values(self):
        row = self.query_rows("xs'xm", "P' OR 1=1 --", [('other', 11, 'OTHER', 'OTHER', '其他记录'), ("xs'xm", 22, "P' OR 1=1 --", "P' OR 1=1 --", '目标')])
        self.assertEqual(row['FEntryID'], 22)

    def test_duplicate_in_same_category_stops(self):
        with self.assertRaisesRegex(RuntimeError, '金蝶同类别项目编号存在重复记录，已停止同步'):
            self.query_rows('xsxm', 'TEST', [('xsxm', 11, 'TEST', 'TEST', '重复一'), ('xsxm', 22, 'TEST', 'TEST', '重复二')])

    def test_unexpected_project_code_cannot_be_used_as_update_target(self):
        with client_with(lambda req: httpx.Response(200, json=[[99, 'OTHER', 'OTHER', '其他项目']])) as client:
            with self.assertRaises(RuntimeError):
                client.query_assistant_data('BOS_ASSISTANTDATA_DETAIL', 'xsxm', 'TEST')

    def test_invalid_external_id_is_not_a_create_fallback(self):
        with client_with(lambda req: httpx.Response(200, json=[['', 'TEST', 'TEST', '项目']])) as client:
            with self.assertRaises(RuntimeError):
                client.query_assistant_data('BOS_ASSISTANTDATA_DETAIL', 'xsxm', 'TEST')

if __name__ == '__main__':
    unittest.main()
