"""Read-only snapshot SQL traced to StkInvGetData in the supplied DLL.

The caller must establish a complete organization baseline before treating an
absent dimension as zero. A latest material row is not an inventory baseline.
"""
from datetime import date, timedelta


def effective_date(balance_date, balance_type):
    if type(balance_date) is not date or type(balance_type) is not int or balance_type not in (0, 1):
        raise ValueError('库存结存基点无效')
    if balance_type == 0:
        if balance_date == date.max:
            raise ValueError('库存结存基点超出日期范围')
        return balance_date + timedelta(days=1)
    return balance_date


def snapshot_sql(query, organization_id, balance_date, balance_type):
    if type(organization_id) is not int or organization_id <= 0:
        raise ValueError('组织范围无效')
    if effective_date(balance_date, balance_type) > query.start_date:
        raise ValueError('库存结存基点晚于查询开始日期')
    keyword = query.material.replace('[', '[[]').replace('%', '[%]').replace('_', '[_]')
    predicates = ['S.FSTOCKORGID=%s', 'S.FBALTYPE=%s', 'S.FBALDATE=%s',
        '''(M.FNUMBER LIKE %s OR EXISTS (SELECT 1 FROM dbo.T_BD_MATERIAL_L ML
            WHERE ML.FMATERIALID=M.FMATERIALID AND ML.FLOCALEID=2052
            AND (ML.FNAME LIKE %s OR ML.FSPECIFICATION LIKE %s)))''']
    params = [organization_id, balance_type, balance_date, *(['%' + keyword + '%'] * 3)]
    if query.stock_id is not None:
        predicates.append('S.FSTOCKID=%s'); params.append(query.stock_id)
    # The plugin checks shared strategy separately for material/BOM and each
    # polymorphic owner/keeper view. All values below are fixed source metadata.
    sql = '''SELECT S.FID AS snapshot_id, S.FSTOCKORGID AS organization_id,
        M.FMATERIALID AS material_id, M.FMASTERID AS material_master_id, M.FNUMBER AS material_code,
        S.FSTOCKID AS stock_id, S.FSTOCKSTATUSID AS stock_status_id,
        S.FOWNERTYPEID AS owner_type, O.FITEMID AS owner_id, S.FOWNERID AS owner_master_id,
        S.FKEEPERTYPEID AS keeper_type, K.FITEMID AS keeper_id, S.FKEEPERID AS keeper_master_id,
        S.FSTOCKLOCID AS stock_location_id, S.FAUXPROPID AS auxiliary_property_id,
        B.FID AS bom_id, S.FBOMID AS bom_master_id, S.FMTONO AS mto_no,
        L.FNUMBER AS lot_no, S.FLOT AS lot_master_id,
        CASE WHEN MS.FISBATCHMANAGE='1' AND MS.FISKFPERIOD='1' AND MS.FISEXPPARTOFLOT='1'
            THEN L.FPRODUCEDATE ELSE S.FPRODUCEDATE END AS produce_date,
        CASE WHEN MS.FISBATCHMANAGE='1' AND MS.FISKFPERIOD='1' AND MS.FISEXPPARTOFLOT='1'
            THEN L.FEXPIRYDATE ELSE S.FEXPIRYDATE END AS expiry_date,
        S.FBASEENDQTY AS base_qty
        FROM dbo.T_STK_INVBAL S
        INNER JOIN dbo.T_BD_MATERIAL M ON M.FMASTERID=S.FMATERIALID
          AND (M.FUSEORGID=S.FSTOCKORGID OR EXISTS (SELECT 1 FROM dbo.T_META_BASEDATATYPE BT
            WHERE BT.FBASEDATATYPEID='BD_MATERIAL' AND BT.FSTRATEGYTYPE=1))
        INNER JOIN dbo.T_BD_MATERIALSTOCK MS ON MS.FMATERIALID=M.FMATERIALID
        INNER JOIN dbo.T_BD_STOCK ST ON ST.FSTOCKID=S.FSTOCKID
        LEFT JOIN dbo.T_ENG_BOM B ON B.FMASTERID=S.FBOMID
          AND (B.FUSEORGID=S.FSTOCKORGID OR EXISTS (SELECT 1 FROM dbo.T_META_BASEDATATYPE BT
            WHERE BT.FBASEDATATYPEID='ENG_BOM' AND BT.FSTRATEGYTYPE=1))
        LEFT JOIN dbo.V_ITEMCLASS_OWNER O ON O.FMASTERID=S.FOWNERID AND O.FFORMID=S.FOWNERTYPEID
          AND (O.FUSEORGID=S.FSTOCKORGID OR O.FUSEORGID=0 OR EXISTS (
            SELECT 1 FROM dbo.T_META_BASEDATATYPE BT INNER JOIN dbo.V_ITEMCLASS_OWNER OV ON OV.FFORMID=BT.FBASEDATATYPEID
            WHERE BT.FSTRATEGYTYPE=1))
        LEFT JOIN dbo.V_ITEMCLASS_KEEPER K ON K.FMASTERID=S.FKEEPERID AND K.FFORMID=S.FKEEPERTYPEID
          AND (K.FUSEORGID=S.FSTOCKORGID OR K.FUSEORGID=0 OR EXISTS (
            SELECT 1 FROM dbo.T_META_BASEDATATYPE BT INNER JOIN dbo.V_ITEMCLASS_KEEPER KV ON KV.FFORMID=BT.FBASEDATATYPEID
            WHERE BT.FSTRATEGYTYPE=1))
        LEFT JOIN dbo.T_BD_LOTMASTER L ON L.FMASTERID=S.FLOT AND L.FUSEORGID=S.FSTOCKORGID
        WHERE ''' + ' AND '.join(predicates)
    return sql, params
