"""Exercise report assembly independently of database credentials."""
from datetime import date, datetime
from decimal import Decimal as D
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import stock_detail_reader as reader
from app.services.stock_detail_balance import InventoryKey


class DatasetContract(unittest.TestCase):
    key = InventoryKey(1, 10, 20, 10000, 'BD_OwnerOrg', 1, 10087)

    def query(self, **kwargs):
        return reader.StockDetailQuery(material='PFA', organization_ids=[1], start_date='2026-06-01',
                                       end_date='2026-06-30', **kwargs)

    def row(self, entry, day, income='0', issue='0', **kwargs):
        return dict(inventory_key=self.key, row_id=str(entry), bill_date=date(2026, 6, day),
                    created_at=datetime(2026, 6, day, 10), source_order=0,
                    bill_no=f'DOC{entry}', bill_seq=entry, material_code='PFA',
                    income_qty=D(income), issue_qty=D(issue), **kwargs)

    def assemble(self, rows, **kwargs):
        self.assertTrue(hasattr(reader, 'assemble_page'), 'report assembly not implemented')
        return reader.assemble_page(self.query(**kwargs), rows,
                                    {self.key: D('5')}, opening_date=date(2026, 6, 1))

    def test_calculates_before_paging_and_keeps_openings_separate(self):
        result = self.assemble([self.row(1, 1, '6'), self.row(2, 2, issue='4'),
                                self.row(3, 3, '10')], page=2, page_size=2)
        self.assertEqual(result['total'], 3)
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['items'][0]['balance_qty'], D('17'))
        self.assertEqual(result['openings'][0]['opening_qty'], D('5'))

    def test_same_day_sort_is_stable_and_input_is_not_mutated(self):
        rows = [self.row(2, 1, issue='4'), self.row(1, 1, '6')]
        result = self.assemble(rows)
        self.assertEqual([r['row_id'] for r in result['items']], ['1', '2'])
        self.assertEqual([r['balance_qty'] for r in result['items']], [D('11'), D('7')])
        self.assertNotIn('balance_qty', rows[0])

    def test_public_payload_does_not_leak_source_or_financial_fields(self):
        result = self.assemble([self.row(1, 1, '6', price=D('99'), password='secret')])
        self.assertNotIn('price', result['items'][0])
        self.assertNotIn('password', result['items'][0])
        self.assertNotIn('inventory_key', result['items'][0])
        self.assertNotIn('created_at', result['items'][0])

    def test_rejects_duplicate_movements_instead_of_double_counting(self):
        row = self.row(1, 1, '6')
        with self.assertRaisesRegex(ValueError, '重复'):
            self.assemble([row, row.copy()])

    def test_rejects_incorrect_opening_date_and_out_of_period_rows(self):
        self.assertTrue(hasattr(reader, 'assemble_page'))
        with self.assertRaisesRegex(ValueError, '期初'):
            reader.assemble_page(self.query(), [], {self.key: D(0)},
                                 opening_date=date(2026, 5, 31))
        row = self.row(1, 1, '6'); row['bill_date'] = date(2026, 7, 1)
        with self.assertRaisesRegex(ValueError, '日期'):
            self.assemble([row])

    def test_empty_page_does_not_erase_total_or_opening(self):
        result = self.assemble([self.row(1, 1, '6')], page=3, page_size=1)
        self.assertEqual(result['items'], [])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['openings'][0]['opening_qty'], D('5'))


if __name__ == '__main__':
    unittest.main()
