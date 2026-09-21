"""Interactive, fixed-target provisioning. Never persist admin credentials.

Only creates a NEW principal. Existing identities/configuration stop the run.
No business data is written; permission checks never execute test DML.
"""
import getpass
import json
import os
from pathlib import Path
import secrets
import string
import warnings

HOST = '10.10.1.248'
DATABASE = 'AIS20231211221516'
LOGIN = 'pms_purchase_reader'
ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / '.runtime/private/purchase-report.env'
RESULT = ROOT / '.runtime/purchase-reader-provision-result.json'

# Deliberately excludes prices, tax amounts, credentials and arbitrary tables.
TABLES = {
    'T_PUR_REQUISITION': 'FID FBILLNO FDOCUMENTSTATUS FAPPLICATIONDATE FCANCELSTATUS FCLOSESTATUS FAPPLICATIONORGID FAPPLICATIONDEPTID',
    'T_PUR_REQENTRY': 'FENTRYID FID FSEQ FMATERIALID FUNITID FBASEUNITID FREQQTY FAPPROVEQTY FBASEREQQTY FBASEUNITQTY FMRPCLOSESTATUS FMRPTERMINATESTATUS FISSPLITCANCEL F_TWBJ_ASSISTANT_83G F_TWBJ_TEXT_83G',
    'T_PUR_REQENTRY_R': 'FENTRYID FID FORDERQTY FORDERBASEQTY FORDERJOINQTY FORDERJNBASEQTY FSTOCKQTY FBASESTOCKQTY FSRCREQSPLITENTRYID FSRCREQMERGEENTRYIDS',
    'T_PUR_POORDER': 'FID FBILLNO FDATE FDOCUMENTSTATUS FCANCELSTATUS FCLOSESTATUS FSUPPLIERID FPURCHASEORGID',
    'T_PUR_POORDERENTRY': 'FENTRYID FID FSEQ FMATERIALID FUNITID FBASEUNITID FQTY FBASEUNITQTY FSTOCKUNITID FSTOCKQTY FSTOCKBASEQTY FMRPCLOSESTATUS FMRPTERMINATESTATUS FTERMINATESTATUS F_TWBJ_ASSISTANT_TZK F_TWBJ_TEXT_RE5',
    'T_PUR_POORDERENTRY_R': 'FENTRYID FID FSRCBILLTYPEID FSRCBILLNO FSRCROWID FSTOCKINQTY FBASESTOCKINQTY FSTOCKRETQTY FBASESTOCKRETQTY FMRBQTY FBASEMRBQTY',
    'T_STK_INSTOCK': 'FID FBILLNO FDATE FDOCUMENTSTATUS FCANCELSTATUS FSUPPLIERID FSTOCKORGID',
    'T_STK_INSTOCKENTRY': 'FENTRYID FID FSEQ FMATERIALID FUNITID FBASEUNITID FREALQTY FBASEUNITQTY FPOORDERENTRYID FPOORDERNO FSRCBILLTYPEID FSRCBILLNO FSRCROWID FSRCENTRYID FPROJECTNO FRETURNJOINQTY FBASERETURNJOINQTY',
    'T_STK_INSTOCKENTRY_F': 'FENTRYID FID FREMAININSTOCKQTY FREMAININSTOCKBASEQTY FREMAININSTOCKUNITID',
    'T_PUR_RECEIVE': 'FID FBILLNO FDATE FDOCUMENTSTATUS FCANCELSTATUS FSUPPLIERID',
    'T_PUR_RECEIVEENTRY': 'FENTRYID FID FSEQ FMATERIALID FUNITID FBASEUNITID FACTRECEIVEQTY FBASEUNITQTY FPOORDERENTRYID FSRCID FSRCFORMID FSRCENTRYID FSRCBILLNO',
    'T_PUR_MRB': 'FID FBILLNO FDATE FDOCUMENTSTATUS FCANCELSTATUS FSUPPLIERID',
    'T_PUR_MRBENTRY': 'FENTRYID FID FSEQ FMATERIALID FUNITID FBASEUNITID FRMREALQTY FBASEUNITQTY FPOORDERENTRYID FSRCBILLTYPEID FSRCFID FSRCROWID FSRCBILLNO',
    'T_BAS_ASSISTANTDATAENTRY': 'FENTRYID FID FNUMBER FFORBIDSTATUS',
    'T_BAS_ASSISTANTDATAENTRY_L': 'FENTRYID FLOCALEID FDATAVALUE',
    'T_BD_MATERIAL': 'FMATERIALID FNUMBER FMASTERID',
    'T_BD_MATERIAL_L': 'FMATERIALID FLOCALEID FNAME FSPECIFICATION',
    'T_BD_UNIT_L': 'FUNITID FLOCALEID FNAME',
    'T_BD_SUPPLIER_L': 'FSUPPLIERID FLOCALEID FNAME',
}
for _table in ('T_PUR_POORDERENTRY_LK', 'T_STK_INSTOCKENTRY_LK', 'T_PUR_RECEIVEENTRY_LK', 'T_PUR_MRBENTRY_LK'):
    TABLES[_table] = 'FENTRYID FLINKID FSTABLEID FSTABLENAME FSBILLID FSID FBASEUNITQTY FBASEUNITQTYOLD'
