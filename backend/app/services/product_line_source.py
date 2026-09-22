"""Verified Kingdee organization catalog, using only the dedicated reader."""
from fastapi import HTTPException
from app.schemas.product_line import OrganizationOption
from app.services.purchase_connection import purchase_connection

FROM_CATALOG = (' FROM dbo.T_ORG_ORGANIZATIONS o '
                'JOIN dbo.T_ORG_ORGANIZATIONS_L l ON l.FORGID=o.FORGID AND l.FLOCALEID=%s ')
COLUMNS = ('o.FORGID AS organization_id,o.FNUMBER AS code,l.FNAME AS name,'
           'o.FFORBIDSTATUS AS forbid_status,o.FDOCUMENTSTATUS AS document_status')


def _option(row):
    return OrganizationOption(source_key='kingdee', organization_id=row['organization_id'],
        code=row['code'].strip(), name=row['name'].strip(),
        active=row['forbid_status'] == 'A' and row['document_status'] == 'C')


def _like(value):
    for char in ('~', '%', '_', '['):
        value = value.replace(char, '~' + char)
    return '%' + value + '%'


def list_organizations(keyword='', page=1, page_size=50, *, connection_factory=purchase_connection):
    if page < 1 or not 1 <= page_size <= 500 or len(keyword) > 100:
        raise HTTPException(422, '分页或搜索参数无效')
    where = ("WHERE o.FFORBIDSTATUS='A' AND o.FDOCUMENTSTATUS='C' "
             'AND LEN(LTRIM(RTRIM(l.FNAME)))>0 AND LEN(LTRIM(RTRIM(o.FNUMBER)))>0')
    params = [2052]
    if keyword.strip():
        where += " AND (o.FNUMBER LIKE %s ESCAPE '~' OR l.FNAME LIKE %s ESCAPE '~')"
        params.extend([_like(keyword.strip())] * 2)
    try:
        with connection_factory() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute('SELECT COUNT(*) AS total' + FROM_CATALOG + where, tuple(params))
                total = cursor.fetchone()['total']
                cursor.execute('SELECT ' + COLUMNS + FROM_CATALOG + where +
                    ' ORDER BY o.FNUMBER,o.FORGID OFFSET %s ROWS FETCH NEXT %s ROWS ONLY',
                    tuple(params + [(page-1)*page_size, page_size]))
                items = [_option(row).model_dump() for row in cursor.fetchall()]
                return {'items': items, 'total': total}
            finally:
                cursor.close()
    except Exception:
        raise HTTPException(503, '金蝶组织目录暂不可用，请稍后重试') from None


def get_organization(organization_id, *, connection_factory=purchase_connection):
    if type(organization_id) is not int or organization_id <= 0:
        raise HTTPException(422, '组织编号无效')
    try:
        with connection_factory() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute('SELECT TOP (2) ' + COLUMNS + FROM_CATALOG + 'WHERE o.FORGID=%s', (2052, organization_id))
                rows = cursor.fetchall()
            finally:
                cursor.close()
        if len(rows) != 1:
            raise HTTPException(422, '组织不存在或中文名称不唯一，请核对金蝶资料')
        option = _option(rows[0])
        if not option.active:
            raise HTTPException(422, '金蝶组织未审核或已禁用')
        return option
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, '金蝶组织目录暂不可用，请稍后重试') from None
