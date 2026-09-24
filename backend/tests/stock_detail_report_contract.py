"""Query boundary tests; these do not establish ERP source completeness."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pydantic import ValidationError
from app.services.business_data_scope import ALL_DATA_SCOPE


class StockDetailQueryContract(unittest.TestCase):
    def reader(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.stock_detail_reader'))
        from app.services import stock_detail_reader
        return stock_detail_reader

    def query(self, **changes):
        args = dict(material='180102020045', start_date='2026-06-01', end_date='2026-09-23')
        args.update(changes)
        return self.reader().StockDetailQuery(**args)

    def test_material_is_required_even_when_restoring_saved_query(self):
        r = self.reader()
        for value in ('', ' ', '\t\n', '\u3000', None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.query(material=value)
        with self.assertRaises(ValidationError):
            r.StockDetailQuery(start_date='2026-06-01', end_date='2026-09-23')
        self.assertEqual(self.query(material='  PFA管  ').material, 'PFA管')

    def test_dates_paging_and_candidate_id_validation(self):
        for args in ({'end_date':'2026-05-31'}, {'start_date':''}, {'start_date':'bad'},
                     {'page':0}, {'page_size':501}, {'stock_id':0}, {'stock_id':-1},
                     {'stock_id':'自由输入仓库'}, {'stock':'原材料仓'}, {'organization_id':-1}):
            with self.subTest(args=args), self.assertRaises(ValidationError):
                self.query(**args)
        q = self.query(stock_id=4397043)
        self.assertEqual(q.page_size, 50)
        self.assertIsNone(self.query().stock_id)

    def test_permission_scope_fails_closed_and_all_data_is_explicit(self):
        r = self.reader()
        self.assertEqual(r.effective_organizations(self.query(), None), [])
        self.assertEqual(r.effective_organizations(self.query(), []), [])
        self.assertEqual(r.effective_organizations(self.query(), [2, 1, 2, True, -1]), [1, 2])
        self.assertEqual(r.effective_organizations(self.query(organization_id=3), [1, 2]), [])
        self.assertEqual(r.effective_organizations(self.query(organization_id=2), [1, 2]), [2])
        self.assertIs(r.effective_organizations(self.query(), ALL_DATA_SCOPE), ALL_DATA_SCOPE)
        self.assertEqual(r.effective_organizations(self.query(organization_id=3), ALL_DATA_SCOPE), [3])

    def test_public_fields_exclude_prices_and_internal_ids(self):
        r = self.reader()
        fields = r.report_fields()
        self.assertEqual([f['key'] for f in fields][-4:], ['opening_qty','income_qty','issue_qty','balance_qty'])
        self.assertEqual(len({f['key'] for f in fields}),len(fields))
        self.assertFalse(any(word in str(fields).lower() for word in ['price','amount','cost']))
        self.assertEqual([f['label'] for f in fields if f['key']=='bill_no'], ['单据编号'])

    def test_multiple_organizations_intersect_current_permissions(self):
        r = self.reader()
        q = self.query(organization_ids=[3, 2, 2, 1])
        self.assertEqual(r.effective_organizations(q, [2, 1]), [1, 2])
        self.assertEqual(r.effective_organizations(q, []), [])
        self.assertEqual(r.effective_organizations(q, ALL_DATA_SCOPE), [1, 2, 3])
        self.assertEqual(r.effective_organizations(self.query(organization_ids=[]), [2]), [2])
        for ids in ([0], [-1], ['bad']):
            with self.assertRaises(ValidationError):
                self.query(organization_ids=ids)
        with self.assertRaises(ValidationError):
            self.query(organization_ids=[2], organization_id=1)


if __name__ == '__main__':
    unittest.main()
