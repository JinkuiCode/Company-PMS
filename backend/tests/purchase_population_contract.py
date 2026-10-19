"""Fixed request population is shared by report, detail, candidates and export."""
import json
import unittest

import purchase_reader_contract as fixture
from purchase_overview_export_contract import SqlServerOrderConnection
from app.services import purchase_reader as reader
from app.services.business_data_scope import ALL_DATA_SCOPE
from app.services.report_export_data import overview_batches, purchase_batches
from app.services.report_filters import filter_fields, query_fields


class PopulationContract(unittest.TestCase):
    def setUp(self):
        source = fixture.ReaderContract()
        self.addCleanup(source.doCleanups)
        self.db, _ = source.classification_fixture()
        self.db.execute("UPDATE T_PUR_REQENTRY SET FMRPTERMINATESTATUS='A'")
        self.db.execute("UPDATE T_PUR_REQENTRY SET FMRPTERMINATESTATUS='B' WHERE FENTRYID=2")
        self.db.execute("UPDATE T_PUR_REQUISITION SET FDOCUMENTSTATUS='B' WHERE FID=3")
        for key, status in [(4, None), (5, 'NEW'), (6, '')]:
            self.db.execute('UPDATE T_PUR_REQENTRY SET FMRPTERMINATESTATUS=? WHERE FENTRYID=?', (status, key))
        self.connection = SqlServerOrderConnection(self.db)
        self.expected = {1, 7, 8, 9}

    def test_only_audited_normal_lines_are_counted_and_paged(self):
        ids = set()
        for page in range(1, 6):
            result = reader.list_requests(self.connection, reader.PurchaseQuery(page=page, page_size=1), ALL_DATA_SCOPE)
            self.assertEqual(result['total'], 4)
            ids.update(row['id'] for row in result['items'])
        self.assertEqual(ids, self.expected)
        row = reader.list_overview(self.connection, reader.PurchaseOverviewQuery(), ALL_DATA_SCOPE)['items'][0]
        self.assertEqual(row['total_lines'], 4)
        self.assertEqual(float(row['completion_rate']), 0)
        self.assertEqual(float(row['conversion_rate']), 25)

    def test_detail_cannot_reopen_excluded_request(self):
        for key in range(1, 10):
            with self.subTest(key=key):
                self.assertEqual(reader.load_request(self.connection, key, ALL_DATA_SCOPE) is not None, key in self.expected)
        self.assertIsNone(reader.load_request(self.connection, 1, []))

    def test_candidates_cannot_reveal_excluded_project(self):
        self.db.execute("INSERT INTO T_BAS_ASSISTANTDATAENTRY(FENTRYID,FNUMBER) VALUES ('excluded','EXCLUDED')")
        self.db.execute("UPDATE T_PUR_REQENTRY SET F_TWBJ_ASSISTANT_83G='excluded' WHERE FENTRYID IN (2,3,4,5,6)")
        result = reader.list_options(self.connection, 'project', '', ALL_DATA_SCOPE)
        self.assertEqual(result['items'], [dict(value='P-1', label='P-1')])

    def test_exports_share_same_fixed_population(self):
        from purchase_typed_progress_contract import Connection
        rows = [r for batch in purchase_batches(Connection(self.db), reader.PurchaseQuery(), ALL_DATA_SCOPE) for r in batch]
        self.assertEqual({r['id'] for r in rows}, self.expected)
        exported = [r for batch in overview_batches(self.connection, reader.PurchaseOverviewQuery(), ALL_DATA_SCOPE) for r in batch]
        self.assertEqual(exported[0]['total_lines'], 4)

    def test_status_is_display_only_and_old_conditions_are_rejected(self):
        for fields in (filter_fields('purchase'), query_fields('purchase'), query_fields('purchase-overview')):
            self.assertNotIn('document_status', {f['field'] for f in fields})
        for model in (reader.PurchaseQuery, reader.PurchaseOverviewQuery):
            for version in (1, 2):
                with self.subTest(model=model.__name__, version=version), self.assertRaises(ValueError):
                    model(filters=json.dumps([dict(field='document_status', operator='equals', value='C', schemaVersion=version)]))


if __name__ == '__main__':
    unittest.main()