TABLES['T_STK_INSTOCKENTRY_LK'] += ' FREMAININSTOCKBASEQTY FREMAININSTOCKBASEQTYOLD'


def grant_statements():
    return [f"GRANT SELECT ({','.join('[' + c + ']' for c in fields.split())}) "
            f"ON OBJECT::[dbo].[{table}] TO [{LOGIN}]" for table, fields in TABLES.items()]


def check_absent(row):
    if row['login_exists'] or row['user_exists']:
        raise RuntimeError('existing_principal')


def new_password():
    return 'Aa7!' + ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(44))


def write_private_config(path, password):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(f'PURCHASE_DB_HOST={HOST}\nPURCHASE_DB_NAME={DATABASE}\n'
                     f'PURCHASE_DB_USER={LOGIN}\nPURCHASE_DB_PASSWORD={password}\n')
        stream.flush()
        os.fsync(stream.fileno())


def check_permissions(database_permissions, server_permissions):
    db_allowed = {'CONNECT', 'VIEW ANY COLUMN ENCRYPTION KEY DEFINITION', 'VIEW ANY COLUMN MASTER KEY DEFINITION'}
    server_allowed = {'CONNECT SQL', 'VIEW ANY DATABASE'}
    if set(database_permissions) - db_allowed or set(server_permissions) - server_allowed:
        raise RuntimeError('unexpected_effective_permissions')


def verify_reader(cursor):
    cursor.execute('SELECT DB_NAME() AS db, SUSER_SNAME() AS login_name')
    identity = cursor.fetchone()
    if identity['db'] != DATABASE or identity['login_name'] != LOGIN:
        raise RuntimeError('wrong_identity')
    cursor.execute("SELECT permission_name FROM sys.fn_my_permissions(NULL, 'DATABASE')")
    db_permissions = [row['permission_name'] for row in cursor.fetchall()]
    cursor.execute("SELECT permission_name FROM sys.fn_my_permissions(NULL, 'SERVER')")
    check_permissions(db_permissions, [row['permission_name'] for row in cursor.fetchall()])
    for table, fields in TABLES.items():
        names = ','.join('[' + field + ']' for field in fields.split())
        cursor.execute(f'SELECT TOP (0) {names} FROM [dbo].[{table}]')
        cursor.fetchall()
        for permission in ('INSERT', 'UPDATE', 'DELETE', 'ALTER', 'CONTROL', 'TAKE OWNERSHIP'):
            cursor.execute("SELECT HAS_PERMS_BY_NAME(%s, 'OBJECT', %s) AS allowed", ('dbo.' + table, permission))
            if cursor.fetchone()['allowed'] != 0:
                raise RuntimeError('write_or_ownership_permission')


