"""Normalized-quantity arithmetic tests, independent of ERP extraction."""
from datetime import date
from decimal import Decimal as D
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class BalanceContract(unittest.TestCase):
    def service(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.stock_detail_balance'))
        from app.services import stock_detail_balance
        return stock_detail_balance

    def key(self, **changes):
        args=dict(organization_id=1,material_id=4465850,stock_id=4397043,
                  stock_status_id=10000,owner_type='BD_OwnerOrg',owner_id=1,unit_id=10087)
        args.update(changes)
        return self.service().InventoryKey(**args)

    def test_six_sample_movements_preserve_balances_across_pages(self):
        s=self.service();k=self.key()
        rows=[{'inventory_key':k,'income_qty':D(i),'issue_qty':D(o),'row_id':n}
              for n,(i,o) in enumerate([(6,0),(0,6),(10,0),(0,10),(20,0),(0,20)])]
        result=list(s.running_balances(iter(rows),{k:D(0)}))
        self.assertEqual([r['balance_qty'] for r in result],[D(6),D(0),D(10),D(0),D(20),D(0)])
        self.assertEqual(result[3:5][0]['balance_qty'],D(0))
        self.assertNotIn('balance_qty',rows[0])

    def test_dimensions_must_not_be_mixed(self):
        s=self.service();keys=[self.key(),self.key(organization_id=2),self.key(stock_id=2),
            self.key(owner_id=2),self.key(stock_status_id=2),self.key(unit_id=2),
            self.key(lot_id=2),self.key(stock_location_id=2),self.key(mto_no='P1')]
        rows=[{'inventory_key':k,'income_qty':D(1),'issue_qty':D(0)} for k in keys]
        balances=list(s.running_balances(rows,{k:D(i) for i,k in enumerate(keys)}))
        self.assertEqual([r['balance_qty'] for r in balances],list(map(D,range(1,10))))

    def test_negative_receipt_is_not_changed_into_positive_issue(self):
        s=self.service();k=self.key()
        rows=[{'inventory_key':k,'income_qty':D('-2.25'),'issue_qty':D(0)},
              {'inventory_key':k,'income_qty':D(0),'issue_qty':D('-1.5')}]
        result=list(s.running_balances(rows,{k:D(5)}))
        self.assertEqual([r['balance_qty'] for r in result],[D('2.75'),D('4.25')])

    def test_page_two_uses_prior_movements_not_opening_again(self):
        s=self.service();k=self.key()
        rows=[{'inventory_key':k,'income_qty':D(10),'issue_qty':D(0)},
              {'inventory_key':k,'income_qty':D(0),'issue_qty':D(3)},
              {'inventory_key':k,'income_qty':D(0),'issue_qty':D(4)}]
        result=list(s.running_balances(rows,{k:D(5)}))
        self.assertEqual(result[2:3][0]['balance_qty'],D(8))

    def test_signed_movements_follow_kingdee_columns(self):
        s=self.service()
        self.assertEqual(s.signed_movement('income',D(4)),(D(4),D(0)))
        self.assertEqual(s.signed_movement('negative_income',D(4)),(D(-4),D(0)))
        self.assertEqual(s.signed_movement('negative_issue',D(4)),(D(0),D(-4)))
        self.assertEqual(s.signed_movement('transfer_in',D(4),'RETURN'),(D(0),D(-4)))
        self.assertEqual(s.signed_movement('transfer_out',D(4),'RETURN'),(D(-4),D(0)))
        self.assertEqual(s.signed_movement('transfer_out',D(4),'GENERAL'),(D(0),D(4)))
        self.assertEqual(s.signed_movement('conversion',D(4),'A'),(D(0),D(4)))
        self.assertEqual(s.signed_movement('conversion',D(4),'B'),(D(4),D(0)))
        with self.assertRaises(ValueError):s.signed_movement('transfer_in',D(4),'UNKNOWN')
        with self.assertRaises(ValueError):s.signed_movement('unknown',D(4))

    def test_unit_conversion_rounds_half_away_from_zero(self):
        s=self.service()
        self.assertEqual(s.stock_quantity(D('1.005'),D(1),D(1),2),D('1.01'))
        self.assertEqual(s.stock_quantity(D('-1.005'),D(1),D(1),2),D('-1.01'))
        self.assertEqual(s.stock_quantity(D(12),D(6),D(1),3),D('2.000'))
        self.assertEqual(s.stock_quantity(D(12),D(0),D(1),2),D('12.00'))
        self.assertEqual(s.stock_quantity(D(12),D(6),D(0),2),D('12.00'))

    def test_rejects_unverified_openings_and_nonfinite_quantities(self):
        s=self.service();k=self.key()
        row={'inventory_key':k,'income_qty':D(1),'issue_qty':D(0)}
        with self.assertRaises(ValueError):list(s.running_balances([row],{}))
        for n in (D('NaN'),D('Infinity'),1.1):
            with self.assertRaises((ValueError,TypeError)):
                list(s.running_balances([{**row,'income_qty':n}],{k:D(0)}))
        with self.assertRaises(ValueError):s.stock_quantity(D(1),D(1),D(1),-1)

    def test_opening_uses_only_movements_after_verified_baseline(self):
        s = self.service(); k = self.key(); other = self.key(stock_id=2)
        baseline = {k: D(5), other: D(10)}
        rows = [dict(inventory_key=k, row_id='one', bill_date=date(2026, 5, 1), income_qty=D(2), issue_qty=D(0)),
                dict(inventory_key=k, row_id='two', bill_date=date(2026, 5, 31), income_qty=D(0), issue_qty=D(3))]
        result = s.derive_openings(date(2026, 5, 1), date(2026, 6, 1), baseline, rows)
        self.assertEqual(result, {k: D(4), other: D(10)})
        self.assertEqual(baseline[k], D(5))

    def test_opening_rejects_duplicates_wrong_dates_and_unknown_dimensions(self):
        s = self.service(); k = self.key()
        row = dict(inventory_key=k, row_id='one', bill_date=date(2026, 5, 31), income_qty=D(2), issue_qty=D(0))
        for rows in ([row, row], [{**row, 'bill_date': date(2026, 6, 1)}],
                     [{**row, 'bill_date': date(2026, 4, 30)}],
                     [{**row, 'inventory_key': self.key(stock_id=2)}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                s.derive_openings(date(2026, 5, 1), date(2026, 6, 1), {k: D(5)}, rows)
        with self.assertRaises(ValueError):
            s.derive_openings(date(2026, 6, 2), date(2026, 6, 1), {k: D(5)}, [])


if __name__=='__main__':unittest.main()
