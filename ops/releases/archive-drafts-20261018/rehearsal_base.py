"""Approved online backup and new-database rehearsal only. No production upgrade."""
import argparse
import datetime
import getpass
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

HERE = Path(__file__).resolve().parent
ROOT = Path('C:/PMS')
CANDIDATE = 'e12d0e5d56ef2897ba4cdf7b0997c3b076d83e3eed7d34e81e0061f4317a65b6'
PACKAGE_SHA = '30c248dad3c45746d326a819b5b1efaee6a0a776bd43ad3107aa40c737dd81cb'
BASELINE = '6ebc2d2e7f5c6772c816e97684cda2d50f91d49d'
PREVIOUS = '2026-10-15-governance-01'
CURRENT = '2026-10-16-form-draft-02'
PREFIX = 'PMS_DRAFT_REHEARSAL_20261018_'
NEW_TABLES = {'pms_form_draft'}
NODES = (('project:archive:draft:manage','草稿管理',22,12),)
ADDED = {}


class GateError(RuntimeError): pass


def check(ok, message):
    if not ok: raise GateError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        default=str, separators=(',', ':')).encode()).hexdigest()


def hashfile(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def read_package(path):
    check(hashfile(path) == PACKAGE_SHA, 'Pinned candidate ZIP mismatch')
    with zipfile.ZipFile(path) as z:
        check(z.testzip() is None, 'ZIP CRC mismatch')
        names = z.namelist()
        check(len(names) == len(set(n.casefold() for n in names)), 'Duplicate Windows ZIP path')
        prefix = 'pms-draft-rehearsal-20261018/'
        files = {}
        for entry in z.infolist():
            n = entry.filename
            check(n.startswith(prefix) and ':' not in n and '\\' not in n
                  and '..' not in PurePosixPath(n).parts and not n.startswith('/'), 'Unsafe ZIP path')
            check((entry.external_attr >> 16) & 0o170000 != 0o120000, 'ZIP symlink refused')
            if not entry.is_dir(): files[n[len(prefix):]] = z.read(n)
        checks = {}
        for line in files['SHA256SUMS'].decode().splitlines():
            h, n = line.split(maxsplit=1)
            check(n not in checks and n in files and hashlib.sha256(files[n]).hexdigest() == h, 'Payload mismatch')
            checks[n] = h
        check(set(checks) == set(files) - {'SHA256SUMS'}, 'Incomplete file manifest')
        manifest = json.loads(files['snapshot.json'])
        code_hashes={name:checks[name] for name in checks if name!='snapshot.json'}
        code_identity=hashlib.sha256(json.dumps(code_hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        check(manifest['snapshot_sha256'] == CANDIDATE == code_identity and manifest['database_revision'] == CURRENT
              and manifest['kind'] == 'isolated-rehearsal-snapshot' and manifest['commit'] is None
              and manifest['baseline_commit'] == BASELINE and 'release.json' not in files
              and manifest['file_count'] == len(code_hashes), 'Wrong snapshot metadata')
    return manifest, files


def extract_package(path, target):
    check(not target.exists(), 'Candidate extraction target exists')
    manifest, files = read_package(path)
    target.mkdir()
    for name, data in files.items():
        p = target / name
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('xb') as stream: stream.write(data)
    return manifest


def guard_host(addresses): check('10.10.1.228' in addresses, 'Wrong application host')


def guard_target(actual, source, expected):
    check(re.fullmatch(re.escape(PREFIX) + '[0-9a-f]{8}', expected) is not None, 'Invalid isolated database name')
    check(actual == expected and actual.casefold() != source.casefold(), 'Wrong actual database target')


def literal(value): return "N'" + str(value).replace("'", "''") + "'"


def valid_folder(folder):
    p = PureWindowsPath(folder)
    check(p.is_absolute() and re.fullmatch('[A-Za-z]:', p.drive) is not None
          and not any(c in folder for c in ('\x00', '\r', '\n', '"', '<', '>', '|', '?', '*')), 'Invalid SQL local directory')
    return p


def restore_plan(source, target, backup, files, data_folder, log_folder):
    guard_target(target, source, target)
    check(files and {'D', 'L'} <= {r['Type'] for r in files}
          and all(r['Type'] in ('D', 'L') for r in files), 'Unsupported or incomplete backup file list')
    check(len({r['LogicalName'] for r in files}) == len(files)
          and len({r['FileId'] for r in files}) == len(files), 'Duplicate backup files')
    valid_folder(str(PureWindowsPath(backup).parent))
    paths, moves = [], []
    for row in files:
        check(isinstance(row['FileId'], int) and row['FileId'] > 0, 'Invalid file ordinal')
        folder = valid_folder(data_folder if row['Type'] == 'D' else log_folder)
        name = target + '_' + str(row['FileId']) + ('.mdf' if row['Type'] == 'D' else '.ldf')
        path = str(folder / name)
        paths.append(path)
        moves.append('MOVE ' + literal(row['LogicalName']) + ' TO ' + literal(path))
    check(len(set(p.casefold() for p in paths)) == len(paths), 'Duplicate restore paths')
    sql = 'RESTORE DATABASE [' + target + '] FROM DISK=' + literal(backup) + ' WITH ' + ', '.join(moves) + ', CHECKSUM,RECOVERY'
    return sql, paths


def ensure_new_target(target, database_names, paths, existing_paths):
    check(target.casefold() not in {n.casefold() for n in database_names}, 'Restore database already exists')
    check(not {p.casefold() for p in paths} & {p.casefold() for p in existing_paths}, 'Restore path already exists')


def guard_backup(receipt):
    check(all(receipt.get(k) is True for k in ('copy_only', 'checksum', 'verifyonly'))
          and receipt.get('backup_sets') == 1 and re.fullmatch('[0-9a-f]{64}', receipt.get('sha256', '')),
          'Backup is not completely verified')


def validate_upgrade(before, after):
    check(before['revision'] == PREVIOUS and after['revision'] == CURRENT, 'Wrong upgrade versions')
    check(set(after['schema']) == set(before['schema']) | NEW_TABLES, 'Unexpected table change')
    for name, schema in before['schema'].items():
        check(after['schema'][name] == schema, 'Existing structure changed: ' + name)
    check(set(after['tables']) == set(before['tables']) | NEW_TABLES, 'Unexpected business table set')
    for name, rows in before['tables'].items():
        check(after['tables'][name] == rows, 'Existing business or permission rows changed: ' + name)
    for name in NEW_TABLES: check(after['tables'][name]['count'] == 0, 'Draft data unexpectedly created')
    check(after['new_values_nonnull'] == 0, 'Historical logs or feedback backfilled')
    old = {r['id']: r for r in before['menus']}
    now = {r['id']: r for r in after['menus']}
    check(len(old) == len(before['menus']) and len(now) == len(after['menus']), 'Duplicate menu identity')
    check(all(now.get(i) == row for i, row in old.items()), 'Existing menu changed')
    added = [r for i, r in now.items() if i not in old]
    expected = {code for code, _, _, _ in NODES} - {r['permission_code'] for r in old.values()}
    check(len(added) == len(expected) and {r['permission_code'] for r in added} == expected, 'Unexpected permission nodes')
    for row in added:
        code, label, parent, sort = next(n for n in NODES if n[0] == row['permission_code'])
        check(row['parent_id'] == parent and row['menu_name'] == label and row['sort'] == sort
              and row['menu_type'] == 'B' and row['status'] == 1 and row['visible'] == 1
              and all(row.get(k) is None for k in ('path', 'component', 'icon')), 'Permission node shape mismatch')


def guard_runtime_permissions(rights):
    check(set(rights)=={'SELECT','INSERT','UPDATE','DELETE'} and all(value==1 for value in rights.values()), 'Existing daily identity lacks draft table permissions; no grants performed')


def safe_receipt(state):
    allowed = {'phase', 'candidate', 'source_head', 'database_revision', 'sql_host', 'database_name',
        'sql_version', 'dependency_versions', 'health_ok', 'protected_configs_unchanged', 'isolated_database',
        'backup', 'verification', 'failed_phase', 'error_type', 'gate_error', 'service_unchanged', 'backend_stopped'}
    return {k: v for k, v in state.items() if k in allowed}


def save(path, value, *, new=False):
    with path.open('x' if new else 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)


def run(command, **kw):
    p = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', **kw)
    check(p.returncode == 0, 'Controlled system command failed')
    return p.stdout.strip()


def runtime_fingerprint(root=ROOT):
    dist = root / 'frontend/dist'
    check((dist / 'index.html').is_file(), 'Live frontend entry missing')
    hashes = {p.relative_to(dist).as_posix(): hashfile(p) for p in dist.rglob('*') if p.is_file()}
    pid = json.loads(run(['powershell.exe', '-NoProfile', '-Command',
        '@((Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess | Sort-Object -Unique) | ConvertTo-Json -Compress']))
    pid = pid if isinstance(pid, list) else [pid]
    check(len(pid) == 1 and isinstance(pid[0], int) and pid[0] > 0, 'Ambiguous live backend process')
    return dict(frontend_hash=digest(hashes), frontend_files=len(hashes), backend_pid=pid[0],
        runtime_manifest_sha256=hashfile(root / 'release.json') if (root / 'release.json').exists() else None)


def raw_query(connection, sql):
    driver = connection.connection.driver_connection
    driver.timeout = 0
    cursor = driver.cursor()
    try:
        cursor.execute(sql)
        sets = []
        while True:
            if cursor.description:
                names = [r[0] for r in cursor.description]
                sets.append([dict(zip(names, row)) for row in cursor.fetchall()])
            if not cursor.nextset(): break
        return sets
    finally: cursor.close()


def file_exists(connection, path):
    sets = raw_query(connection, 'EXEC master.dbo.xp_fileexist ' + literal(path))
    check(sets and len(sets[0]) == 1, 'Cannot check SQL file existence')
    return bool(list(sets[0][0].values())[0])


def capture(connection, *, projected=False):
    from sqlalchemy import inspect, text
    inspector = inspect(connection)
    result = dict(schema={}, tables={}, menus=[], new_values_nonnull=0)
    result['revision'] = connection.execute(text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one()
    for name in sorted(inspector.get_table_names(schema='dbo')):
        excluded = ADDED.get(name, set()) if projected else set()
        cols = [dict(name=c['name'], type=str(c['type'].compile(dialect=connection.dialect)),
            nullable=c['nullable'], default=c.get('default'), identity=c.get('identity'))
            for c in inspector.get_columns(name, schema='dbo') if c['name'] not in excluded]
        indexes = inspector.get_indexes(name, schema='dbo')
        checks = connection.execute(text('SELECT name,definition,is_disabled,is_not_trusted FROM sys.check_constraints '
            "WHERE parent_object_id=OBJECT_ID(:obj) ORDER BY name"), {'obj': 'dbo.' + name}).mappings().all()
        result['schema'][name] = json.loads(json.dumps(dict(columns=cols,
            indexes=sorted(indexes, key=lambda i: i['name']),
            pk=inspector.get_pk_constraint(name, schema='dbo'),
            fks=sorted(inspector.get_foreign_keys(name, schema='dbo'), key=lambda i: i['name']),
            checks=[dict(r) for r in checks]), default=str))
        select_cols = ','.join('[' + c['name'].replace(']', ']]') + ']' for c in cols)
        records = [dict(row) for row in connection.execute(text('SELECT ' + select_cols + ' FROM dbo.[' + name.replace(']', ']]') + ']')).mappings()]
        if name == 'sys_menu': result['menus'] = json.loads(json.dumps(sorted(records, key=lambda r: r['id']), default=str))
        elif name != 'pms_database_revision': result['tables'][name] = dict(count=len(records), sha256=digest(sorted(digest(r) for r in records)))
        if projected and excluded:
            condition = ' OR '.join('[' + n + '] IS NOT NULL' for n in sorted(excluded))
            result['new_values_nonnull'] += connection.execute(text('SELECT COUNT(*) FROM dbo.[' + name + '] WHERE ' + condition)).scalar_one()
    return result


def upgrade_child():
    payload = json.load(sys.stdin)
    guard_host(socket.gethostbyname_ex(socket.gethostname())[2])
    guard_target(payload['database'], payload['source'], payload['database'])
    check(payload['host'] == '10.10.1.230' and payload['source'] == 'PMS', 'Unexpected SQL identity')
    candidate = HERE / 'candidate'
    _, files = read_package(HERE / 'candidate.zip')
    for name, data in files.items(): check(hashfile(candidate / name) == hashlib.sha256(data).hexdigest(), 'Extracted candidate changed')
    # No production settings or worker imports are used in the candidate process.
    for key in list(os.environ):
        if key.startswith(('DB_', 'K3_', 'SSO_', 'OA_', 'PMS_')): os.environ.pop(key)
    os.environ['PMS_CONFIG_FILE'] = str(HERE / 'never-created.env')
    check(not Path(os.environ['PMS_CONFIG_FILE']).exists(), 'Unexpected child config file')
    sys.path.insert(0, str(candidate / 'backend'))
    from app.core import config
    config.settings = config.Settings(_env_file=None, DB_DIALECT='pyodbc', DB_HOST=payload['host'],
        DB_PORT=payload['port'], DB_NAME=payload['database'], DB_DRIVER=payload['driver'],
        DB_USER=quote(payload['username'], safe=''), DB_PASSWORD=quote(payload['password'], safe=''),
        SSO_ENABLED=False, ERP_SYNC_WORKER_ENABLED=False, PMS_RELEASE_MAIL_WORKER_ENABLED=False, K3_URL='')
    from app.core.database import engine
    from sqlalchemy import text
    import app.models.init_db  # Register models only; never call init_db or import main.
    from app.services.form_draft_management_migration import upgrade_draft_management
    from app.services.database_revision import check_database_ready
    try:
        with engine.connect() as c:
            guard_target(c.execute(text('SELECT DB_NAME()')).scalar_one(), payload['source'], payload['database'])
            before = capture(c)
        save(HERE / 'isolated-before.json', before, new=True)
        check(before['revision'] == PREVIOUS, 'Restored database source version mismatch')
        upgrade_draft_management(engine)
        check_database_ready(engine)
        with engine.connect() as c:
            after = capture(c, projected=True)
        validate_upgrade(before, after)
        save(HERE / 'isolated-after.json', after, new=True)
        upgrade_draft_management(engine)
        check_database_ready(engine)
        with engine.connect() as c:
            again = capture(c, projected=True)
        check(after == again, 'Repeated verification changed isolated database')
        save(HERE / 'isolated-verification.json', dict(upgrade_verified=True, startup_structure_verified=True,
            repeated_upgrade_unchanged=True, existing_tables_preserved=len(before['tables']),
            archive_count=before['tables']['pms_project_archive']['count'], default_grants=0,
            release_records=0, real_mssql=True), new=True)
        print('ISOLATED_MSSQL_VERIFIED', flush=True)
    finally: engine.dispose()


class Rehearsal:
    def __init__(self, result_url):
        check(os.name == 'nt' and HERE == ROOT / '.runtime/archive-draft-mssql-rehearsal-20261018-r2', 'Wrong rehearsal directory')
        guard_host(socket.gethostbyname_ex(socket.gethostname())[2])
        self.opener = build_opener(ProxyHandler({}))
        self.result_url = result_url
        check(result_url is None, 'Remote receipt upload is disabled')
        check(not (HERE / 'rehearsal-state.json').exists(), 'Existing rehearsal state; inspect instead of rerunning')
        self.state = dict(phase='initial', candidate=CANDIDATE, backend_stopped=False)
        self.cfg = json.loads((ROOT / 'ops/windows/pms-operations.json').read_text(encoding='utf-8-sig'))
        os.environ['PMS_CONFIG_FILE'] = self.cfg['protectedConfig']
        os.environ['PMS_PURCHASE_CONFIG_FILE'] = self.cfg['purchaseConfig']
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(ROOT / 'backend'))
        from app.core.config import settings, validate_runtime_config
        validate_runtime_config(settings)
        check(settings.PMS_ENV == 'production' and settings.DB_HOST == '10.10.1.230'
              and settings.DB_NAME == 'PMS' and settings.DB_DIALECT == 'pyodbc', 'Wrong production database settings')
        from app.core.database import engine
        from sqlalchemy import text
        self.engine, self.settings, self.text = engine, settings, text
        self.protected = {str(p): hashfile(p) for p in dict.fromkeys([ROOT / 'backend/.env.local',
            ROOT / 'ops/windows/pms-operations.json', Path(self.cfg['protectedConfig']), Path(self.cfg['purchaseConfig']),
            Path('C:/nginx/conf/nginx.conf'), Path('C:/nginx/conf/pms.conf')])}
        self.live_runtime = runtime_fingerprint()
        save(HERE / 'production-runtime-before.json', self.live_runtime, new=True)

    def record(self, phase):
        self.state['phase'] = phase
        save(HERE / 'rehearsal-state.json', self.state)
        public = safe_receipt(self.state)
        if self.result_url:
            try:
                self.opener.open(Request(self.result_url, data=json.dumps(public, ensure_ascii=False).encode(),
                    headers={'Content-Type': 'application/json'}), timeout=10).read()
            except Exception: print('Receipt retained on server', flush=True)
        print('REHEARSAL_PHASE ' + phase, flush=True)

    def verify_live(self):
        check(run(['git.exe', '-C', str(ROOT), 'rev-parse', 'HEAD']) == BASELINE, 'Live source changed')
        check(run(['git.exe', '-C', str(ROOT), 'status', '--porcelain']) in ('','?? release.json'), 'Unexpected live source changes')
        manifest=json.loads((ROOT/'release.json').read_text(encoding='utf-8'))
        check(manifest['version']=='v1.0.2' and manifest['commit']==BASELINE and manifest['database_revision']==PREVIOUS,'Live release identity changed')
        check(all(hashfile(p) == h for p, h in self.protected.items()), 'Protected configuration changed')
        check(runtime_fingerprint() == self.live_runtime, 'Live process or frontend/manifest changed')
        with self.opener.open('http://127.0.0.1:8000/api/health', timeout=8) as response:
            check(json.load(response).get('status') == 'ok', 'Live health failed')
        with self.engine.connect() as c:
            check(c.execute(self.text('SELECT DB_NAME()')).scalar_one() == 'PMS', 'Wrong live database')
            check(c.execute(self.text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one() == PREVIOUS, 'Live revision changed')
        self.state.update(health_ok=True, protected_configs_unchanged=True, source_head=BASELINE,
                          database_revision=PREVIOUS, sql_host=self.settings.DB_HOST, database_name='PMS')

    def preflight(self):
        self.verify_live()
        read_package(HERE / 'candidate.zip')
        import sqlalchemy, pyodbc
        check(sqlalchemy.__version__ == '2.0.37' and pyodbc.version == '5.2.0', 'Server dependency mismatch')
        with self.engine.connect() as c:
            self.state['sql_version'] = str(c.execute(self.text("SELECT SERVERPROPERTY('ProductVersion')")).scalar_one())
            check(self.state['sql_version'].startswith('14.'), 'Expected SQL Server 2017')
            activity = dict(erp=c.execute(self.text("SELECT COUNT(*) FROM erp_sync_task WHERE status IN ('queued','running','review')")).scalar_one(),
                export=c.execute(self.text("SELECT COUNT(*) FROM pms_report_export_job WHERE status IN ('queued','running')")).scalar_one())
            save(HERE / 'preflight-activity.json', activity, new=True)
        self.state['dependency_versions'] = dict(sqlalchemy=sqlalchemy.__version__, pyodbc=pyodbc.version)
        self.record('preflight-verified')

    def backup_restore(self, username, password):
        from sqlalchemy import create_engine
        from sqlalchemy.engine import URL
        check(username and password and username.casefold() != self.settings.DB_USER.casefold(), 'Separate SQL identity required')
        url = URL.create('mssql+pyodbc', username=username, password=password, host=self.settings.DB_HOST,
            port=self.settings.DB_PORT, database='master', query={'driver': self.settings.DB_DRIVER,
                'Encrypt': 'no', 'TrustServerCertificate': 'yes'})
        admin = create_engine(url, isolation_level='AUTOCOMMIT', connect_args={'timeout': 10})
        try:
            with admin.connect() as c:
                check(c.execute(self.text('SELECT DB_NAME()')).scalar_one() == 'master', 'Wrong administration context')
                check(c.execute(self.text("SELECT CASE WHEN IS_SRVROLEMEMBER('sysadmin')=1 THEN 1 ELSE 0 END")).scalar_one() == 1,
                      'Rehearsal requires an existing authorized SQL backup/restore administrator')
                folder = c.execute(self.text("SELECT CONVERT(nvarchar(4000),SERVERPROPERTY('InstanceDefaultBackupPath'))")).scalar_one_or_none()
                if not folder:
                    sets = raw_query(c, "EXEC master.dbo.xp_instance_regread N'HKEY_LOCAL_MACHINE', N'Software\\Microsoft\\MSSQLServer\\MSSQLServer', N'BackupDirectory'")
                    check(sets and sets[0], 'Backup directory is unavailable')
                    folder = list(sets[0][0].values())[1]
                folder = str(valid_folder(folder))
                size = c.execute(self.text("SELECT SUM(CONVERT(bigint,size))*8192 FROM sys.master_files WHERE database_id=DB_ID(N'PMS')")).scalar_one()
                drives = raw_query(c, 'EXEC master.dbo.xp_fixeddrives')[0]
                available = {str(list(row.values())[0]).upper(): int(list(row.values())[1]) * 1048576 for row in drives}
                data_folder = c.execute(self.text("SELECT CONVERT(nvarchar(4000),SERVERPROPERTY('InstanceDefaultDataPath'))")).scalar_one()
                log_folder = c.execute(self.text("SELECT CONVERT(nvarchar(4000),SERVERPROPERTY('InstanceDefaultLogPath'))")).scalar_one()
                for directory in (folder, data_folder, log_folder):
                    drive = valid_folder(directory).drive[0].upper()
                    check(available.get(drive, 0) > size * 3 + 1073741824, 'Insufficient SQL disk space for protected rehearsal')
                target = PREFIX + uuid.uuid4().hex[:8]
                backup = str(PureWindowsPath(folder) / (target + '.bak'))
                check(not file_exists(c, backup), 'Backup file already exists')
                self.state['isolated_database'] = target
                self.state['backup'] = dict(path_on_sql_server=backup)
                self.record('backup-running')
                raw_query(c, 'BACKUP DATABASE [PMS] TO DISK=' + literal(backup) + ' WITH COPY_ONLY,CHECKSUM')
                self.record('backup-verify-running')
                raw_query(c, 'RESTORE VERIFYONLY FROM DISK=' + literal(backup) + ' WITH CHECKSUM')
                headers = raw_query(c, 'RESTORE HEADERONLY FROM DISK=' + literal(backup))[0]
                check(len(headers) == 1 and headers[0]['DatabaseName'] == 'PMS' and headers[0]['BackupType'] == 1
                      and headers[0]['IsCopyOnly'] and headers[0]['HasBackupChecksums']
                      and not headers[0]['IsDamaged'] and headers[0]['BackupFinishDate'] is not None, 'Backup header verification failed')
                # Hash inside SQL Server: backup bytes never leave the server.
                sha = c.execute(self.text("SELECT LOWER(CONVERT(varchar(64),HASHBYTES('SHA2_256',BulkColumn),2)) FROM OPENROWSET(BULK "
                    + literal(backup) + ', SINGLE_BLOB) AS backup_bytes')).scalar_one()
                self.state['backup'].update(copy_only=True, checksum=True, verifyonly=True, backup_sets=1,
                    sha256=sha, finished=str(headers[0]['BackupFinishDate']),
                    first_lsn=str(headers[0]['FirstLSN']), last_lsn=str(headers[0]['LastLSN']))
                guard_backup(self.state['backup'])
                self.record('backup-verified')
                files = raw_query(c, 'RESTORE FILELISTONLY FROM DISK=' + literal(backup))[0]
                sql, paths = restore_plan('PMS', target, backup, files, data_folder, log_folder)
                names = c.execute(self.text('SELECT name FROM sys.databases')).scalars().all()
                used_paths = c.execute(self.text('SELECT physical_name FROM sys.master_files')).scalars().all()
                used_paths += [p for p in paths if file_exists(c, p)]
                ensure_new_target(target, names, paths, used_paths)
                save(HERE / 'restore-plan.json', dict(database=target, paths=paths, sql=sql), new=True)
                self.record('isolated-restore-running')
                raw_query(c, sql)
                check(c.execute(self.text('SELECT state_desc FROM sys.databases WHERE name=:name'), {'name': target}).scalar_one() == 'ONLINE',
                      'Restored isolated database is not online')
                self.record('isolated-restored')
            return target
        finally: admin.dispose()

    def verify_daily_access(self,target):
        from sqlalchemy import create_engine
        # Reuse the existing runtime identity without displaying or persisting it.
        isolated=create_engine(self.engine.url.set(database=target),connect_args={'timeout':10})
        try:
            with isolated.connect() as c:
                guard_target(c.execute(self.text('SELECT DB_NAME()')).scalar_one(),'PMS',target)
                rights={action:c.execute(self.text("SELECT HAS_PERMS_BY_NAME('dbo.pms_form_draft','OBJECT',:action)"),{'action':action}).scalar_one() for action in ('SELECT','INSERT','UPDATE','DELETE')}
                guard_runtime_permissions(rights)
            self.state['verification']['daily_identity_permissions_verified']=True
        finally:isolated.dispose()

    def execute(self):
        self.preflight()
        extract_package(HERE / 'candidate.zip', HERE / 'candidate')
        self.record('awaiting-local-sql-identity')
        username = getpass.getpass('SQL backup/restore administrator username (hidden): ').strip()
        password = getpass.getpass('SQL backup/restore password (hidden): ')
        try:
            self.verify_live()
            target = self.backup_restore(username, password)
            self.verify_live()
            self.record('isolated-upgrade-running')
            payload = dict(database=target, source='PMS', host=self.settings.DB_HOST, port=self.settings.DB_PORT,
                driver=self.settings.DB_DRIVER, username=username, password=password)
            result = subprocess.run([sys.executable, '-B', str(HERE / 'server_rehearsal.py'), '--upgrade-child'],
                input=json.dumps(payload), text=True, encoding='utf-8', capture_output=True)
            payload.clear()
            check(result.returncode == 0, 'Isolated upgrade process stopped; inspect server receipt')
            self.state['verification'] = json.loads((HERE / 'isolated-verification.json').read_text(encoding='utf-8'))
            self.verify_daily_access(target)
            self.verify_live()
            self.state['service_unchanged'] = True
            self.record('complete')
        finally:
            username = password = None
            self.engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--result-url')
    parser.add_argument('--upgrade-child', action='store_true')
    args = parser.parse_args()
    if args.upgrade_child:
        try: upgrade_child()
        except Exception as error:
            save(HERE / 'isolated-error.json', {'error_type': type(error).__name__,
                'gate_error': str(error) if isinstance(error, GateError) else None})
            print('ISOLATED_CHILD_STOPPED ' + type(error).__name__, flush=True)
            raise SystemExit(1)
        return
    worker = None
    try:
        worker = Rehearsal(args.result_url)
        worker.execute()
    except Exception as error:
        if worker is not None:
            worker.state.update(failed_phase=worker.state['phase'], error_type=type(error).__name__)
            if isinstance(error, GateError): worker.state['gate_error'] = str(error)
            worker.record('failed')
        print('REHEARSAL_STOPPED ' + type(error).__name__ + '; no automatic retry or restore', flush=True)
        raise SystemExit(1)


if __name__ == '__main__': main()
