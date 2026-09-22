"""Preview by default; --apply requires explicit authorization and local credentials."""
import argparse
import getpass
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.provision_purchase_reader import HOST, DATABASE, LOGIN, verify_reader
from app.services.inventory_fields import FIELDS

TABLES = {'YD_JIN_INVENTORY': [f[0] for f in FIELDS], 'T_STK_INVENTORY': ['FID', 'FSTOCKORGID']}


def statements():
    return [f"GRANT SELECT ({','.join('[' + c + ']' for c in columns)}) "
            f"ON OBJECT::[dbo].[{table}] TO [{LOGIN}]" for table, columns in TABLES.items()]


def apply(connection):
    cursor = connection.cursor()
    try:
        cursor.execute('SET LOCK_TIMEOUT 3000')
        cursor.execute('SELECT DB_NAME() AS db, SUSER_ID(%s) AS login_id, USER_ID(%s) AS user_id', (LOGIN, LOGIN))
        identity = cursor.fetchone()
        if identity['db'] != DATABASE or not identity['login_id'] or not identity['user_id']:
            raise RuntimeError('target_or_existing_reader_mismatch')
        for table, columns in TABLES.items():
            cursor.execute('SELECT name FROM sys.columns WHERE object_id=OBJECT_ID(%s)', ('dbo.' + table,))
            if not {column.upper() for column in columns} <= {row['name'].upper() for row in cursor.fetchall()}:
                raise RuntimeError('source_columns_changed')
        for statement in statements():
            cursor.execute(statement)
        cursor.execute(f"EXECUTE AS LOGIN = '{LOGIN}'")
        try:
            verify_reader(cursor)
            for table, columns in TABLES.items():
                cursor.execute(f"SELECT TOP (0) {','.join('[' + c + ']' for c in columns)} FROM [dbo].[{table}]")
                cursor.fetchall()
                for permission in ('INSERT', 'UPDATE', 'DELETE', 'ALTER', 'CONTROL', 'TAKE OWNERSHIP'):
                    cursor.execute("SELECT HAS_PERMS_BY_NAME(%s, 'OBJECT', %s) AS allowed", ('dbo.' + table, permission))
                    if cursor.fetchone()['allowed'] != 0:
                        raise RuntimeError('unexpected_write_permission')
        finally:
            cursor.execute('REVERT')
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(f'{HOST} / {DATABASE} / {LOGIN}')
    if not args.apply:
        print('\n'.join(statements()))
        return 0
    import pymssql
    connection = None
    try:
        username = input('Database administrator username: ').strip()
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            password = getpass.getpass('Password (hidden; not saved): ')
        try:
            connection = pymssql.connect(server=HOST, database=DATABASE, user=username, password=password,
                encryption='require', as_dict=True, autocommit=False, login_timeout=10, timeout=20,
                appname='PMS-Approved-Inventory-Column-Grants')
        finally:
            password = None
        apply(connection)
        print('INVENTORY_COLUMN_GRANTS_VERIFIED')
        return 0
    except Exception as error:
        print('Grant failed: ' + type(error).__name__)
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == '__main__':
    sys.exit(main())
