from datetime import date, datetime
from decimal import Decimal as D
from pathlib import Path
import importlib.util
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class NormalizeContract(unittest.TestCase):
    def service(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.stock_detail_normalize'))
        from app.services import stock_detail_normalize
        return stock_detail_normalize

    def row(self, **changes):
        return dict(organization_id=1, material_id=11, stock_id=20, stock_status_id=1,
            owner_type='BD_OwnerOrg', owner_id=1, keeper_type='BD_KeeperOrg', keeper_id=1,
            bill_id=100, entry_id=101, bill_seq=1, bill_no='DOC001', bill_date=date(2026, 9, 1),
            created_at=datetime(2026, 9, 1, 8), base_income_qty=D(12), base_issue_qty=D(0), **changes)

    def unit(self):
        return dict(unit_id=10, numerator=D(6), denominator=D(1), precision=3)

    def test_raw_quantities_are_converted_without_leaking_private_columns(self):
        row = self.row(price=D(100), amount=D(1200))
        result = self.service().normalize_movement(row, 'STK_TRANSFERDIRECT', 'in', self.unit(),
            {'material_code': 'M1', 'material_name': '物料', 'unit_name': '盒'}, '直接调拨单')
        self.assertEqual(result['income_qty'], D('2.000'))
        self.assertEqual(result['row_id'], 'STK_TRANSFERDIRECT:in:100:101')
        self.assertEqual(result['bill_name'], '直接调拨单')
        self.assertEqual(result['inventory_key'].unit_id, 10)
        self.assertNotIn('price', result)
        self.assertNotIn('amount', result)

    def test_batch_text_participates_in_inventory_identity(self):
        service = self.service()
        keys = [service.inventory_key(self.row(lot_no=lot), 10) for lot in ('批次A', '批次B')]
        self.assertNotEqual(*keys)

    def test_sql_integer_zero_is_exact_but_float_remains_rejected(self):
        service = self.service()
        row = dict(self.row(), base_issue_qty=0)
        result = service.normalize_movement(row, 'STK_TRANSFERDIRECT', 'in', self.unit(), {}, '直接调拨单')
        self.assertEqual(result['issue_qty'], D(0))
        with self.assertRaises(TypeError):
            service.normalize_movement(dict(row, base_issue_qty=0.0), 'STK_TRANSFERDIRECT', 'in', self.unit(), {}, '直接调拨单')

    def test_snapshot_aggregates_base_quantities_before_rounding(self):
        rows = [dict(self.row(), snapshot_id=1, base_qty=D('1.001')),
                dict(self.row(), snapshot_id=2, base_qty=D('1.001'))]
        unit = dict(unit_id=10, numerator=D(1), denominator=D(1), precision=2)
        result = self.service().normalize_snapshots(rows, {11: unit})
        self.assertEqual(list(result.values()), [D('2.00')])
        with self.assertRaises(ValueError):
            self.service().normalize_snapshots([rows[0], rows[0]], {11: unit})

    def test_unresolved_snapshot_master_is_not_silently_replaced_with_zero(self):
        row = dict(self.row(), snapshot_id=1, base_qty=D(1), owner_id=None, owner_master_id=10)
        with self.assertRaises(ValueError):
            self.service().normalize_snapshots([row], {11: self.unit()})


if __name__ == '__main__':
    unittest.main()
