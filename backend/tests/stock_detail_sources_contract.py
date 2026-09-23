"""Bound SQL adapters; synthetic inputs exercise query boundaries."""
from pathlib import Path
import importlib.util
import sys
import unittest
import sqlite3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.stock_detail_reader import StockDetailQuery


class SourceContract(unittest.TestCase):
    def sources(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.stock_detail_sources'))
        from app.services import stock_detail_sources
        return stock_detail_sources

    def query(self, **changes):
        return StockDetailQuery(material="PFA%' OR 1=1--", start_date='2026-06-01', end_date='2026-09-23', **changes)

    def test_bound_material_dates_organizations_and_stock(self):
        sql, params = self.sources().movement_sql('PRD_PickMtrl', self.query(stock_id=20), [1])
        self.assertNotIn("OR 1=1--", sql)
        self.assertIn('H.FSTOCKORGID IN (%s)', sql)
        self.assertIn('E.FSTOCKID=%s', sql)
        self.assertIn('H.FDATE>=%s AND H.FDATE<%s', sql)
        self.assertIn("Q.FBASESTOCKACTUALQTY", sql)
        self.assertNotIn('FPRICE', sql)
        self.assertNotIn('FAMOUNT', sql)
        self.assertEqual(sql.count('%s'), len(params))

    def test_return_is_negative_issue_not_positive_income(self):
        sql, _ = self.sources().movement_sql('PRD_ReturnMtrl', self.query(), [1])
        self.assertIn('0 AS base_income_qty', sql)
        self.assertIn('-Q.FBASESTOCKQTY AS base_issue_qty', sql)

    def test_entrusted_production_is_not_double_counted(self):
        sql, _ = self.sources().movement_sql('PRD_INSTOCK', self.query(), [1])
        self.assertIn('H.FENTRUSTINSTOCKID=0', sql)

    def test_unknown_sources_and_empty_scope_fail_closed(self):
        module = self.sources()
        for source, scope in [('UNKNOWN', [1]), ('PRD_PickMtrl', []), ('PRD_PickMtrl', [True])]:
            with self.subTest(source=source, scope=scope), self.assertRaises(ValueError):
                module.movement_sql(source, self.query(), scope)

    def test_partial_source_coverage_cannot_be_published(self):
        module = self.sources()
        with self.assertRaisesRegex(ValueError, '未完成'):
            module.require_source_coverage(['PRD_PickMtrl', 'STK_InvBal'])
        module.require_source_coverage(['PRD_PickMtrl'])

    def test_subcontract_return_trace_number_is_in_extension(self):
        sql, _ = self.sources().movement_sql('SUB_RETURNMTRL', self.query(), [1])
        self.assertIn('Q.FMTONO AS mto_no', sql)

    def test_miscellaneous_returns_keep_vendor_column_direction(self):
        sql, _ = self.sources().movement_sql('STK_MisDelivery', self.query(), [1])
        self.assertIn("WHEN H.FSTOCKDIRECT='RETURN' THEN -E.FBASEQTY", sql)
        self.assertIn('0 AS base_income_qty', sql)

    def test_conversion_pair_has_opposite_sides(self):
        sql, _ = self.sources().movement_sql('STK_StatusConvert', self.query(), [1])
        self.assertIn("WHEN UPPER(E.FCONVERTTYPE)='B' THEN E.FBASEQTY", sql)
        self.assertIn("WHEN UPPER(E.FCONVERTTYPE)='A' THEN E.FBASEQTY", sql)

    def test_count_loss_uses_loss_quantity(self):
        sql, _ = self.sources().movement_sql('STK_StockCountLoss', self.query(), [1])
        self.assertIn('E.FBASELOSSQTY AS base_issue_qty', sql)

    def test_sales_exclude_generated_and_non_inventory_entries(self):
        for code in ('SAL_OUTSTOCK', 'SAL_RETURNSTOCK'):
            sql, params = self.sources().movement_sql(code, self.query(), [1])
            self.assertIn("F.FISGENFORIOS='0'", sql)
            self.assertIn("B.FISINVENTORY='1'", sql)
            self.assertIn("Q.FROWTYPE IN ('Son','Standard',' ')", sql)
            self.assertEqual(sql.count('%s'), len(params))
        self.assertIn('-E.FBASEUNITQTY AS base_issue_qty', sql)
        self.assertIn("E.FRETURNTYPE <> '0fa6270ab70b416cb2a7141a8f182d64'", sql)

    def test_receipt_without_stock_update_is_excluded(self):
        sql, _ = self.sources().movement_sql('PUR_ReceiveBill', self.query(), [1])
        self.assertIn("E.FSTOCKFLAG='1'", sql)
        self.assertIn('E.FSTOCKID>0', sql)
        self.assertIn('E.FBASEUNITQTY AS base_income_qty', sql)
        self.assertIn("B.FISINVENTORY='1'", sql)

    def test_direct_transfer_scopes_each_side_independently(self):
        module = self.sources()
        self.assertTrue(hasattr(module, 'movement_queries'))
        queries = module.movement_queries('STK_TransferDirect', self.query(stock_id=20), [1])
        self.assertEqual([side for side, _, _ in queries], ['in', 'out'])
        incoming, outgoing = queries[0][1], queries[1][1]
        self.assertIn('H.FSTOCKORGID IN (%s)', incoming)
        self.assertIn('H.FSTOCKOUTORGID IN (%s)', outgoing)
        self.assertIn('E.FDESTSTOCKID=%s', incoming)
        self.assertIn('E.FSRCSTOCKID=%s', outgoing)
        self.assertIn('M.FMATERIALID=E.FSRCMATERIALID', outgoing)
        self.assertIn('E.FOWNEROUTID AS owner_id', outgoing)
        self.assertIn('E.FKEEPEROUTID AS keeper_id', outgoing)
        for _, sql, params in queries:
            self.assertIn("H.FISGENFORIOS<>'1'", sql)
            self.assertIn("H.FOBJECTTYPEID='STK_TransferDirect'", sql)
            self.assertEqual(sql.count('%s'), len(params))
        self.assertIn('E.FSTOCKINFLAG AS stock_flag', incoming)
        self.assertIn('E.FSTOCKOUTFLAG AS stock_flag', outgoing)

    def test_purchase_stock_preserves_receiving_side_dimensions(self):
        module = self.sources()
        queries = module.movement_queries('STK_InStock', self.query(stock_id=20), [1])
        self.assertEqual([side for side, _, _ in queries], ['stock', 'receive'])
        stock, receive = queries[0][1], queries[1][1]
        self.assertIn('E.FBASEUNITQTY AS base_income_qty', stock)
        self.assertIn('E.FBASEUNITQTY AS base_issue_qty', receive)
        self.assertIn('E.FRECEIVESTOCKID=%s', receive)
        self.assertIn('E.FRECEIVEOWNERID AS owner_id', receive)
        self.assertIn('E.FRECEIVEAUXPROPID AS auxiliary_property_id', receive)
        self.assertIn('E.FRECEIVEMTONO AS mto_no', receive)
        self.assertIn("E.FRECEIVESTOCKFLAG='1'", receive)

    def test_purchase_return_preserves_negative_income_and_status_change(self):
        sql, _ = self.sources().movement_sql('PUR_MRB', self.query(), [1])
        self.assertIn('-E.FBASEUNITQTY AS base_income_qty', sql)
        self.assertIn("H.FMRTYPE='B'", sql)
        self.assertIn('E.FSTOCKSTATUSID<>E.FRECEIVESTOCKSTATUSID', sql)

    def test_step_transfer_includes_in_transit_adjustments(self):
        module = self.sources()
        incoming = module.movement_queries('STK_TRANSFERIN', self.query(), [1])
        outgoing = module.movement_queries('STK_TRANSFEROUT', self.query(), [1])
        self.assertEqual([s for s, _, _ in incoming], ['in', 'transit_a', 'transit_b'])
        self.assertEqual([s for s, _, _ in outgoing], ['out', 'transit_a', 'transit_b'])
        for _, sql, _ in incoming[1:]:
            self.assertIn('-E.FBASEQTY-Q.FBASEPATHLOSSQTY AS base_income_qty', sql)
        self.assertIn('H.FSTOCKOUTORGID IN (%s)', incoming[1][1])
        self.assertIn('E.FSRCPRODUCEDATE AS produce_date', incoming[1][1])
        self.assertIn('H.FSTOCKINORGID IN (%s)', outgoing[2][1])
        self.assertIn('E.FDESTMATERIALID AS material_id', outgoing[2][1])
        self.assertIn('E.FOWNERINID AS owner_id', outgoing[2][1])

    def test_assembly_subitems_use_detail_identity_and_parent_join(self):
        queries = self.sources().movement_queries('STK_AssembledApp', self.query(), [1])
        self.assertEqual([s for s, _, _ in queries], ['product', 'component'])
        self.assertIn('E.FDETAILID AS entry_id', queries[1][1])
        self.assertIn('E.FENTRYID=P.FENTRYID', queries[1][1])
        self.assertIn("WHEN 'ASSEMBLY' THEN 0 WHEN 'DASSEMBLY' THEN E.FBASEQTY", queries[1][1])

    def test_production_line_transfer_does_not_borrow_standard_row_type_filter(self):
        queries = self.sources().movement_queries('REM_TransferDirect', self.query(), [1])
        self.assertEqual(len(queries), 2)
        for _, sql, _ in queries:
            self.assertIn('T_REM_STKTRANSFERIN', sql)
            self.assertNotIn('FISGENFORIOS', sql)
            self.assertNotIn('FROWTYPE IN', sql)

    def test_initial_stock_uses_start_stock_date_not_bill_date(self):
        sql, params = self.sources().movement_sql('STK_InvInit', self.query(), [1])
        self.assertIn("P.FKEY='STARTSTOCKDATE'", sql)
        self.assertIn('DATEADD(day,-1,TRY_CONVERT(date,P.FVALUE)) AS bill_date', sql)
        self.assertIn('DATEADD(day,-1,TRY_CONVERT(date,P.FVALUE))>=%s', sql)
        self.assertIn('H.FKEEPERID AS keeper_id', sql)
        self.assertNotIn('FCANCELSTATUS', sql)
        self.assertEqual(sql.count('%s'), len(params))

    def test_direct_transfer_sql_produces_only_authorized_side_and_return_sign(self):
        module = self.sources()
        self.assertTrue(hasattr(module, 'movement_queries'))
        tables = {
            'T_STK_STKTRANSFERIN': [dict(FID=1, FSTOCKORGID=10, FSTOCKOUTORGID=20,
                FBILLNO='DOC1', FDATE='2026-09-01', FCREATEDATE='2026-09-01',
                FCANCELSTATUS='A', FDOCUMENTSTATUS='C', FISGENFORIOS='0',
                FOBJECTTYPEID='STK_TransferDirect', FTRANSFERDIRECT='GENERAL')],
            'T_STK_STKTRANSFERINENTRY': [dict(FID=1, FENTRYID=100, FSEQ=1,
                FMATERIALID=11, FSRCMATERIALID=22, FDESTSTOCKID=101, FSRCSTOCKID=202,
                FDESTSTOCKSTATUSID=1, FSRCSTOCKSTATUSID=1, FDESTSTOCKLOCID=0, FSRCSTOCKLOCID=0,
                FBOMID=0, FSRCBOMID=0, FDESTLOT_TEXT='', FLOT_TEXT='', FAUXPROPID=0,
                FOWNERTYPEID='BD_OwnerOrg', FOWNERID=10, FOWNERTYPEOUTID='BD_OwnerOrg', FOWNEROUTID=20,
                FKEEPERTYPEID='BD_KeeperOrg', FKEEPERID=10, FKEEPERTYPEOUTID='BD_KeeperOrg', FKEEPEROUTID=20,
                FMTONO='', FPRODUCEDATE=None, FEXPIRYDATE=None, FSTOCKINFLAG=1, FSTOCKOUTFLAG=1, FBASEQTY=6)],
            'T_STK_STKTRANSFERINENTRY_T': [dict(FENTRYID=100, FROWTYPE='Standard')],
            'T_STK_STKTRANSFERINENTRY_R': [dict(FENTRYID=100)],
            'T_BD_MATERIALBASE': [dict(FMATERIALID=11, FISINVENTORY='1'), dict(FMATERIALID=22, FISINVENTORY='1')],
            'T_BD_MATERIAL': [dict(FMATERIALID=11, FMASTERID=1, FNUMBER='PFA'), dict(FMATERIALID=22, FMASTERID=1, FNUMBER='PFA')],
            'T_BD_MATERIAL_L': [dict(FMATERIALID=11, FLOCALEID=2052, FNAME='PFA管', FSPECIFICATION='')],
        }
        with sqlite3.connect(':memory:') as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("ATTACH DATABASE ':memory:' AS dbo")
            for table, rows in tables.items():
                columns = list(rows[0])
                connection.execute(f'CREATE TABLE dbo.{table} ({",".join(columns)})')
                connection.executemany(f'INSERT INTO dbo.{table} VALUES ({",".join("?" for _ in columns)})',
                                       [tuple(row[column] for column in columns) for row in rows])
            query = StockDetailQuery(material='PFA', start_date='2026-09-01', end_date='2026-09-30')
            def result(scope):
                values = []
                for side, sql, params in module.movement_queries('STK_TransferDirect', query, scope):
                    args = [value.isoformat() if hasattr(value, 'isoformat') else value for value in params]
                    values.extend((side, dict(row)) for row in connection.execute(sql.replace('%s', '?'), args))
                return values
            incoming, outgoing = result([10]), result([20])
            self.assertEqual([(side, row['base_income_qty'], row['base_issue_qty']) for side, row in incoming], [('in', 6, 0)])
            self.assertEqual([(side, row['base_income_qty'], row['base_issue_qty']) for side, row in outgoing], [('out', 0, 6)])
            self.assertEqual(len(result([10, 20])), 2)
            self.assertEqual(result([30]), [])
            connection.execute("UPDATE dbo.T_STK_STKTRANSFERIN SET FTRANSFERDIRECT='RETURN'")
            self.assertEqual([(side, row['base_income_qty'], row['base_issue_qty']) for side, row in result([10, 20])], [('in', 0, -6), ('out', -6, 0)])
            connection.execute("UPDATE dbo.T_STK_STKTRANSFERIN SET FISGENFORIOS='1'")
            self.assertEqual(result([10, 20]), [])


if __name__ == '__main__':
    unittest.main()
