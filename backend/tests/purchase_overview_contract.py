"""Project/organization aggregates execute the real accounting SQL offline."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import purchase_reader_contract as fixture
from app.services import purchase_reader as reader
from app.services.business_data_scope import ALL_DATA_SCOPE


class OverviewContract(unittest.TestCase):
    def setUp(self):
        self.source = fixture.ReaderContract()
        self.addCleanup(self.source.doCleanups)
        self.db, self.connection = self.source.classification_fixture()

    def overview(self, scope=ALL_DATA_SCOPE, **params):
        self.assertTrue(hasattr(reader, 'list_overview'), 'Project overview reader is missing')
        return reader.list_overview(self.connection, reader.PurchaseOverviewQuery(**params), scope)

    def test_counts_use_same_states_and_keep_review_in_denominator(self):
        result = self.overview()
        row = result['items'][0]
        self.assertEqual(result['total'], 1)
        self.assertEqual([row[k] for k in ('total_lines', 'not_ordered_lines', 'ordering_lines',
                                         'receiving_lines', 'complete_lines', 'review_lines')], [9, 1, 2, 2, 1, 3])
        self.assertAlmostEqual(float(row['completion_rate']), 100 / 9, places=6)
        self.assertEqual(self.db.execute("SELECT name FROM sqlite_temp_master WHERE name LIKE 'temp_pms_purchase_%'").fetchall(), [])

    def test_same_code_different_organizations_and_server_pagination(self):
        self.db.execute('UPDATE T_PUR_REQUISITION SET FAPPLICATIONORGID=200 WHERE FID=1')
        result = self.overview(page_size=1)
        second = self.overview(page_size=1, page=2)
        self.assertEqual(result['total'], 2)
        self.assertEqual(second['total'], 2)
        self.assertEqual(len(result['items']), 1)
        self.assertNotEqual(result['items'][0]['id'], second['items'][0]['id'])
        self.assertEqual({r['organization_id']: r['total_lines'] for r in result['items'] + second['items']}, {100: 8, 200: 1})
        self.assertEqual(self.overview([reader.OrganizationGrant(200)])['items'][0]['total_lines'], 1)
        self.assertEqual(self.overview([reader.OrganizationGrant(100)], organization_ids=[200])['total'], 0)
        self.assertEqual(self.overview([])['total'], 0)

    def test_project_quick_filters_do_not_remove_lines_from_denominator(self):
        self.assertEqual(self.overview(overview_status='complete')['total'], 0)
        for status in ('unfinished', 'review'):
            self.assertEqual(self.overview(overview_status=status)['items'][0]['total_lines'], 9)
        self.assertEqual(self.overview(keyword='R4')['items'][0]['complete_lines'], 1)
        self.assertEqual(self.overview(keyword='missing')['total'], 0)

    def test_empty_project_drill_cannot_broaden_to_all_projects(self):
        self.db.execute('UPDATE T_PUR_REQENTRY SET F_TWBJ_ASSISTANT_83G=NULL WHERE FENTRYID=1')
        rows = reader.list_requests(self.connection, reader.PurchaseQuery(project_code_is_empty=True,
                                    organization_ids=[100]), ALL_DATA_SCOPE)['items']
        self.assertEqual([row['id'] for row in rows], [1])
        with self.assertRaises(ValueError):
            reader.PurchaseQuery(project_code='P-1', project_code_is_empty=True)

    def test_metadata_prefix_and_summary_names_match(self):
        from app.services import purchase_fields
        self.assertTrue(hasattr(purchase_fields, 'overview_fields'), 'Overview metadata is missing')
        from app.services.purchase_fields import report_fields, overview_fields
        expected = [('product_line_name', '产品线'), ('project_code', '项目编码'), ('project_name', '项目名称')]
        self.assertEqual([(f['key'], f['label']) for f in report_fields()[:3]], expected)
        self.assertEqual([(f['key'], f['label']) for f in overview_fields()[:3]], expected)


if __name__ == '__main__':
    unittest.main()
