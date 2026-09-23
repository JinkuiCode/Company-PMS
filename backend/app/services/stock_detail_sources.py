"""Quantity-only source SQL, traced to the supplied 9.0.553.10 DLL.

These are raw adapters, not a complete report reader. Inventory update flags,
master mappings, unit conversion and period openings are resolved by the reader.
Never run a partial registry as though it covered the complete ERP report.
"""
from dataclasses import dataclass, replace
from datetime import timedelta
from app.services.business_data_scope import ALL_DATA_SCOPE


@dataclass(frozen=True)
class Source:
    header: str
    entry: str
    income: str
    issue: str
    quantity_table: str = ''
    owner_alias: str = 'E'
    additional: str = '1=1'
    mto_alias: str = 'E'
    joins: str = ''
    column_overrides: tuple = ()
    parent_join: str = ''
    entry_join: str = 'E.FID=H.FID'
    cancel_predicate: str = "H.FCANCELSTATUS='A'"


SOURCES = {
    'STK_INVINIT': Source('T_STK_INVINIT', 'T_STK_INVINITDETAIL', 'E.FBASEQTY', '0',
        joins="INNER JOIN dbo.T_BAS_SYSTEMPROFILE P ON P.FORGID=H.FSTOCKORGID AND P.FCATEGORY='STK' AND P.FKEY='STARTSTOCKDATE'",
        column_overrides=(('bill_date', 'DATEADD(day,-1,TRY_CONVERT(date,P.FVALUE))'),
                          ('keeper_type', 'H.FKEEPERTYPEID'), ('keeper_id', 'H.FKEEPERID')),
        cancel_predicate='1=1'),
    'PUR_MRB': Source('T_PUR_MRB', 'T_PUR_MRBENTRY', '-E.FBASEUNITQTY', '0',
        'T_PUR_MRBENTRY_F', additional="E.FSTOCKID>0 AND F.FISGENFORIOS='0' AND (E.FSTOCKFLAG='1' OR (H.FMRTYPE='B' AND B.FISINVENTORY='1' AND E.FSTOCKSTATUSID<>E.FRECEIVESTOCKSTATUSID))",
        joins='INNER JOIN dbo.T_PUR_MRBFIN F ON F.FID=H.FID INNER JOIN dbo.T_BD_MATERIALBASE B ON B.FMATERIALID=E.FMATERIALID'),
    'PUR_RECEIVEBILL': Source('T_PUR_RECEIVE', 'T_PUR_RECEIVEENTRY', 'E.FBASEUNITQTY', '0',
        'T_PUR_RECEIVEENTRY_F', additional="E.FSTOCKID>0 AND E.FSTOCKFLAG='1' AND B.FISINVENTORY='1'",
        joins='INNER JOIN dbo.T_PUR_RECEIVEFIN F ON F.FID=H.FID INNER JOIN dbo.T_BD_MATERIALBASE B ON B.FMATERIALID=E.FMATERIALID'),
    'SAL_OUTSTOCK': Source('T_SAL_OUTSTOCK', 'T_SAL_OUTSTOCKENTRY', '0', 'E.FBASEUNITQTY',
        'T_SAL_OUTSTOCKENTRY_F', additional="Q.FROWTYPE IN ('Son','Standard',' ') AND F.FISGENFORIOS='0' AND B.FISINVENTORY='1'",
        joins='INNER JOIN dbo.T_SAL_OUTSTOCKFIN F ON F.FID=H.FID INNER JOIN dbo.T_BD_MATERIALBASE B ON B.FMATERIALID=E.FMATERIALID INNER JOIN dbo.T_SAL_OUTSTOCKENTRY_R R ON R.FENTRYID=E.FENTRYID'),
    'SAL_RETURNSTOCK': Source('T_SAL_RETURNSTOCK', 'T_SAL_RETURNSTOCKENTRY', '0', '-E.FBASEUNITQTY',
        'T_SAL_RETURNSTOCKENTRY_F', additional="Q.FROWTYPE IN ('Son','Standard',' ') AND F.FISGENFORIOS='0' AND B.FISINVENTORY='1' AND E.FRETURNTYPE <> '0fa6270ab70b416cb2a7141a8f182d64'",
        joins='INNER JOIN dbo.T_SAL_RETURNSTOCKFIN F ON F.FID=H.FID INNER JOIN dbo.T_BD_MATERIALBASE B ON B.FMATERIALID=E.FMATERIALID INNER JOIN dbo.T_SAL_RETURNSTOCKENTRY_R R ON R.FENTRYID=E.FENTRYID'),
    'PRD_FEEDMTRL': Source('T_PRD_FEEDMTRL', 'T_PRD_FEEDMTRLDATA', '0', 'Q.FBASESTOCKACTUALQTY', 'T_PRD_FEEDMTRLDATA_Q'),
    'PRD_INSTOCK': Source('T_PRD_INSTOCK', 'T_PRD_INSTOCKENTRY', 'E.FBASEREALQTY', '0', additional='H.FENTRUSTINSTOCKID=0'),
    'PRD_PICKMTRL': Source('T_PRD_PICKMTRL', 'T_PRD_PICKMTRLDATA', '0', 'Q.FBASESTOCKACTUALQTY', 'T_PRD_PICKMTRLDATA_A', 'Q'),
    'PRD_RETSTOCK': Source('T_PRD_RESTOCK', 'T_PRD_RESTOCKENTRY', '-E.FBASEREALQTY', '0', 'T_PRD_RESTOCKENTRY_A', additional='H.FENTRUSTRETSTOCKID=0'),
    'PRD_RETURNMTRL': Source('T_PRD_RETURNMTRL', 'T_PRD_RETURNMTRLENTRY', '0', '-Q.FBASESTOCKQTY', 'T_PRD_RETURNMTRLENTRY_A'),
    'REM_INSTOCK': Source('T_REM_INSTOCK', 'T_REM_INSTOCKENTRY', 'E.FBASEREALQTY', '0'),
    'REM_OUTSTOCK': Source('T_REM_OUTSTOCK', 'T_REM_OUTSTOCKENTRY', '-E.FBASEREALQTY', '0'),
    'REM_PICKMTRL': Source('T_REM_PICKMTRL', 'T_REM_PICKMTRLDATA', '0', 'Q.FBASESTOCKACTUALQTY', 'T_REM_PICKMTRLDATA_A', 'Q'),
    'REM_RETURNMTRL': Source('T_REM_RETURNMTRL', 'T_REM_RETURNMTRLENTRY', '0', '-Q.FBASESTOCKQTY', 'T_REM_RETURNMTRLENTRY_A'),
    'SP_INSTOCK': Source('T_SP_INSTOCK', 'T_SP_INSTOCKENTRY', 'E.FBASEREALQTY', '0'),
    'SP_OUTSTOCK': Source('T_SP_OUTSTOCK', 'T_SP_OUTSTOCKENTRY', '-E.FBASEOUTQTY', '0', 'T_SP_OUTSTOCKENTRY_R'),
    'SP_PICKMTRL': Source('T_SP_PICKMTRL', 'T_SP_PICKMTRLDATA', '0', 'E.FBASEACTUALQTY'),
    'SP_RETURNMTRL': Source('T_SP_RETURNMTRL', 'T_SP_RETURNMTRLENTRY', '0', '-E.FBASEQTY'),
    'SUB_EXCONSUME': Source('T_SUB_EXCONSUME', 'T_SUB_EXCONSUMEENTRY', '0', 'E.FBASESTOCKACTUALQTY'),
    'SUB_FEEDMTRL': Source('T_SUB_FEEDMTRL', 'T_SUB_FEEDMTRLENTRY', '0', 'Q.FBASESTOCKACTUALQTY', 'T_SUB_FEEDMTRLENTRY_Q'),
    'SUB_PICKMTRL': Source('T_SUB_PICKMTRL', 'T_SUB_PICKMTRLDATA', '0', 'E.FBASESTOCKACTUALQTY', 'T_SUB_PICKMTRLDATA_A', 'Q'),
    'SUB_RETURNMTRL': Source('T_SUB_RETURNMTRL', 'T_SUB_RETURNMTRLENTRY', '0', '-E.FBASESTOCKQTY', 'T_SUB_RETURNMTRLENTRY_A', mto_alias='Q'),
    'STK_MISCELLANEOUS': Source('T_STK_MISCELLANEOUS', 'T_STK_MISCELLANEOUSENTRY',
        "CASE WHEN H.FSTOCKDIRECT='GENERAL' THEN E.FBASEQTY WHEN H.FSTOCKDIRECT='RETURN' THEN -E.FBASEQTY ELSE NULL END", '0', 'T_STK_MISCELLANEOUSENTRY_R'),
    'STK_MISDELIVERY': Source('T_STK_MISDELIVERY', 'T_STK_MISDELIVERYENTRY', '0',
        "CASE WHEN H.FSTOCKDIRECT='GENERAL' THEN E.FBASEQTY WHEN H.FSTOCKDIRECT='RETURN' THEN -E.FBASEQTY ELSE NULL END", 'T_STK_MISDELIVERYENTRY_R'),
    'STK_OEMINSTOCK': Source('T_STK_OEMINSTOCK', 'T_STK_OEMINSTOCKENTRY', 'E.FBASEQTY', '0', 'T_STK_OEMINSTOCKENTRY_R'),
    'STK_OEMINSTOCKRETURN': Source('T_STK_OEMINSTOCKRTN', 'T_STK_OEMINSTOCKRTNENTRY', '-E.FBASEQTY', '0', 'T_STK_OEMINSTOCKRTNENTRY_R', additional="H.FRETURNTYPE='StockReMat'"),
    'STK_STOCKCOUNTGAIN': Source('T_STK_STKCOUNTGAIN', 'T_STK_STKCOUNTGAINENTRY', 'E.FBASEGAINQTY', '0'),
    'STK_STOCKCOUNTLOSS': Source('T_STK_STKCOUNTLOSS', 'T_STK_STKCOUNTLOSSENTRY', '0', 'E.FBASELOSSQTY'),
    'STK_LOTADJUST': Source('T_STK_LOTADJUST', 'T_STK_LOTADJUSTENTRY',
        "CASE WHEN UPPER(E.FCONVERTTYPE)='B' THEN E.FBASEQTY WHEN UPPER(E.FCONVERTTYPE)='A' THEN 0 ELSE NULL END",
        "CASE WHEN UPPER(E.FCONVERTTYPE)='A' THEN E.FBASEQTY WHEN UPPER(E.FCONVERTTYPE)='B' THEN 0 ELSE NULL END"),
    'STK_STATUSCONVERT': Source('T_STK_STATUSCONVERT', 'T_STK_STATUSCONVERTENTRY',
        "CASE WHEN UPPER(E.FCONVERTTYPE)='B' THEN E.FBASEQTY WHEN UPPER(E.FCONVERTTYPE)='A' THEN 0 ELSE NULL END",
        "CASE WHEN UPPER(E.FCONVERTTYPE)='A' THEN E.FBASEQTY WHEN UPPER(E.FCONVERTTYPE)='B' THEN 0 ELSE NULL END"),
    'STK_STOCKCONVERT': Source('T_STK_STOCKCONVERT', 'T_STK_STOCKCONVERTENTRY',
        "CASE WHEN UPPER(E.FCONVERTTYPE)='B' THEN E.FBASEQTY WHEN UPPER(E.FCONVERTTYPE)='A' THEN 0 ELSE NULL END",
        "CASE WHEN UPPER(E.FCONVERTTYPE)='A' THEN E.FBASEQTY WHEN UPPER(E.FCONVERTTYPE)='B' THEN 0 ELSE NULL END", 'T_STK_STOCKCONVERTENTRY_R'),
}


