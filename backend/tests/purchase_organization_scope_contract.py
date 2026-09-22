"""A project code and ERP organization form one indivisible report grant."""
import unittest
import purchase_reader_contract as fixtures
from app.services import purchase_reader as reader


class OrganizationScope(unittest.TestCase):
    def test_missing_scope_is_not_all_projects(self):
        self.assertEqual(reader.scope_clause('a.FNUMBER', None), ('1=0', []))

    def test_project_and_organization_are_matched_as_pairs(self):
        self.assertTrue(hasattr(reader, 'ProjectOrganizationGrant'))
        fixture = fixtures.ReaderContract()
        self.addCleanup(fixture.doCleanups)
        db, connection = fixture.classification_fixture()
        db.execute("INSERT INTO T_BAS_ASSISTANTDATAENTRY(FENTRYID,FNUMBER) VALUES ('a','P-A'),('b','P-B')")
        db.execute("UPDATE T_PUR_REQENTRY SET F_TWBJ_ASSISTANT_83G=CASE WHEN FENTRYID IN (1,2) THEN 'a' ELSE 'b' END")
        db.execute('UPDATE T_PUR_REQUISITION SET FAPPLICATIONORGID=CASE WHEN FID IN (1,3) THEN 100 ELSE 200 END')
        grants = [reader.ProjectOrganizationGrant('P-A', 100), reader.ProjectOrganizationGrant('P-B', 200)]
        rows = reader.list_requests(connection, reader.PurchaseQuery(), grants)
        self.assertEqual({row['id'] for row in rows['items']}, {1,4,5,6,7,8,9})
        self.assertIsNone(reader.load_request(connection, 2, grants))
        self.assertIsNone(reader.load_request(connection, 3, grants))
        self.assertEqual(reader.list_requests(connection, reader.PurchaseQuery(), None)['total'], 0)

    def test_large_grants_are_batched_without_truncation(self):
        self.assertTrue(hasattr(reader, 'ProjectOrganizationGrant'))
        fixture = fixtures.ReaderContract()
        self.addCleanup(fixture.doCleanups)
        db, connection = fixture.classification_fixture()
        db.execute("INSERT INTO T_BAS_ASSISTANTDATAENTRY(FENTRYID,FNUMBER) VALUES ('a','P-2500')")
        db.execute("UPDATE T_PUR_REQENTRY SET F_TWBJ_ASSISTANT_83G='a'")
        db.execute('UPDATE T_PUR_REQUISITION SET FAPPLICATIONORGID=100')
        grants = [reader.ProjectOrganizationGrant(f'P-{n}', 100) for n in range(2501)]
        self.assertEqual(reader.list_requests(connection, reader.PurchaseQuery(), grants)['total'], 9)
        self.assertEqual(reader.list_requests(connection, reader.PurchaseQuery(), [])['total'], 0)

    def test_foreign_chain_is_hidden_and_both_summary_paths_require_review(self):
        for table, column in [('T_PUR_POORDER', 'FPURCHASEORGID'), ('T_STK_INSTOCK', 'FSTOCKORGID')]:
            with self.subTest(table=table):
                fixture = fixtures.ReaderContract()
                self.addCleanup(fixture.doCleanups)
                db, connection = fixture.classification_fixture()
                db.execute('UPDATE T_PUR_POORDER SET FPURCHASEORGID=100')
                db.execute('UPDATE T_STK_INSTOCK SET FSTOCKORGID=100')
                db.execute(f'UPDATE {table} SET {column}=200 WHERE FID=4')
                query = reader.PurchaseQuery(keyword='R4')
                row = reader.list_requests(connection, query, fixtures.GRANTS)['items'][0]
                self.assertEqual(row['progress'], 'review')
                self.assertIsNone(row['ordered'])
                reviewed = reader.list_requests(connection, query.model_copy(update={'progress': 'review'}), fixtures.GRANTS)
                self.assertEqual(reviewed['total'], 1)
                chain = reader.load_chains(connection, [reader.load_request(connection, 4, fixtures.GRANTS)])[4]
                key = 'orders' if table == 'T_PUR_POORDER' else 'receipts'
                self.assertEqual(chain[key], [])

    def test_receiving_and_return_organizations_cannot_be_ignored(self):
        for kind in ('receive', 'return'):
            fixture = fixtures.ReaderContract()
            self.addCleanup(fixture.doCleanups)
            db, connection = fixture.classification_fixture()
            if kind == 'receive':
                db.execute("INSERT INTO T_PUR_RECEIVE(FID,FSTOCKORGID) VALUES (40,200)")
                db.execute("INSERT INTO T_PUR_RECEIVEENTRY(FENTRYID,FID,FPOORDERENTRYID,FMATERIALID,FBASEUNITID) VALUES (40,40,4,10,1)")
            else:
                db.execute("INSERT INTO T_PUR_MRB(FID,FSTOCKORGID,FDOCUMENTSTATUS,FCANCELSTATUS) VALUES (40,200,'C','A')")
                db.execute("INSERT INTO T_PUR_MRBENTRY(FENTRYID,FID,FPOORDERENTRYID,FMATERIALID,FBASEUNITID,FBASEUNITQTY) VALUES (40,40,4,10,1,1)")
                db.execute("INSERT INTO T_PUR_MRBENTRY_LK(FENTRYID,FLINKID,FSTABLENAME,FSID,FSBILLID,FBASEUNITQTY) VALUES (40,40,'T_STK_INSTOCKENTRY',4,4,1)")
            query = reader.PurchaseQuery(keyword='R4')
            result = reader.list_requests(connection, query, fixtures.GRANTS)['items'][0]
            self.assertEqual(result['progress'], 'review', kind)
            self.assertIsNone(result['ordered'], kind)
            self.assertEqual(reader.list_requests(connection, query.model_copy(update={'progress': 'review'}), fixtures.GRANTS)['total'], 1)
            chain = reader.load_chains(connection, [reader.load_request(connection, 4, fixtures.GRANTS)])[4]
            self.assertEqual(chain['returns'], [])

    def test_foreign_supplier_is_not_a_candidate_or_filter_match(self):
        fixture = fixtures.ReaderContract()
        self.addCleanup(fixture.doCleanups)
        db, connection = fixture.classification_fixture()
        db.execute("INSERT INTO T_BD_SUPPLIER_L(FSUPPLIERID,FLOCALEID,FNAME) VALUES (900,2052,'外部供应商')")
        db.execute('UPDATE T_PUR_POORDER SET FPURCHASEORGID=200,FSUPPLIERID=900 WHERE FID=4')
        self.assertEqual(reader.list_options(connection, 'supplier', '', fixtures.GRANTS)['items'], [])
        self.assertEqual(reader.list_requests(connection, reader.PurchaseQuery(supplier='外部供应商'), fixtures.GRANTS)['total'], 0)

    def test_merged_order_supplier_follows_hidden_detail_boundary(self):
        fixture = fixtures.ReaderContract()
        self.addCleanup(fixture.doCleanups)
        db, connection = fixture.classification_fixture()
        db.execute("INSERT INTO T_BD_SUPPLIER_L(FSUPPLIERID,FLOCALEID,FNAME) VALUES (900,2052,'合并订单供应商')")
        db.execute('UPDATE T_PUR_POORDER SET FSUPPLIERID=900 WHERE FID=4')
        db.execute('UPDATE T_PUR_REQUISITION SET FAPPLICATIONORGID=200 WHERE FID=5')
        db.execute("INSERT INTO T_PUR_POORDERENTRY_LK(FENTRYID,FLINKID,FSTABLENAME,FSID,FSBILLID,FBASEUNITQTY) VALUES (4,999,'T_PUR_REQENTRY',5,5,1)")
        chain = reader.load_chains(connection, [reader.load_request(connection, 4, fixtures.GRANTS)])[4]
        self.assertEqual(chain['orders'], [])
        self.assertEqual(reader.list_options(connection, 'supplier', '', fixtures.GRANTS)['items'], [])
        self.assertEqual(reader.list_requests(connection, reader.PurchaseQuery(supplier='合并订单供应商'), fixtures.GRANTS)['total'], 0)


if __name__ == '__main__':
    unittest.main()
