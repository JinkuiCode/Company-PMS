"""Candidate lookup must remain scoped and must not depend on nonzero stock."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import stock_detail_reader as reader
from app.services.business_data_scope import ALL_DATA_SCOPE


class Cursor:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchall(self):
        return self.rows


class OptionsContract(unittest.TestCase):
    def lookup(self, cursor, kind='stock', keyword='', scope=None):
        self.assertTrue(hasattr(reader, 'list_candidates'), 'candidate reader not implemented')
        return reader.list_candidates(cursor, kind, keyword, scope)

    def test_empty_scope_never_queries(self):
        cursor = Cursor([])
        self.assertEqual(self.lookup(cursor, scope=[]), {'items': [], 'has_more': False})
        self.assertEqual(cursor.calls, [])

    def test_warehouse_options_use_master_data_and_parameters(self):
        cursor = Cursor([{'value': 20, 'label': '研发仓', 'code': 'CK01'}])
        result = self.lookup(cursor, keyword="%' OR 1=1--", scope=[1, 200292])
        sql, params = cursor.calls[0]
        self.assertIn('T_BD_STOCK', sql)
        self.assertNotIn('INVENTORY', sql.upper())
        self.assertNotIn("OR 1=1--", sql)
        self.assertIn('FUSEORGID IN (%s,%s)', sql)
        self.assertEqual(params[:2], [1, 200292])
        self.assertIn("[%]' OR 1=1--", params[2])
        self.assertEqual(result['items'][0]['value'], 20)

    def test_material_candidates_are_codes_not_org_specific_ids(self):
        cursor = Cursor([{'value': '180102020045', 'label': 'PFA管', 'code': '180102020045'}])
        result = self.lookup(cursor, kind='material', keyword='PFA', scope=ALL_DATA_SCOPE)
        self.assertEqual(result['items'][0]['value'], '180102020045')
        self.assertIn('T_BD_MATERIAL', cursor.calls[0][0])
        self.assertIn('GROUP BY', cursor.calls[0][0])

    def test_unknown_candidate_kind_and_invalid_scope_are_rejected(self):
        for kind, scope in [('table; DROP', [1]), ('stock', [True]), ('stock', ['1'])]:
            with self.subTest(kind=kind, scope=scope), self.assertRaises(ValueError):
                self.lookup(Cursor([]), kind=kind, scope=scope)

    def test_candidate_page_signals_more_without_returning_extra_row(self):
        cursor = Cursor([{'value': n, 'label': str(n), 'code': str(n)} for n in range(101)])
        result = self.lookup(cursor, scope=[1])
        self.assertTrue(result['has_more'])
        self.assertEqual(len(result['items']), 100)


if __name__ == '__main__':
    unittest.main()