def main():
    import pymssql
    phase, committed, commit_attempted = 'preflight', False, False
    connection = None
    created_config = False
    admin_password = None
    report_password = None
    result = dict(host=HOST, database=DATABASE, login=LOGIN, complete=False)
    try:
        if CONFIG.exists() or CONFIG.is_symlink():
            raise RuntimeError('existing_private_configuration')
        print(f'Target: {HOST} / {DATABASE}; NEW reader: {LOGIN}', flush=True)
        username = input('Database administrator username: ').strip()
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            admin_password = getpass.getpass('Administrator password (hidden, never saved): ')
        phase = 'admin_connection'
        connection = pymssql.connect(server=HOST, database=DATABASE, user=username, password=admin_password,
            encryption='require', as_dict=True, autocommit=False, login_timeout=10, timeout=30,
            appname='PMS-Purchase-Reader-Provision')
        admin_password = None
        cursor = connection.cursor()
        cursor.execute('SET LOCK_TIMEOUT 3000')
        cursor.execute('SELECT DB_NAME() AS name, IS_SRVROLEMEMBER(\'sysadmin\') AS administrator')
        identity = cursor.fetchone()
        if identity['name'] != DATABASE or identity['administrator'] != 1:
            raise RuntimeError('target_or_admin_validation')
        cursor.execute("SELECT CASE WHEN SUSER_ID(%s) IS NULL THEN 0 ELSE 1 END AS login_exists, "
                       "CASE WHEN USER_ID(%s) IS NULL THEN 0 ELSE 1 END AS user_exists", (LOGIN, LOGIN))
        check_absent(cursor.fetchone())
        # Refuse inherited public access to business tables rather than altering
        # a shared role used by Kingdee and other applications.
        cursor.execute("""SELECT TOP (1) p.permission_name FROM sys.database_permissions p
            JOIN sys.objects o ON o.object_id=p.major_id
            WHERE p.grantee_principal_id=DATABASE_PRINCIPAL_ID('public')
              AND p.state IN ('G','W') AND o.is_ms_shipped=0
              AND p.permission_name NOT IN ('INSERT','UPDATE','DELETE','EXECUTE')""")
        if cursor.fetchone():
            raise RuntimeError('public_business_permissions_require_review')
        for table, fields in TABLES.items():
            cursor.execute('SELECT c.name FROM sys.columns c WHERE c.object_id=OBJECT_ID(%s)', ('dbo.' + table,))
            actual = {r['name'].upper() for r in cursor.fetchall()}
            if not set(fields.split()) <= actual:
                raise RuntimeError('schema_diff_' + table)
        phase = 'private_config'
        CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if CONFIG.parent.is_symlink() or CONFIG.parent.stat().st_mode & 0o077:
            raise RuntimeError('private_directory_permissions')
        report_password = new_password()
        write_private_config(CONFIG, report_password)
        created_config = True
        phase = 'create_and_grant'
        # Driver-bound input; never emit this statement or a raw driver error.
        cursor.execute("DECLARE @pwd nvarchar(128)=%s; DECLARE @sql nvarchar(max)="
                       "N'CREATE LOGIN [pms_purchase_reader] WITH PASSWORD = ' + QUOTENAME(@pwd, '''') + "
                       "N', CHECK_POLICY=ON, CHECK_EXPIRATION=OFF, DEFAULT_DATABASE=[AIS20231211221516]'; EXEC(@sql)",
                       (report_password,))
        cursor.execute(f'CREATE USER [{LOGIN}] FOR LOGIN [{LOGIN}] WITH DEFAULT_SCHEMA=[dbo]')
        cursor.execute(f'GRANT CONNECT TO [{LOGIN}]')
        cursor.execute(f'DENY INSERT, UPDATE, DELETE, EXECUTE TO [{LOGIN}]')
        for sql in grant_statements():
            cursor.execute(sql)
        phase = 'transaction_permission_audit'
        cursor.execute(f"EXECUTE AS LOGIN = '{LOGIN}'")
        try:
            verify_reader(cursor)
        finally:
            cursor.execute('REVERT')
        phase = 'commit'
        commit_attempted = True
        connection.commit()
        committed = True
        phase = 'reader_login_verification'
        reader = pymssql.connect(server=HOST, database=DATABASE, user=LOGIN, password=report_password,
            encryption='require', as_dict=True, read_only=True, login_timeout=10, timeout=20,
            appname='PMS-Purchase-Reader-Verify')
        try:
            verify_reader(reader.cursor())
            reader.rollback()
        finally:
            reader.close()
        result.update(complete=True, phase='verified', committed=True, table_count=len(TABLES))
        print('READER_CREATED_AND_VERIFIED', flush=True)
    except Exception as error:
        # No tracebacks or raw SQL messages: driver errors can contain secrets.
        result.update(phase=phase, committed=committed, commit_attempted=commit_attempted,
                      error_type=type(error).__name__)
        known_reasons = {'existing_principal', 'existing_private_configuration',
            'target_or_admin_validation', 'public_business_permissions_require_review',
            'private_directory_permissions', 'wrong_identity', 'unexpected_effective_permissions',
            'write_or_ownership_permission'} | {'schema_diff_' + table for table in TABLES}
        if isinstance(error, RuntimeError) and str(error) in known_reasons:
            result['reason'] = str(error)
        print('STOPPED at ' + phase + '; safe diagnostic saved.', flush=True)
    finally:
        admin_password = report_password = None
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                result['rollback_uncertain'] = True
            connection.close()
        # Retain the generated credential if COMMIT outcome is uncertain.
        if created_config and not commit_attempted and not result.get('rollback_uncertain'):
            CONFIG.unlink(missing_ok=True)
        RESULT.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(RESULT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print('Result: ' + str(RESULT), flush=True)


if __name__ == '__main__':
    main()
    input('Press Enter to close...')
