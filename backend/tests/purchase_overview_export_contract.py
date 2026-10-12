"""Execute overview exports with SQL Server's final ORDER BY uniqueness rule."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import purchase_reader_contract as fixture
from app.services.business_data_scope import ALL_DATA_SCOPE
from app.services.purchase_reader import PurchaseOverviewQuery, list_overview
from app.services.report_export_data import overview_batches


class SqlServerOrderCursor(fixture.SqliteCursor):
    def execute(self, sql, params=()):
        if sql.startswith('SELECT * FROM (') and ' AS selected ORDER BY ' in sql:
            terms = sql.rsplit(' ORDER BY ', 1)[1].split(',')
            names = [term.strip().split()[0] for term in terms]
            if len(names) != len(set(names)):
                raise ValueError('SQL Server 169: duplicate final ORDER BY column')
        super().execute(sql, params)

    def fetchmany(self, size):
        return [dict(row) for row in self.cursor.fetchmany(size)]


class SqlServerOrderConnection(fixture.FixtureConnection):
    def cursor(self):
        return SqlServerOrderCursor(self.db)


class OverviewExportContract(unittest.TestCase):
    def setUp(self):
        source = fixture.ReaderContract()
        self.addCleanup(source.doCleanups)
        self.db, _ = source.classification_fixture()
        # Equal counts/rates must retain distinct organization/project pairs.
        self.db.execute('UPDATE T_PUR_REQUISITION SET FAPPLICATIONORGID=200 WHERE FID=1')
        self.connection = SqlServerOrderConnection(self.db)

    def test_each_sort_exports_same_authorized_rows_as_list_without_duplicate_order(self):
        for sort in ('project_code', 'completion_rate', 'conversion_rate', 'total_lines'):
            for direction in ('asc', 'desc'):
                with self.subTest(sort=sort, direction=direction):
                    query = PurchaseOverviewQuery(sort=sort, direction=direction)
                    expected = list_overview(self.connection, query, ALL_DATA_SCOPE)['items']
                    exported = [row for batch in overview_batches(self.connection, query, ALL_DATA_SCOPE)
                                for row in batch]
                    keys = ('organization_id', 'project_code', 'total_lines', 'complete_lines', 'completion_rate', 'conversion_rate')
                    self.assertEqual([tuple(row[key] for key in keys) for row in exported],
                                     [tuple(row[key] for key in keys) for row in expected])

    def test_empty_authorization_exports_no_rows(self):
        self.assertEqual(list(overview_batches(self.connection, PurchaseOverviewQuery(), [])), [])


if __name__ == '__main__':
    unittest.main()