_TRANSFER_FILTER = "H.FISGENFORIOS<>'1' AND H.FOBJECTTYPEID='STK_TransferDirect' AND Q.FROWTYPE IN ('Son','Standard',' ') AND B.FISINVENTORY='1'"
_TRANSFER_JOINS = 'INNER JOIN dbo.T_STK_STKTRANSFERINENTRY_R R ON R.FENTRYID=E.FENTRYID INNER JOIN dbo.T_BD_MATERIALBASE B ON B.FMATERIALID={material}'
MULTI_SOURCES = {
    'STK_ASSEMBLEDAPP': (
        ('product', Source('T_STK_ASSEMBLY', 'T_STK_ASSEMBLYPRODUCT',
            "CASE UPPER(H.FAFFAIRTYPE) WHEN 'ASSEMBLY' THEN E.FBASEQTY WHEN 'DASSEMBLY' THEN 0 ELSE NULL END",
            "CASE UPPER(H.FAFFAIRTYPE) WHEN 'ASSEMBLY' THEN 0 WHEN 'DASSEMBLY' THEN E.FBASEQTY ELSE NULL END",
            joins='LEFT JOIN dbo.T_STK_ASSEMBLYPRODUCT_R R ON R.FENTRYID=E.FENTRYID')),
        ('component', Source('T_STK_ASSEMBLY', 'T_STK_ASSEMBLYSUBITEM',
            "CASE UPPER(H.FAFFAIRTYPE) WHEN 'ASSEMBLY' THEN 0 WHEN 'DASSEMBLY' THEN E.FBASEQTY ELSE NULL END",
            "CASE UPPER(H.FAFFAIRTYPE) WHEN 'ASSEMBLY' THEN E.FBASEQTY WHEN 'DASSEMBLY' THEN 0 ELSE NULL END",
            joins='INNER JOIN dbo.T_BD_STOCK S ON S.FSTOCKID=E.FSTOCKID LEFT JOIN dbo.T_STK_ASSEMBLYPRODUCT_R R ON R.FENTRYID=E.FENTRYID',
            column_overrides=(('entry_id', 'E.FDETAILID'),),
            parent_join='INNER JOIN dbo.T_STK_ASSEMBLYPRODUCT P ON P.FID=H.FID', entry_join='E.FENTRYID=P.FENTRYID')),
    ),
    'STK_INSTOCK': (
        ('stock', Source('T_STK_INSTOCK', 'T_STK_INSTOCKENTRY', 'E.FBASEUNITQTY', '0',
            'T_STK_INSTOCKENTRY_F', additional="F.FISGENFORIOS='0' AND B.FISINVENTORY='1'",
            joins='INNER JOIN dbo.T_STK_INSTOCKFIN F ON F.FID=H.FID INNER JOIN dbo.T_BD_MATERIALBASE B ON B.FMATERIALID=E.FMATERIALID')),
        ('receive', Source('T_STK_INSTOCK', 'T_STK_INSTOCKENTRY', '0', 'E.FBASEUNITQTY',
            'T_STK_INSTOCKENTRY_F', additional="F.FISGENFORIOS='0' AND E.FRECEIVESTOCKFLAG='1' AND E.FRECEIVESTOCKID>0 AND E.FRECEIVESTOCKSTATUS>0",
            joins='INNER JOIN dbo.T_STK_INSTOCKFIN F ON F.FID=H.FID INNER JOIN dbo.T_BD_STOCK S ON S.FSTOCKID=E.FRECEIVESTOCKID',
            column_overrides=(('stock_id', 'E.FRECEIVESTOCKID'), ('stock_status_id', 'E.FRECEIVESTOCKSTATUS'),
                ('stock_location_id', 'E.FRECEIVESTOCKLOCID'), ('lot_no', 'E.FRECEIVELOT_TEXT'),
                ('owner_type', 'E.FRECEIVEOWNERTYPEID'), ('owner_id', 'E.FRECEIVEOWNERID'),
                ('auxiliary_property_id', 'E.FRECEIVEAUXPROPID'), ('mto_no', 'E.FRECEIVEMTONO')))),
    ),
    'STK_TRANSFERDIRECT': (
        ('in', Source('T_STK_STKTRANSFERIN', 'T_STK_STKTRANSFERINENTRY',
            "CASE UPPER(H.FTRANSFERDIRECT) WHEN 'GENERAL' THEN E.FBASEQTY WHEN 'RETURN' THEN 0 ELSE NULL END",
            "CASE UPPER(H.FTRANSFERDIRECT) WHEN 'GENERAL' THEN 0 WHEN 'RETURN' THEN -E.FBASEQTY ELSE NULL END",
            'T_STK_STKTRANSFERINENTRY_T', additional=_TRANSFER_FILTER,
            joins=_TRANSFER_JOINS.format(material='E.FMATERIALID'), column_overrides=(
                ('stock_id', 'E.FDESTSTOCKID'), ('stock_status_id', 'E.FDESTSTOCKSTATUSID'),
                ('stock_location_id', 'E.FDESTSTOCKLOCID'), ('lot_no', 'E.FDESTLOT_TEXT'),
                ('stock_flag', 'E.FSTOCKINFLAG')))),
        ('out', Source('T_STK_STKTRANSFERIN', 'T_STK_STKTRANSFERINENTRY',
            "CASE UPPER(H.FTRANSFERDIRECT) WHEN 'GENERAL' THEN 0 WHEN 'RETURN' THEN -E.FBASEQTY ELSE NULL END",
            "CASE UPPER(H.FTRANSFERDIRECT) WHEN 'GENERAL' THEN E.FBASEQTY WHEN 'RETURN' THEN 0 ELSE NULL END",
            'T_STK_STKTRANSFERINENTRY_T', additional=_TRANSFER_FILTER,
            joins=_TRANSFER_JOINS.format(material='E.FSRCMATERIALID'), column_overrides=(
                ('organization_id', 'H.FSTOCKOUTORGID'), ('material_id', 'E.FSRCMATERIALID'),
                ('stock_id', 'E.FSRCSTOCKID'), ('stock_status_id', 'E.FSRCSTOCKSTATUSID'),
                ('stock_location_id', 'E.FSRCSTOCKLOCID'), ('bom_id', 'E.FSRCBOMID'),
                ('owner_type', 'E.FOWNERTYPEOUTID'), ('owner_id', 'E.FOWNEROUTID'),
                ('keeper_type', 'E.FKEEPERTYPEOUTID'), ('keeper_id', 'E.FKEEPEROUTID'),
                ('stock_flag', 'E.FSTOCKOUTFLAG')))),
    ),
}


