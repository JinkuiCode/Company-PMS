from datetime import date, datetime
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


class BaselineContract(unittest.TestCase):
    def service(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.stock_detail_baseline'))
        from app.services import stock_detail_baseline
        return stock_detail_baseline

    def test_closed_snapshot_is_verified_for_organization_not_material(self):
        cursor = Cursor([[{'close_date': datetime(2026, 5, 31)}], [{'exists': 1}]])
        result = self.service().load_baseline(cursor, 1, date(2026, 6, 1))
        self.assertEqual(result.effective_date, date(2026, 6, 1))
        self.assertEqual(result.balance_type, 0)
        self.assertNotIn('FMATERIALID', cursor.calls[1][0])
        for sql, params in cursor.calls:
            self.assertEqual(sql.count('%s'), len(params))

    def test_missing_closed_snapshot_fails_not_zero(self):
        with self.assertRaises(ValueError):
            self.service().load_baseline(Cursor([[{'close_date': date(2026, 5, 31)}], []]), 1, date(2026, 6, 1))

    def test_initialization_includes_day_before_startup(self):
        result = self.service().load_baseline(Cursor([[], [{'start_date': '2026-01-01'}]]), 1, date(2026, 6, 1))
        self.assertEqual(result.effective_date, date(2025, 12, 31))
        self.assertIsNone(result.balance_type)

    def test_query_before_startup_keeps_initialization_in_period(self):
        result = self.service().load_baseline(Cursor([[], [{'start_date': '2026-01-01'}]]), 1, date(2025, 12, 1))
        self.assertEqual(result.effective_date, date(2025, 12, 1))

    def test_missing_or_ambiguous_startup_fails(self):
        for rows in ([], [{'start_date': 'bad'}], [{'start_date': '2026-01-01'}] * 2):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.service().load_baseline(Cursor([[], rows]), 1, date(2026, 6, 1))


if __name__ == '__main__':
    unittest.main()
