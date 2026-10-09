"""Read all registered quantity sources using the runtime read-only connection."""
from app.services.business_data_scope import ALL_DATA_SCOPE
from app.services.stock_detail_baseline import load_baseline
from app.services.stock_detail_catalog import load_catalog
from app.services.stock_detail_engine import compile_organization, validate_registry
from app.services.stock_detail_reader import effective_organizations
from app.services.stock_detail_snapshots import snapshot_sql
from app.services.stock_detail_sources import movement_queries


BILL_NAMES = {
    'STK_INVINIT': '初始库存', 'PRD_FEEDMTRL': '生产补料单', 'PRD_INSTOCK': '生产入库单',
    'PRD_PICKMTRL': '生产领料单', 'PRD_RETSTOCK': '生产退库单', 'PRD_RETURNMTRL': '生产退料单',
    'PUR_MRB': '采购退料单', 'PUR_RECEIVEBILL': '采购收料单',
    'REM_INSTOCK': '生产线产品入库单', 'REM_OUTSTOCK': '生产线产品退库单',
    'REM_PICKMTRL': '生产线领料单', 'REM_RETURNMTRL': '生产线退料单',
    'REM_TRANSFERDIRECT': '生产线在制仓库调拨单',
    'SAL_OUTSTOCK': '销售出库单', 'SAL_RETURNSTOCK': '销售退货单',
    'SP_INSTOCK': '简单生产入库单', 'SP_OUTSTOCK': '简单生产退库单',
    'SP_PICKMTRL': '简单生产领料单', 'SP_RETURNMTRL': '简单生产退料单',
    'STK_ASSEMBLEDAPP': '组装拆卸单', 'STK_INSTOCK': '采购入库单', 'STK_LOTADJUST': '批号调整单',
    'STK_MISCELLANEOUS': '其他入库单', 'STK_MISDELIVERY': '其他出库单',
    'STK_OEMINSTOCK': '受托加工材料入库单', 'STK_OEMINSTOCKRETURN': '受托加工材料退料单',
    'STK_STATUSCONVERT': '形态转换单', 'STK_STOCKCONVERT': '库存状态转换单',
    'STK_STOCKCOUNTGAIN': '盘盈单', 'STK_STOCKCOUNTLOSS': '盘亏单',
    'STK_TRANSFERDIRECT': '直接调拨单', 'STK_TRANSFERIN': '分步式调入单', 'STK_TRANSFEROUT': '分步式调出单',
    'SUB_EXCONSUME': '委外超耗单', 'SUB_FEEDMTRL': '委外补料单',
    'SUB_PICKMTRL': '委外领料单', 'SUB_RETURNMTRL': '委外退料单',
}


def read_dataset(connection, query, authorized):
    organizations = effective_organizations(query, authorized)
    result = dict(rows=[], openings={}, labels={})
    if organizations == []:
        return result
    cursor = connection.cursor()
    try:
        cursor.execute('SELECT snapshot_isolation_state FROM sys.databases WHERE name=DB_NAME()', ())
        state = cursor.fetchall()
        if len(state) != 1 or state[0]['snapshot_isolation_state'] != 1:
            raise ValueError('数据库尚未启用事务级一致性快照，拒绝返回可能错配的库存数据')
        connection.rollback()
        cursor.execute('SET TRANSACTION ISOLATION LEVEL SNAPSHOT', ())
        # pymssql starts a new transaction after rollback; restart under the new isolation.
        connection.rollback()
        cursor.execute('SELECT FBILLFORMID,FCLASSNAME,FRPTTYPE FROM dbo.T_BAS_UPDATESTOCKRPTSET', ())
        forms = validate_registry(cursor.fetchall())
        if set(forms) - BILL_NAMES.keys():
            raise ValueError('单据名称映射尚未核实')
        if organizations is ALL_DATA_SCOPE:
            cursor.execute("""SELECT DISTINCT FORGID AS organization_id FROM dbo.T_BAS_SYSTEMPROFILE
                WHERE FCATEGORY='STK' AND FKEY='STARTSTOCKDATE'""", ())
            organizations = sorted({row['organization_id'] for row in cursor.fetchall()})
            if any(type(value) is not int or value <= 0 for value in organizations):
                raise ValueError('库存组织目录无效')
        for organization_id in organizations:
            baseline = load_baseline(cursor, organization_id, query.start_date)
            snapshots = []
            if baseline.balance_type is not None:
                sql, params = snapshot_sql(query, organization_id, baseline.balance_date, baseline.balance_type)
                cursor.execute(sql, tuple(params))
                snapshots = cursor.fetchall()
            period_query = query.model_copy(update={'start_date': baseline.effective_date})
            movements = []
            for form in forms:
                for side, sql, params in movement_queries(form, period_query, [organization_id]):
                    cursor.execute(sql, tuple(params))
                    movements.extend((form, side, BILL_NAMES[form], row) for row in cursor.fetchall())
            catalog = load_catalog(cursor, [*snapshots, *(item[3] for item in movements)])
            compiled = compile_organization(query, organization_id, baseline, snapshots, movements, catalog)
            result['rows'].extend(compiled['rows'])
            result['openings'].update(compiled['openings'])
            result['labels'].update(compiled['labels'])
        return result
    finally:
        try:
            connection.rollback()
        finally:
            cursor.close()