def _mapped(source, **columns):
    return replace(source, column_overrides=tuple((dict(source.column_overrides) | columns).items()))


_direct_in = MULTI_SOURCES['STK_TRANSFERDIRECT'][0][1]
_direct_out = MULTI_SOURCES['STK_TRANSFERDIRECT'][1][1]
MULTI_SOURCES['REM_TRANSFERDIRECT'] = tuple((side, replace(source,
    header='T_REM_STKTRANSFERIN', entry='T_REM_STKTRANSFERINENTRY', quantity_table='T_REM_STKTRANSFERINENTRY_T',
    joins='INNER JOIN dbo.T_REM_STKTRANSFERINENTRY_R R ON R.FENTRYID=E.FENTRYID', additional='1=1'))
    for side, source in MULTI_SOURCES['STK_TRANSFERDIRECT'])

_step_in = replace(_direct_in,
    additional="H.FISGENFORIOS<>'1' AND H.FOBJECTTYPEID='STK_TRANSFERIN'",
    joins='INNER JOIN dbo.T_STK_STKTRANSFERINENTRY_R R ON R.FENTRYID=E.FENTRYID')
_step_in_a = _mapped(replace(_direct_out, income='-E.FBASEQTY-Q.FBASEPATHLOSSQTY', issue='0',
    additional=_step_in.additional + " AND H.FVESTONWAY='A'", joins=_step_in.joins),
    produce_date='E.FSRCPRODUCEDATE', expiry_date='E.FSRCEXPIRYDATE', mto_no='E.FSRCMTONO')
