"""Column membership must never mutate top-level ordered operators."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import column
from fastapi import HTTPException
from app.services.query_conditions import build_query_clause


class MembershipIsolationContract(unittest.TestCase):
    def test_column_membership_does_not_enable_business_membership(self):
        for kind, value in [('number', [1, 2]), ('date', ['2026-10-11'])]:
            condition = {'schemaVersion': 2, 'operator': 'in', 'value': value}
            build_query_clause(column('value'), kind, condition, membership=True)
            with self.assertRaises(HTTPException) as caught:
                build_query_clause(column('value'), kind, condition)
            self.assertEqual(caught.exception.status_code, 422)


if __name__ == '__main__':
    unittest.main()
