"""Fixed, read-only organization discovery. No grants or private config output."""
import json
import getpass
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.purchase_connection import purchase_connection


def inspect_organizations(cursor):
    cursor.execute("""SELECT TOP (2000) s.name AS schema_name, t.name AS table_name,
        c.name AS column_name, ty.name AS type_name
        FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
        JOIN sys.columns c ON c.object_id=t.object_id
        JOIN sys.types ty ON ty.user_type_id=c.user_type_id
        WHERE s.name='dbo' AND (t.name LIKE 'T_ORG_%'
          OR (t.name IN ('T_PUR_RECEIVE','T_PUR_MRB') AND c.name LIKE '%ORG%'))
        ORDER BY t.name,c.column_id""")
    columns = cursor.fetchall()
    result = dict(columns=columns, organization_catalog_status=(
        'metadata_visible_requires_review' if any(r['table_name'].startswith('T_ORG_') for r in columns)
        else 'metadata_not_visible'), ready_for_runtime=False, samples={})
    for name, sql in (
        ('requisition', 'SELECT TOP (100) FID, FAPPLICATIONORGID AS organization_id FROM dbo.T_PUR_REQUISITION WHERE FAPPLICATIONDATE >= %s ORDER BY FID DESC'),
        ('order', 'SELECT TOP (100) FID, FPURCHASEORGID AS organization_id FROM dbo.T_PUR_POORDER WHERE FDATE >= %s ORDER BY FID DESC'),
        ('stock', 'SELECT TOP (100) FID, FSTOCKORGID AS organization_id FROM dbo.T_STK_INSTOCK WHERE FDATE >= %s ORDER BY FID DESC'),
    ):
        cursor.execute(sql, ('2026-01-01',))
        sample = cursor.fetchall()
        result['samples'][name] = dict(count=len(sample), organization_ids=sorted({
            row['organization_id'] for row in sample if row['organization_id'] is not None}))
    return result


def inspect_catalog_rows(cursor, columns):
    actual = {(row['table_name'], row['column_name']) for row in columns}
    required = {(table, column) for table, names in (
        ('T_ORG_ORGANIZATIONS', 'FORGID FNUMBER FFORBIDSTATUS FDOCUMENTSTATUS'),
        ('T_ORG_ORGANIZATIONS_L', 'FORGID FLOCALEID FNAME'),
    ) for column in names.split()}
    if not required <= actual:
        raise ValueError('organization_catalog_columns_not_verified')
    cursor.execute('SELECT TOP (501) o.FORGID AS organization_id, o.FNUMBER AS code, '
                   'o.FFORBIDSTATUS AS forbid_status, o.FDOCUMENTSTATUS AS document_status, '
                   'l.FLOCALEID AS locale_id, l.FNAME AS name '
                   'FROM dbo.T_ORG_ORGANIZATIONS o LEFT JOIN dbo.T_ORG_ORGANIZATIONS_L l '
                   'ON l.FORGID=o.FORGID ORDER BY o.FORGID,l.FLOCALEID')
    rows = cursor.fetchall()
    return {'rows': rows[:500], 'truncated': len(rows) > 500}


def inspect_admin_connection(connection, *, catalog=False):
    try:
        cursor = connection.cursor()
        try:
            result = inspect_organizations(cursor)
            if catalog:
                result['catalog'] = inspect_catalog_rows(cursor, result['columns'])
            return result
        finally:
            cursor.close()
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def interactive_admin():
    import pymssql
    print('Read-only inspection: 10.10.1.248 / AIS20231211221516', flush=True)
    username = input('Database administrator username: ').strip()
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        password = getpass.getpass('Password (hidden; not saved): ')
    try:
        connection = pymssql.connect(
            server='10.10.1.248', database='AIS20231211221516',
            user=username, password=password, encryption='require',
            as_dict=True, read_only=True, autocommit=False,
            login_timeout=10, timeout=20, appname='PMS-Organization-ReadOnly-Discovery')
    finally:
        password = None
    return inspect_admin_connection(connection, catalog=True)


def main():
    try:
        if sys.argv[1:] == ['--interactive-admin']:
            result = interactive_admin()
            output = Path(__file__).resolve().parents[2] / '.runtime/organization-discovery.json'
            output.parent.mkdir(exist_ok=True)
            output.write_text(json.dumps(result, ensure_ascii=False, default=str, indent=2), encoding='utf-8')
        elif not sys.argv[1:]:
            with purchase_connection() as connection:
                cursor = connection.cursor()
                try:
                    result = inspect_organizations(cursor)
                finally:
                    cursor.close()
        else:
            raise ValueError('unsupported_arguments')
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({'phase': 'organization_discovery', 'error_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