_step_in_b = _mapped(replace(_step_in, income='-E.FBASEQTY-Q.FBASEPATHLOSSQTY', issue='0',
    additional=_step_in.additional + " AND H.FVESTONWAY='B'"),
    stock_status_id='E.FSRCSTOCKSTATUSID', stock_flag='E.FSTOCKOUTFLAG')
MULTI_SOURCES['STK_TRANSFERIN'] = (('in', _step_in), ('transit_a', _step_in_a), ('transit_b', _step_in_b))

_step_out = Source('T_STK_STKTRANSFEROUT', 'T_STK_STKTRANSFEROUTENTRY', _direct_out.income, _direct_out.issue,
    'T_STK_STKTRANSFEROUTENTRY_T', additional="H.FISGENFORIOS<>'1'",
    joins='INNER JOIN dbo.T_STK_STKTRANSFEROUTENTRY_R R ON R.FENTRYID=E.FENTRYID',
    column_overrides=(('stock_id', 'E.FSRCSTOCKID'), ('stock_status_id', 'E.FSRCSTOCKSTATUSID'),
        ('stock_location_id', 'E.FSRCSTOCKLOCID'), ('stock_flag', 'E.FSTOCKOUTFLAG')))
_step_out_a = _mapped(replace(_step_out, income='E.FBASEQTY', issue='0',
    additional=_step_out.additional + " AND H.FVESTONWAY='A'"),
    stock_status_id='E.FDESTSTOCKSTATUSID', stock_flag='E.FSTOCKINFLAG')
