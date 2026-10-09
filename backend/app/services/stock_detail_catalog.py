"""Resolve descriptive labels only for identities in authorized source rows."""
from decimal import Decimal

from app.services.stock_detail_balance import stock_quantity


def _ids(rows, field):
    values = {row.get(field) for row in rows}
    if any(type(value) is not int or value <= 0 for value in values):
        raise ValueError('库存基础资料内码无效')
    return sorted(values)


def _read(cursor, sql, ids):
    result = []
    for offset in range(0, len(ids), 500):
        batch = ids[offset:offset + 500]
        cursor.execute(sql.format(ids=','.join(['%s'] * len(batch))), tuple(batch))
        result.extend(cursor.fetchall())
    return result


def _unique(rows, expected, key=lambda row: row['id']):
    result = {}
    for row in rows:
        identity = key(row)
        if identity in result:
            raise ValueError('库存基础资料映射重复')
        result[identity] = row
    if set(result) != set(expected):
        raise ValueError('库存基础资料映射缺失')
    return result


def load_catalog(cursor, rows):
    catalog = {name: {} for name in ('materials', 'units', 'stocks', 'statuses', 'owners')}
    if not rows:
        return catalog
    material_ids = _ids(rows, 'material_id')
    materials = _read(cursor, """
        SELECT M.FMATERIALID AS id, M.FNUMBER AS code,
            COALESCE(L.FNAME,M.FNUMBER) AS name,
            S.FSTOREUNITID AS unit_id, S.FSTOREURNUM AS numerator,
            S.FSTOREURNOM AS denominator, U.FPRECISION AS precision,
            COALESCE(UL.FNAME,U.FNUMBER) AS unit_name
        FROM dbo.T_BD_MATERIAL M
        LEFT JOIN dbo.T_BD_MATERIAL_L L ON L.FMATERIALID=M.FMATERIALID AND L.FLOCALEID=2052
        LEFT JOIN dbo.T_BD_MATERIALSTOCK S ON S.FMATERIALID=M.FMATERIALID
        LEFT JOIN dbo.T_BD_UNIT U ON U.FUNITID=S.FSTOREUNITID
        LEFT JOIN dbo.T_BD_UNIT_L UL ON UL.FUNITID=U.FUNITID AND UL.FLOCALEID=2052
        WHERE M.FMATERIALID IN ({ids})""", material_ids)
    catalog['materials'] = _unique(materials, material_ids)
    for identity, material in catalog['materials'].items():
        if type(material.get('unit_id')) is not int or material['unit_id'] <= 0:
            raise ValueError('库存单位映射缺失')
        try:
            stock_quantity(Decimal(0), material['numerator'], material['denominator'], material['precision'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('库存单位换算信息无效') from error
        catalog['units'][identity] = material
    stock_ids = _ids(rows, 'stock_id')
    catalog['stocks'] = _unique(_read(cursor, """
        SELECT S.FSTOCKID AS id, COALESCE(L.FNAME,S.FNUMBER) AS name
        FROM dbo.T_BD_STOCK S LEFT JOIN dbo.T_BD_STOCK_L L
          ON L.FSTOCKID=S.FSTOCKID AND L.FLOCALEID=2052
        WHERE S.FSTOCKID IN ({ids})""", stock_ids), stock_ids)
    status_ids = _ids(rows, 'stock_status_id')
    catalog['statuses'] = _unique(_read(cursor, """
        SELECT L.FSTOCKSTATUSID AS id, L.FNAME AS name
        FROM dbo.T_BD_STOCKSTATUS_L L
        WHERE L.FLOCALEID=2052 AND L.FSTOCKSTATUSID IN ({ids})""", status_ids), status_ids)
    owners = {(str(row.get('owner_type') or '').strip(), row.get('owner_id') or 0) for row in rows}
    if any(type(identity) is not int or identity < 0 or (identity and not kind) for kind, identity in owners):
        raise ValueError('货主内码无效')
    owners = {key for key in owners if key[1]}
    owner_rows = _read(cursor, """
        SELECT O.FITEMID AS id, O.FFORMID AS owner_type, COALESCE(L.FNAME,O.FNUMBER) AS name
        FROM dbo.V_ITEMCLASS_OWNER O LEFT JOIN dbo.V_ITEMCLASS_OWNER_L L
          ON L.FITEMID=O.FITEMID AND L.FLOCALEID=2052
        WHERE O.FITEMID IN ({ids})""", sorted({key[1] for key in owners}))
    catalog['owners'] = _unique(
        [row for row in owner_rows if (row['owner_type'], row['id']) in owners],
        owners, key=lambda row: (row['owner_type'], row['id']))
    return catalog


def row_labels(row, catalog):
    material = catalog['materials'][row['material_id']]
    owner_type = str(row.get('owner_type') or '').strip()
    owner = catalog['owners'].get((owner_type, row.get('owner_id') or 0), {})
    return {
        'material_code': material['code'], 'material_name': material['name'],
        'unit_name': material['unit_name'], 'stock_name': catalog['stocks'][row['stock_id']]['name'],
        'stock_status_name': catalog['statuses'][row['stock_status_id']]['name'],
        'owner_type_name': {'BD_OwnerOrg': '业务组织', 'BD_Customer': '客户', 'BD_Supplier': '供应商'}.get(owner_type, owner_type),
        'owner_name': owner.get('name', ''),
    }
