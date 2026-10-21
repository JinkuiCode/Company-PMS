"""Report-only material identities; master visibility never grants business rows."""
from fastapi import HTTPException
from app.services.business_data_scope import ALL_DATA_SCOPE


def normalize_codes(values):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 1000:
        raise HTTPException(422, '请选择1至1000个物料编码')
    if any(type(v) is not str or not v.strip() or len(v) > 256 or any(ord(c) < 32 or ord(c) == 127 for c in v) for v in values):
        raise HTTPException(422, '物料编码必须为非空字符串，单项最多256个字符')
    return list(dict.fromkeys(v.strip().lower() for v in values))


def material_organizations(selected, authorized):
    if not isinstance(selected, (list, tuple)) or len(selected) > 200 or any(type(v) is not int or v <= 0 for v in selected):
        raise HTTPException(422, '物料引用产品线范围无效')
    selected = sorted(set(selected))
    if authorized is ALL_DATA_SCOPE:
        return selected or ALL_DATA_SCOPE
    allowed = sorted({v for v in (authorized or []) if type(v) is int and v > 0})
    return [v for v in selected if v in allowed] if selected else allowed


def list_material_candidates(cursor, keyword, organizations, *, page=1, page_size=50,
                             ids=(), batch_field='code', batch_values=()):
    if (type(page) is not int or not 1 <= page <= 1000000 or type(page_size) is not int or not 1 <= page_size <= 500 or
            not isinstance(keyword, str) or len(keyword) > 100 or batch_field not in {'code', 'name'} or
            not isinstance(ids, (list, tuple)) or not isinstance(batch_values, (list, tuple)) or
            len(ids) > 1000 or len(batch_values) > 1000 or sum(bool(v) for v in (keyword.strip(), ids, batch_values)) > 1):
        raise HTTPException(422, '物料引用查询参数无效')
    normalized = normalize_codes(ids) if ids else []
    batch_keys = normalize_codes(batch_values) if batch_values else []
    if organizations is not ALL_DATA_SCOPE:
        organizations = material_organizations([], organizations)
        if not organizations:
            if ids:
                raise HTTPException(422, '选中物料已失效或无权访问，请重新选择')
            return dict(items=[], total=0, page=page, page_size=page_size, has_more=False, batch=None)
    params = []
    scope = '1=1'
    if organizations is not ALL_DATA_SCOPE:
        scope = '(M.FUSEORGID IN (' + ','.join(['%s'] * len(organizations)) + ') OR EXISTS (SELECT 1 FROM dbo.T_META_BASEDATATYPE BT WHERE BT.FBASEDATATYPEID=\'BD_MATERIAL\' AND BT.FSTRATEGYTYPE=1))'
        params.extend(organizations)
    prefix = f'''WITH eligible AS (SELECT LOWER(LTRIM(RTRIM(M.FNUMBER))) AS value,
        M.FNUMBER AS code,COALESCE(L.FNAME,M.FNUMBER) AS name
        FROM dbo.T_BD_MATERIAL M LEFT JOIN dbo.T_BD_MATERIAL_L L
        ON L.FMATERIALID=M.FMATERIALID AND L.FLOCALEID=2052
        WHERE {scope} AND M.FNUMBER IS NOT NULL AND LTRIM(RTRIM(M.FNUMBER))<>''),
        choices AS (SELECT value,MIN(code) AS code,
          CASE WHEN COUNT(DISTINCT name)>1 THEN CONCAT(MIN(name),N' 等',COUNT(DISTINCT name),N'种名称') ELSE MIN(name) END AS label,
          COUNT(DISTINCT value COLLATE Latin1_General_100_BIN2) AS key_count,COUNT(DISTINCT name) AS name_count
          FROM eligible GROUP BY value)'''
    predicate, extra = '1=1', []
    if normalized:
        predicate = 'value IN (' + ','.join(['%s'] * len(normalized)) + ')'
        extra = normalized
    elif batch_keys:
        column = 'value' if batch_field == 'code' else 'LOWER(LTRIM(RTRIM(name)))'
        predicate = f'value IN (SELECT value FROM eligible WHERE {column} IN (' + ','.join(['%s'] * len(batch_keys)) + '))'
        extra = batch_keys
    elif keyword.strip():
        from app.services.purchase_reader import _like
        predicate = "(code LIKE %s ESCAPE '~' OR value IN (SELECT value FROM eligible WHERE name LIKE %s ESCAPE '~'))"
        extra = [_like(keyword.strip())] * 2
    bound = [*params, *extra]
    if len(bound) + 2 > 2000:
        raise HTTPException(422, '物料查询参数过多，请缩小范围')
    filtered = prefix + f', filtered AS (SELECT * FROM choices WHERE {predicate})'
    if normalized:
        cursor.execute(filtered + ' SELECT value,code,key_count FROM filtered', tuple(bound))
        rows = cursor.fetchall()
        _check_rows(rows)
        if {r['value'] for r in rows} != set(normalized):
            raise HTTPException(422, '选中物料已失效或无权访问，请重新选择')
    batch, matched_names = None, {}
    if batch_keys:
        column = 'value' if batch_field == 'code' else 'LOWER(LTRIM(RTRIM(name)))'
        cursor.execute(prefix + f' SELECT {column} AS matched,COUNT(DISTINCT value) AS count FROM eligible WHERE {column} IN (' + ','.join(['%s'] * len(batch_keys)) + f') GROUP BY {column}', tuple([*params, *batch_keys]))
        counts = {r['matched']: r['count'] for r in cursor.fetchall()}
        originals = dict(zip((v.strip().lower() for v in batch_values), batch_values))
        batch = dict(input_count=len(originals), duplicate_count=len(batch_values)-len(originals), matched_records=sum(counts.values()),
            unmatched_values=[v for k,v in originals.items() if k not in counts],
            ambiguous_values=[v for k,v in originals.items() if counts.get(k,0)>1])
        if batch_field == 'name':
            cursor.execute(prefix + ' SELECT DISTINCT value,name FROM eligible WHERE LOWER(LTRIM(RTRIM(name))) IN (' + ','.join(['%s'] * len(batch_keys)) + ')', tuple([*params,*batch_keys]))
            for row in cursor.fetchall():
                previous = matched_names.get(row['value'])
                if previous and previous.strip().lower() != row['name'].strip().lower():
                    raise HTTPException(422, '同一物料编码匹配多个名称，请改按编码批量查询；原选择保留')
                matched_names[row['value']] = row['name']
    cursor.execute(filtered + ' SELECT COUNT(*) AS total FROM filtered', tuple(bound))
    total = cursor.fetchall()[0]['total']
    start = (page-1)*page_size
    cursor.execute(filtered + ', numbered AS (SELECT *,ROW_NUMBER() OVER (ORDER BY code,value) AS n FROM filtered) SELECT value,code,label,key_count,name_count FROM numbered WHERE n>%s AND n<=%s ORDER BY n', tuple([*bound,start,start+page_size]))
    rows = cursor.fetchall()
    _check_rows(rows)
    if batch_values and batch_field == 'name' and any(r['name_count'] > 1 for r in rows):
        raise HTTPException(422, '同一物料编码存在多个名称，请缩小产品线范围或改按编码批量查询；原选择保留')
    return dict(items=[{**{k:r[k] for k in ('value','code','label')}, **({'name':matched_names[r['value']]} if r['value'] in matched_names else {})} for r in rows], total=total,
        page=page, page_size=page_size, has_more=page*page_size<total, batch=batch)


def _check_rows(rows):
    for row in rows:
        if row['key_count'] != 1 or normalize_codes([row['code']])[0] != row['value']:
            raise HTTPException(422, '物料编码存在排序规则歧义，请缩小产品线范围后核对')


def require_material_codes(cursor, codes, organizations):
    normalized = normalize_codes(codes)
    list_material_candidates(cursor, '', organizations, ids=normalized, page_size=500)
    return normalized


def validate_reference_query(connection, query, organizations):
    codes = [*getattr(query, 'material_codes', []), *[v for c in query.conditions() if getattr(c, 'kind', None) == 'material-reference' for v in c.value]]
    if not codes:
        return
    selected = getattr(query, 'organization_ids', []) or ([query.organization_id] if getattr(query, 'organization_id', None) else [])
    scope = material_organizations(selected, organizations)
    if scope == []:
        raise HTTPException(422, '选中物料已失效或无权访问，请重新选择')
    cursor = connection.cursor()
    try:
        require_material_codes(cursor, codes, scope)
    finally:
        cursor.close()
