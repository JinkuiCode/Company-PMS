from decimal import Decimal as D
from pathlib import Path
import importlib.util
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class Cursor:
    def __init__(self, batches):
        self.batches, self.calls = iter(batches), []

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchall(self):
        return next(self.batches)


class CatalogContract(unittest.TestCase):
    def service(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.stock_detail_catalog'))
        from app.services import stock_detail_catalog
        return stock_detail_catalog

    def test_references_use_bound_ids_and_chinese_names_only(self):
        cursor = Cursor([
            [dict(id=11, code='M1', name='PFA管', unit_id=10, numerator=D(1), denominator=D(1), precision=2, unit_name='米')],
            [dict(id=20, name='研发仓')], [dict(id=1, name='可用')],
            [dict(id=1, owner_type='BD_OwnerOrg', name='组织名称')],
        ])
        rows = [dict(material_id=11, stock_id=20, stock_status_id=1, owner_type='BD_OwnerOrg', owner_id=1)]
        service = self.service()
        catalog = service.load_catalog(cursor, rows)
        labels = service.row_labels(rows[0], catalog)
        self.assertEqual(labels['material_name'], 'PFA管')
        self.assertEqual(labels['unit_name'], '米')
        self.assertEqual(labels['owner_name'], '组织名称')
        self.assertEqual(labels['owner_type_name'], '业务组织')
        for sql, params in cursor.calls:
            self.assertIn('2052', sql)
            self.assertEqual(sql.count('%s'), len(params))
            self.assertNotIn('FPRICE', sql)
            self.assertNotIn('FAMOUNT', sql)

    def test_missing_material_unit_and_duplicate_ids_fail_closed(self):
        service = self.service()
        rows = [dict(material_id=11, stock_id=20, stock_status_id=1, owner_type='', owner_id=0)]
        for batch in ([], [dict(id=11, unit_id=None)], [dict(id=11), dict(id=11)]):
            with self.subTest(batch=batch), self.assertRaises(ValueError):
                service.load_catalog(Cursor([batch]), rows)

    def test_empty_rows_do_not_query(self):
        cursor = Cursor([])
        self.service().load_catalog(cursor, [])
        self.assertEqual(cursor.calls, [])


if __name__ == '__main__':
    unittest.main()
