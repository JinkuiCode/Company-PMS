import sys
import unittest
from pathlib import Path
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []
        self.closed = False

    def execute(self, sql, params=()):
        self.statements.append((sql, params))

    def fetchone(self):
        return {'total': len(self.rows)}

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class Source(unittest.TestCase):
    def reader(self, cursor):
        @contextmanager
        def connection():
            class Connection:
                def cursor(self):
                    return cursor
            yield Connection()
        return connection

    def test_search_is_bound_and_pagination_is_in_database(self):
        from app.services.product_line_source import list_organizations
        cursor = Cursor([])
        result = list_organizations(keyword="%'[", page=2, page_size=10, connection_factory=self.reader(cursor))
        self.assertEqual(result, {'items': [], 'total': 0})
        self.assertEqual(len(cursor.statements), 2)
        self.assertIn('OFFSET %s ROWS FETCH NEXT %s ROWS ONLY', cursor.statements[1][0])
        self.assertEqual(cursor.statements[1][1][-2:], (10, 10))
        self.assertNotIn("%'[", cursor.statements[0][0])
        self.assertIn("%~%'~[%", cursor.statements[0][1])
        self.assertTrue(cursor.closed)

    def test_org_lookup_requires_unique_nonblank_approved_active_chinese_name(self):
        from app.services.product_line_source import get_organization
        good = dict(organization_id=100, code='001', name='测试事业部', forbid_status='A', document_status='C')
        option = get_organization(100, connection_factory=self.reader(Cursor([good])))
        self.assertTrue(option.active)
        for rows in ([], [good, good], [{**good, 'name': ' '}], [{**good, 'forbid_status': 'B'}],
                     [{**good, 'document_status': 'A'}]):
            with self.assertRaises(HTTPException):
                get_organization(100, connection_factory=self.reader(Cursor(rows)))

    def test_connection_errors_are_sanitized(self):
        from app.services.product_line_source import list_organizations
        @contextmanager
        def broken():
            raise RuntimeError('secret-connection-details')
            yield
        with self.assertRaises(HTTPException) as caught:
            list_organizations(connection_factory=broken)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn('secret', str(caught.exception.detail))

    def test_invalid_pagination_does_not_connect(self):
        from app.services.product_line_source import list_organizations
        def forbidden():
            raise AssertionError('should not connect')
        for args in ({'page': 0}, {'page_size': 501}, {'keyword': 'x' * 101}):
            with self.assertRaises(HTTPException) as caught:
                list_organizations(**args, connection_factory=forbidden)
            self.assertEqual(caught.exception.status_code, 422)


if __name__ == '__main__':
    unittest.main()
