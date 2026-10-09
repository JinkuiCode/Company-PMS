"""Snapshot reads preserve the vendor's master-data and date semantics."""
from datetime import date
from pathlib import Path
import importlib.util
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.stock_detail_reader import StockDetailQuery


class SnapshotContract(unittest.TestCase):
    def service(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.stock_detail_snapshots'))
        from app.services import stock_detail_snapshots
        return stock_detail_snapshots

    def test_closed_snapshot_is_effective_on_the_following_day(self):
        service = self.service()
        self.assertEqual(service.effective_date(date(2026, 5, 31), 0), date(2026, 6, 1))
        self.assertEqual(service.effective_date(date(2026, 6, 1), 1), date(2026, 6, 1))
        with self.assertRaises(ValueError):
            service.effective_date(date(2026, 6, 1), 2)

    def test_snapshot_joins_master_ids_with_share_strategy(self):
        query = StockDetailQuery(material="PFA%'", organization_ids=[1], start_date='2026-06-01', end_date='2026-09-23', stock_id=20)
        sql, params = self.service().snapshot_sql(query, 1, date(2026, 5, 31), 0)
        self.assertIn('M.FMASTERID=S.FMATERIALID', sql)
        self.assertIn('M.FUSEORGID=S.FSTOCKORGID', sql)
        self.assertIn('O.FMASTERID=S.FOWNERID', sql)
        self.assertIn('K.FMASTERID=S.FKEEPERID', sql)
        self.assertIn('B.FMASTERID=S.FBOMID', sql)
        self.assertIn('L.FMASTERID=S.FLOT', sql)
        self.assertIn('S.FBASEENDQTY AS base_qty', sql)
        self.assertIn('S.FSTOCKORGID=%s', sql)
        self.assertIn('S.FSTOCKID=%s', sql)
        self.assertNotIn("PFA%'", sql)
        self.assertNotIn('FAMOUNT', sql)
        self.assertNotIn('FPRICE', sql)
        self.assertEqual(sql.count('%s'), len(params))

    def test_future_snapshot_and_invalid_organization_rejected(self):
        query = StockDetailQuery(material='PFA', organization_ids=[1], start_date='2026-06-01', end_date='2026-09-23')
        service = self.service()
        for org, day, kind in [(1, date(2026, 6, 1), 0), (True, date(2026, 5, 31), 0), (0, date(2026, 5, 31), 0)]:
            with self.subTest(org=org, day=day), self.assertRaises(ValueError):
                service.snapshot_sql(query, org, day, kind)


if __name__ == '__main__':
    unittest.main()