_step_out_b = _mapped(replace(_step_out, income='E.FBASEQTY', issue='0',
    additional=_step_out.additional + " AND H.FVESTONWAY='B'"),
    organization_id='H.FSTOCKINORGID', material_id='E.FDESTMATERIALID', stock_id='E.FDESTSTOCKID',
    stock_location_id='E.FDESTSTOCKLOCID', stock_status_id='E.FDESTSTOCKSTATUSID', stock_flag='E.FSTOCKINFLAG',
    owner_type='E.FOWNERTYPEINID', owner_id='E.FOWNERINID', keeper_type='E.FKEEPERTYPEINID', keeper_id='E.FKEEPERINID',
    produce_date='E.FDESTPRODUCEDATE', expiry_date='E.FDESTEXPIRYDATE', bom_id='E.FDESTBOMID',
    mto_no='E.FDESTMTONO', lot_no='E.FDESTLOT_TEXT')
MULTI_SOURCES['STK_TRANSFEROUT'] = (('out', _step_out), ('transit_a', _step_out_a), ('transit_b', _step_out_b))


def require_source_coverage(registered_form_ids):
    codes = {str(code).strip().upper() for code in registered_form_ids}
    if not codes or codes - (SOURCES.keys() | MULTI_SOURCES.keys()):
        raise ValueError('报表来源适配未完成，不能返回不完整的收发明细')


