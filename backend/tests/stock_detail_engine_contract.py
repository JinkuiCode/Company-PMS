from datetime import date, datetime
from decimal import Decimal as D
from pathlib import Path
import importlib.util
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.stock_detail_baseline import Baseline
from app.services.stock_detail_reader import StockDetailQuery, assemble_page


class EngineContract(unittest.TestCase):
    def service(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.stock_detail_engine'))
        from app.services import stock_detail_engine
        return stock_detail_engine

    def test_registry_requires_snapshot_and_rejects_custom_plugin(self):
        service = self.service()
        rows = [{'FBILLFORMID': key, 'FCLASSNAME': '', 'FRPTTYPE': ''}
                for key in ('STK_InvBal', 'PRD_PickMtrl')]
        self.assertEqual(service.validate_registry(rows), ['PRD_PICKMTRL'])
        for invalid in (rows[1:], rows + [rows[1]], [dict(rows[0], FCLASSNAME='custom')],
                        rows + [dict(rows[1], FBILLFORMID='UNKNOWN')]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                service.validate_registry(invalid)

    def raw(self, entry, day, income, issue):
        return dict(organization_id=1, material_id=11, stock_id=20, stock_status_id=1,
            owner_type='', owner_id=0, bill_id=100, entry_id=entry, bill_seq=entry,
            bill_no='B1', bill_date=day, created_at=datetime(2026, 1, 1),
            base_income_qty=D(income), base_issue_qty=D(issue))

    def catalog(self):
        material = dict(code='M1', name='物料', unit_id=10, numerator=D(1), denominator=D(1), precision=2, unit_name='个')
        return dict(materials={11: material}, units={11: material}, stocks={20: dict(name='仓库')},
                    statuses={1: dict(name='可用')}, owners={})

    def test_history_rolls_into_opening_and_pagination_keeps_balance(self):
        query = StockDetailQuery(material='M1', organization_ids=[1], start_date=date(2026, 6, 1), end_date=date(2026, 6, 30), page=2, page_size=1)
        snapshot = dict(self.raw(1, date(2026, 5, 1), 0, 0), snapshot_id=1, base_qty=D(10))
        rows = [self.raw(2, date(2026, 5, 20), 4, 0), self.raw(3, date(2026, 6, 2), 0, 3), self.raw(4, date(2026, 6, 3), 2, 0)]
        result = self.service().compile_organization(query, 1, Baseline(date(2026, 5, 1), date(2026, 4, 30), 0),
            [snapshot], [('PRD_PICKMTRL', 'main', '生产领料单', row) for row in rows], self.catalog())
        page = assemble_page(query, result['rows'], result['openings'], opening_date=query.start_date, opening_labels=result['labels'])
        self.assertEqual(page['openings'][0]['opening_qty'], D(14))
        self.assertEqual(page['items'][0]['balance_qty'], D(13))
        self.assertEqual(page['total'], 2)

    def test_cross_organization_rows_are_rejected_before_normalization(self):
        query = StockDetailQuery(material='M1', organization_ids=[1], start_date=date(2026, 6, 1), end_date=date(2026, 6, 30))
        raw = dict(self.raw(1, date(2026, 6, 2), 1, 0), organization_id=2)
        with self.assertRaises(ValueError):
            self.service().compile_organization(query, 1, Baseline(query.start_date), [],
                [('PRD_PICKMTRL', 'main', '生产领料单', raw)], self.catalog())

    def test_summary_uses_complete_dataset_and_refuses_mixed_dimensions(self):
        from app.services.stock_detail_balance import InventoryKey
        key = InventoryKey(1, 11, 20, 1, '', 0, 10)
        data = dict(openings={key: D(5)}, labels={key: dict(material_code='M1', unit_name='个')},
                    rows=[dict(income_qty=D(10), issue_qty=D(3), inventory_key=key)])
        summary = self.service().quantity_summary(data)
        self.assertEqual(summary['balance_qty'], D(12))
        data['openings'][InventoryKey(1, 12, 20, 1, '', 0, 10)] = D(1)
        self.assertIsNone(self.service().quantity_summary(data))


if __name__ == '__main__':
    unittest.main()
