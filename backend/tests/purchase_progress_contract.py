"""Quantity accounting tests do not require ERP credentials or database writes."""
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class PurchaseProgressContract(unittest.TestCase):
    def setUp(self):
        from app.services.purchase_progress import summarize_requisition
        self.summarize = summarize_requisition
        self.request = dict(id=7, bill_id=10, material_id=20, base_unit_id=1,
                            requested='18', approved='18', approved_base='18', effective=True)
        self.orders = [dict(id=100, bill_id=11, material_id=20, base_unit_id=1, effective=True),
                       dict(id=101, bill_id=12, material_id=20, base_unit_id=1, effective=True)]
        self.links = [dict(order_id=100, request_id=7, request_bill_id=10, base_qty='10', old_base_qty='18'),
                      dict(order_id=101, request_id=7, request_bill_id=10, base_qty='8')]
        self.receipts = [dict(id=200, order_id=101, material_id=20, base_unit_id=1,
                             base_qty='8', effective=True)]

    def result(self, **kwargs):
        kwargs.setdefault('complete', True)
        return self.summarize(self.request, self.orders, self.links, self.receipts, **kwargs)

    def test_current_allocation_not_original_carried_quantity(self):
        r = self.result()
        self.assertEqual(r['ordered'], Decimal('18'))
        self.assertEqual(r['received'], Decimal('8'))
        self.assertEqual(r['pending_order'], Decimal('0'))
        self.assertEqual(r['pending_receipt'], Decimal('10'))

    def test_split_receipts_do_not_multiply_order_quantity(self):
        self.receipts = [dict(self.receipts[0], id=200, base_qty='3'),
                         dict(self.receipts[0], id=201, base_qty='5')]
        self.assertEqual(self.result()['ordered'], Decimal('18'))
        self.assertEqual(self.result()['received'], Decimal('8'))

    def test_return_from_receiving_is_not_stock_return(self):
        returns = [dict(id=300, receipt_id=200, source_kind='stock', base_qty='2', base_unit_id=1, material_id=20, effective=True),
                   dict(id=301, receipt_id=None, source_kind='receive', base_qty='4', effective=True)]
        r = self.result(returns=returns)
        self.assertEqual(r['returned'], Decimal('2'))
        self.assertEqual(r['net_received'], Decimal('6'))
        self.assertEqual(r['pending_receipt'], Decimal('12'))

    def test_merged_application_is_not_arbitrarily_prorated(self):
        self.links.append(dict(order_id=101, request_id=8, request_bill_id=10, base_qty='4'))
        r = self.result()
        self.assertIsNone(r['received'])
        self.assertIsNone(r['pending_receipt'])
        self.assertIn('ambiguous_receipt_allocation', r['issues'])

    def test_source_head_or_material_mismatch_is_not_counted(self):
        self.links[0]['request_bill_id'] = 999
        self.assertIsNone(self.result()['ordered'])
        self.links[0]['request_bill_id'] = 10
        self.orders[0]['material_id'] = 999
        self.assertIsNone(self.result()['ordered'])

    def test_unit_conversion_uses_approved_base_quantity(self):
        self.request.update(requested='1.8', approved='1.8', approved_base='18')
        r = self.result()
        self.assertEqual(r['ordered'], Decimal('1.8'))
        self.assertEqual(r['received'], Decimal('0.8'))

    def test_different_base_units_fail_closed(self):
        self.receipts[0]['base_unit_id'] = 999
        r = self.result()
        self.assertIsNone(r['received'])
        self.assertIn('receipt_unit_mismatch', r['issues'])

    def test_drafts_are_excluded_without_removing_closed_history(self):
        self.orders[0]['effective'] = False
        self.orders[1]['closed'] = True
        r = self.result()
        self.assertEqual(r['ordered'], Decimal('8'))
        self.assertEqual(r['received'], Decimal('8'))

    def test_duplicate_receipt_ids_are_rejected(self):
        self.receipts.append(dict(self.receipts[0]))
        self.assertIn('duplicate_receipt', self.result()['issues'])
        self.assertIsNone(self.result()['received'])

    def test_over_delivery_is_not_hidden_by_zero_clamping(self):
        self.receipts[0]['base_qty'] = '20'
        r = self.result()
        self.assertEqual(r['pending_receipt'], Decimal('-2'))
        self.assertIn('over_delivery', r['issues'])

    def test_unknown_or_nonfinite_quantity_does_not_become_zero(self):
        for value in (None, 'NaN', 'Infinity', 'bad'):
            with self.subTest(value=value):
                self.links[0]['base_qty'] = value
                self.assertIsNone(self.result()['ordered'])

    def test_unapproved_request_has_no_pending_order(self):
        self.request['effective'] = False
        self.assertIsNone(self.result()['pending_order'])

    def test_return_must_match_receipt_material_and_base_unit(self):
        for patch in ({'material_id': 999}, {'base_unit_id': 999}):
            row = dict(id=300, receipt_id=200, source_kind='stock', base_qty='2',
                       base_unit_id=1, material_id=20, effective=True)
            row.update(patch)
            self.assertIsNone(self.result(returns=[row])['net_received'])

    def test_unknown_state_is_not_a_truthy_effective_flag(self):
        self.orders[0]['effective'] = 'C'
        r = self.result()
        self.assertIsNone(r['ordered'])
        self.assertIn('unknown_order_state', r['issues'])

    def test_return_exceeding_original_receipt_is_an_exception(self):
        row = dict(id=300, receipt_id=200, source_kind='stock', base_qty='9',
                   base_unit_id=1, material_id=20, effective=True)
        r = self.result(returns=[row])
        self.assertIsNone(r['net_received'])
        self.assertIn('return_exceeds_receipt', r['issues'])

    def test_partial_chain_never_pretends_to_be_a_complete_total(self):
        r = self.result(complete=False)
        self.assertIsNone(r['ordered'])
        self.assertIsNone(r['net_received'])
        self.assertIn('incomplete_chain', r['issues'])

    def test_recurring_conversion_preserves_exact_completion(self):
        from app.services.purchase_reader import progress_for
        self.request.update(approved='1', approved_base='3')
        self.links[0]['base_qty'] = '1'
        self.links[1]['base_qty'] = '2'
        self.receipts[0]['base_qty'] = '3'
        result = self.result()
        self.assertEqual(result['ordered'], Decimal('1'))
        self.assertEqual(result['pending_order'], Decimal('0'))
        self.assertEqual(progress_for(result), 'complete')

    def test_tiny_real_base_balance_is_not_tolerated_or_rounded_away(self):
        from app.services.purchase_reader import progress_for
        self.request.update(approved='1', approved_base='3')
        self.links[0]['base_qty'] = '1'
        self.receipts = []
        for quantity, expected in [('2', 'receiving'), ('1.999999999', 'ordering'),
                                   ('2.000000001', 'review')]:
            with self.subTest(quantity=quantity):
                self.links[1]['base_qty'] = quantity
                self.assertEqual(progress_for(self.result()), expected)


if __name__ == '__main__':
    unittest.main()
