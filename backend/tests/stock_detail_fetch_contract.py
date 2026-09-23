from datetime import date
from pathlib import Path
from unittest.mock import patch
import importlib.util
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.stock_detail_reader import StockDetailQuery
from app.services.stock_detail_baseline import Baseline


class Cursor:
    def __init__(self, batches):
        self.batches, self.calls, self.closed = iter(batches), [], False

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchall(self):
        value = next(self.batches)
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        self.closed = True


class Connection:
    def __init__(self, batches):
        self.cur = Cursor(batches)
        self.used = False
        self.rollbacks = 0
        self.rollback_positions = []

    def rollback(self):
        self.rollbacks += 1
        self.rollback_positions.append(len(self.cur.calls))

    def cursor(self):
        self.used = True
        return self.cur


class FetchContract(unittest.TestCase):
    def service(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.stock_detail_fetch'))
        from app.services import stock_detail_fetch
        return stock_detail_fetch

    def query(self):
        return StockDetailQuery(material='M1', start_date=date(2026, 6, 1), end_date=date(2026, 6, 30))

    def registry(self):
        return [dict(FBILLFORMID=form) for form in ('STK_InvBal', 'PRD_PickMtrl')]

    def test_empty_authorization_never_opens_cursor(self):
        connection = Connection([])
        result = self.service().read_dataset(connection, self.query(), [])
        self.assertEqual(result, dict(rows=[], openings={}, labels={}))
        self.assertFalse(connection.used)

    def test_source_failure_closes_cursor_and_never_returns_partial_report(self):
        service = self.service()
        connection = Connection([[{'snapshot_isolation_state': 1}], self.registry(), RuntimeError('denied')])
        with patch.object(service, 'load_baseline', return_value=Baseline(date(2026, 1, 1))), self.assertRaises(RuntimeError):
            service.read_dataset(connection, self.query(), [1])
        self.assertTrue(connection.cur.closed)

    def test_scope_and_complete_interval_are_applied_to_source_query(self):
        service = self.service()
        connection = Connection([[{'snapshot_isolation_state': 1}], self.registry(), []])
        with patch.object(service, 'load_baseline', return_value=Baseline(date(2026, 1, 1))):
            result = service.read_dataset(connection, self.query(), [1])
        self.assertEqual(result['rows'], [])
        sql, params = connection.cur.calls[-1]
        self.assertIn('H.FSTOCKORGID IN (%s)', sql)
        self.assertIn(date(2026, 1, 1), params)
        self.assertEqual(params[0], 1)
        self.assertTrue(connection.cur.closed)

    def test_snapshot_capability_is_required_before_reading_sources(self):
        connection = Connection([[{'snapshot_isolation_state': 0}]])
        with self.assertRaises(ValueError):
            self.service().read_dataset(connection, self.query(), [1])
        self.assertEqual(len(connection.cur.calls), 1)
        self.assertTrue(connection.cur.closed)

    def test_one_transaction_snapshot_precedes_all_source_reads(self):
        service = self.service()
        connection = Connection([[{'snapshot_isolation_state': 1}], self.registry(), []])
        with patch.object(service, 'load_baseline', return_value=Baseline(date(2026, 1, 1))):
            service.read_dataset(connection, self.query(), [1])
        self.assertEqual(connection.rollbacks, 3)
        self.assertEqual(connection.rollback_positions[:2], [1, 2])
        self.assertIn('SET TRANSACTION ISOLATION LEVEL SNAPSHOT', connection.cur.calls[1][0])


if __name__ == '__main__':
    unittest.main()
