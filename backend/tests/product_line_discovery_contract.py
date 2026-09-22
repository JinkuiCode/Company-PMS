"""Organization discovery stays bounded, read-only and credential-free."""
import sys
import unittest
from unittest.mock import Mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.inspect_product_line_organizations import inspect_organizations


class Cursor:
    def __init__(self):
        self.statements = []
        self.closed = False

    def execute(self, sql, params=()):
        self.statements.append((sql, params))

    def fetchall(self):
        return []

    def close(self):
        self.closed = True


class Discovery(unittest.TestCase):
    def test_catalog_rows_require_verified_columns_and_keep_language_and_status(self):
        from scripts.inspect_product_line_organizations import inspect_catalog_rows
        cursor = Cursor()
        with self.assertRaises(ValueError):
            inspect_catalog_rows(cursor, [])
        self.assertEqual(cursor.statements, [])
        columns = [dict(table_name=table, column_name=column) for table, names in (
            ('T_ORG_ORGANIZATIONS', 'FORGID FNUMBER FFORBIDSTATUS FDOCUMENTSTATUS'),
            ('T_ORG_ORGANIZATIONS_L', 'FORGID FLOCALEID FNAME'),
        ) for column in names.split()]
        inspect_catalog_rows(cursor, columns)
        sql = cursor.statements[0][0]
        self.assertTrue(sql.startswith('SELECT TOP (501)'))
        self.assertIn('l.FORGID=o.FORGID', sql)
        self.assertIn('FLOCALEID', sql)
        self.assertIn('FFORBIDSTATUS', sql)

    def test_admin_discovery_rolls_back_and_closes_without_commit(self):
        from scripts.inspect_product_line_organizations import inspect_admin_connection
        connection = Mock()
        cursor = Cursor()
        connection.cursor.return_value = cursor
        inspect_admin_connection(connection)
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
        connection.commit.assert_not_called()
        self.assertTrue(cursor.closed)

    def test_empty_metadata_is_not_reported_as_no_organizations(self):
        cursor = Cursor()
        result = inspect_organizations(cursor)
        self.assertEqual(result['organization_catalog_status'], 'metadata_not_visible')
        self.assertFalse(result['ready_for_runtime'])

    def test_only_fixed_bounded_reads(self):
        cursor = Cursor()
        inspect_organizations(cursor)
        self.assertEqual(len(cursor.statements), 4)
        for sql, params in cursor.statements:
            self.assertTrue(sql.strip().upper().startswith('SELECT TOP'))
            self.assertNotIn('GRANT ', sql.upper())
            self.assertNotIn('PASSWORD', sql.upper())
            self.assertNotIn('SELECT *', sql.upper())
        self.assertEqual(cursor.statements[1][1], ('2026-01-01',))


if __name__ == '__main__':
    unittest.main()
