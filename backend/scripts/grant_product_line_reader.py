"""One-time, explicitly approved column grants to the existing report reader."""
import getpass
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.provision_purchase_reader import HOST, DATABASE, LOGIN, verify_reader

TABLES = {
    'T_ORG_ORGANIZATIONS': 'FORGID FNUMBER FFORBIDSTATUS FDOCUMENTSTATUS',
    'T_ORG_ORGANIZATIONS_L': 'FORGID FLOCALEID FNAME',
    'T_PUR_RECEIVE': 'FSTOCKORGID',
    'T_PUR_MRB': 'FSTOCKORGID',
}


def grant_statements():
    return [f"GRANT SELECT ({','.join('[' + col + ']' for col in cols.split())}) "
            f"ON OBJECT::[dbo].[{table}] TO [{LOGIN}]" for table, cols in TABLES.items()]


def verify_columns(cursor):
    for table, columns in TABLES.items():
        fields = ','.join('[' + column + ']' for column in columns.split())
        cursor.execute(f'SELECT TOP (0) {fields} FROM [dbo].[{table}]')
        cursor.fetchall()
        for permission in ('INSERT', 'UPDATE', 'DELETE', 'ALTER', 'CONTROL', 'TAKE OWNERSHIP'):
            cursor.execute("SELECT HAS_PERMS_BY_NAME(%s, 'OBJECT', %s) AS allowed", ('dbo.' + table, permission))
            if cursor.fetchone()['allowed'] != 0:
                raise RuntimeError('unexpected_write_permission')


def apply_grants(connection):
    cursor = connection.cursor()
    try:
        cursor.execute('SET LOCK_TIMEOUT 3000')
        cursor.execute('SELECT DB_NAME() AS db, SUSER_ID(%s) AS login_id, USER_ID(%s) AS user_id', (LOGIN, LOGIN))
        identity = cursor.fetchone()
        if identity['db'] != DATABASE or not identity['login_id'] or not identity['user_id']:
            raise RuntimeError('target_or_existing_reader_mismatch')
        for table, fields in TABLES.items():
            cursor.execute('SELECT name FROM sys.columns WHERE object_id=OBJECT_ID(%s)', ('dbo.' + table,))
            if not set(fields.split()) <= {row['name'] for row in cursor.fetchall()}:
                raise RuntimeError('source_columns_changed')
        for statement in grant_statements():
            cursor.execute(statement)
        cursor.execute(f"EXECUTE AS LOGIN = '{LOGIN}'")
        try:
            verify_reader(cursor)
            verify_columns(cursor)
        finally:
            cursor.execute('REVERT')
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def main():
    import pymssql
    connection = None
    phase = 'credential_input'
    result = {'host': HOST, 'database': DATABASE, 'login': LOGIN, 'complete': False}
    try:
        print(f'Approved column SELECT only: {HOST} / {DATABASE} / {LOGIN}', flush=True)
        username = input('Database administrator username: ').strip()
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            password = getpass.getpass('Password (hidden; not saved): ')
        phase = 'admin_connection'
        try:
            connection = pymssql.connect(server=HOST, database=DATABASE, user=username, password=password,
                encryption='require', as_dict=True, autocommit=False, login_timeout=10, timeout=20,
                appname='PMS-Approved-Organization-Column-Grants')
        finally:
            password = None
        phase = 'grant_and_verify'
        apply_grants(connection)
        result.update(complete=True, tables=TABLES)
        print('APPROVED_COLUMN_GRANTS_VERIFIED', flush=True)
    except Exception as error:
        result.update(phase=phase, error_type=type(error).__name__)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        if connection is not None:
            connection.close()
        path = Path(__file__).resolve().parents[2] / '.runtime/product-line-reader-grant-result.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    sys.exit(main())