def movement_sql(form_id, query, organizations):
    source = SOURCES.get(form_id.upper())
    if source is None:
        raise ValueError('来源适配未完成')
    return _source_sql(source, query, organizations)


def movement_queries(form_id, query, organizations):
    sources = MULTI_SOURCES.get(form_id.upper())
    if sources is None:
        sql, params = movement_sql(form_id, query, organizations)
        return [('main', sql, params)]
    return [(side, *_source_sql(source, query, organizations)) for side, source in sources]


def _source_sql(source, query, organizations):
    owner = source.owner_alias
    columns = dict(organization_id='H.FSTOCKORGID', bill_id='H.FID', bill_no='H.FBILLNO',
        bill_date='H.FDATE', created_at='H.FCREATEDATE', entry_id='E.FENTRYID', bill_seq='E.FSEQ',
        material_id='E.FMATERIALID', material_master_id='M.FMASTERID', material_code='M.FNUMBER',
        stock_id='E.FSTOCKID', stock_status_id='E.FSTOCKSTATUSID', owner_type=f'{owner}.FOWNERTYPEID',
        owner_id=f'{owner}.FOWNERID', keeper_type=f'{owner}.FKEEPERTYPEID', keeper_id=f'{owner}.FKEEPERID',
        stock_location_id='E.FSTOCKLOCID', lot_no='E.FLOT_TEXT', auxiliary_property_id='E.FAUXPROPID',
        bom_id='E.FBOMID', mto_no=f'{source.mto_alias}.FMTONO', produce_date='E.FPRODUCEDATE',
        expiry_date='E.FEXPIRYDATE', stock_flag='E.FSTOCKFLAG',
        base_income_qty=source.income, base_issue_qty=source.issue)
    columns.update(source.column_overrides)
    predicates, params = [], []
    if organizations is not ALL_DATA_SCOPE:
        ids = list(organizations or [])
        if not ids or len(ids) > 1800 or any(type(value) is not int or value <= 0 for value in ids):
            raise ValueError('组织范围无效')
        ids = sorted(set(ids))
        predicates.append(columns['organization_id'] + ' IN (' + ','.join(['%s'] * len(ids)) + ')')
        params.extend(ids)
    if query.end_date.year == 9999 and query.end_date.month == 12 and query.end_date.day == 31:
        raise ValueError('截止日期超出可查询范围')
    predicates.extend([source.cancel_predicate, "H.FDOCUMENTSTATUS='C'", source.additional,
                       f"{columns['bill_date']}>=%s AND {columns['bill_date']}<%s"])
    params.extend([query.start_date, query.end_date + timedelta(days=1)])
    keyword = query.material.replace('[', '[[]').replace('%', '[%]').replace('_', '[_]')
    predicates.append('''(M.FNUMBER LIKE %s OR EXISTS (SELECT 1 FROM dbo.T_BD_MATERIAL_L ML
        WHERE ML.FMATERIALID=M.FMATERIALID AND ML.FLOCALEID=2052
          AND (ML.FNAME LIKE %s OR ML.FSPECIFICATION LIKE %s)))''')
    params.extend(['%' + keyword + '%'] * 3)
    if query.stock_id is not None:
        predicates.append(columns['stock_id'] + '=%s'); params.append(query.stock_id)
    join = (f'INNER JOIN dbo.{source.quantity_table} Q ON Q.FENTRYID=E.FENTRYID'
            if source.quantity_table else '')
    projection = ', '.join(f'{expression} AS {key}' for key, expression in columns.items())
    sql = f'''SELECT {projection}
        FROM dbo.{source.header} H {source.parent_join}
        INNER JOIN dbo.{source.entry} E ON {source.entry_join}
        {join}
        {source.joins}
        INNER JOIN dbo.T_BD_MATERIAL M ON M.FMATERIALID={columns['material_id']}
        WHERE {' AND '.join(predicates)}'''
    return sql, params
