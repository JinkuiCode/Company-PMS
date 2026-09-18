"""Archive queries filter and sort before paging, without per-row user queries."""
import os
import sys
import tempfile
import datetime
from time import perf_counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DB_DIALECT'] = 'sqlite'
os.environ['SQLITE_DB_PATH'] = str(Path(tempfile.mkdtemp()) / 'pagination.db')

from sqlalchemy import event
from app.core.database import Base, engine, SessionLocal
from app.models import project, rbac
from app.services.project import get_archive_list, get_project_list
from app.models.user import SysUser

Base.metadata.create_all(engine)
with SessionLocal() as db:
    user = SysUser(username='pagination-test', real_name='查询测试人', password_hash='not-a-login')
    db.add(user)
    db.flush()
    db.add_all([project.PmsProjectArchive(
        project_code=f'PAGE-{i:04}', project_name='long name ' * 10,
        customer='target' if i % 2 == 0 else 'other',
        product_category=1, is_enabled=1, created_by=user.id, manager_id=user.id,
        plan_start_date=datetime.datetime(2026, 9, 18, 12),
    ) for i in range(1040)])
    db.commit()
    statements = []
    def count_query(*args):
        statements.append(args[2])
    event.listen(engine, 'before_cursor_execute', count_query)
    started = perf_counter()
    first = get_archive_list(db, page_size=15)
    print(f'1040 archives, page 15: {len(statements)} SQL statements, {(perf_counter() - started) * 1000:.1f} ms (local SQLite)')
    assert len(first['items']) == 15 and first['total'] == 1040
    assert len(statements) <= 10, f'Query count grows per row: {len(statements)}'
    result = get_archive_list(db, page=2, page_size=15,
        filters='[{"field":"customer","operator":"equals","value":"target"}]',
        sort='[{"colId":"project_code","sort":"asc"}]')
    assert result['total'] == 520
    assert [r.project_code for r in result['items']] == [f'PAGE-{i:04}' for i in range(30, 60, 2)]
    assert get_archive_list(db, keyword='target')['total'] == 520
    assert get_archive_list(db, keyword='PAGE_%')['total'] == 0
    assert get_archive_list(db, filters='[{"field":"created_by_name","operator":"equals","value":"查询测试人"}]')['total'] == 1040
    assert get_archive_list(db, filters='[{"field":"plan_start_date","operator":"equals","value":"2026-09-18"}]')['total'] == 1040
    assert get_archive_list(db, filters='[{"field":"plan_start_date","operator":"after","value":"2026-09-18"}]')['total'] == 0
    assert get_archive_list(db, scope_context={'data_scope': 1, 'user_id': user.id + 1, 'product_category_ids': None})['total'] == 0
    assert get_archive_list(db, allowed_category_ids=[2])['total'] == 0
    assert get_archive_list(db, archive_id=first['items'][0].id)['total'] == 1
    from fastapi import HTTPException
    try:
        get_archive_list(db, filters='[{"field":"password","operator":"equals","value":"x"}]')
        raise AssertionError('Unknown query field must not be accepted')
    except HTTPException as exc:
        assert exc.status_code == 422
    db.add_all([project.PmsProject(project_code=f'PROGRESS-{i:04}', project_name='test',
        dept_id=1, pm_id=user.id) for i in range(1040)])
    db.commit()
    assert len(get_project_list(db)['items']) == 15
    complete = get_project_list(db, all_rows=True)
    assert complete['total'] == 1040 and len(complete['items']) == 1040
    assert get_project_list(db, all_rows=True, dept_id=2)['total'] == 0
    from app.models.operation_log import SysOperationLog
    from app.services.operation_log import get_operation_logs
    db.add_all([SysOperationLog(module='test', action='test', entity_type='test',
        entity_name='older target' if i == 0 else 'other', summary='test') for i in range(40)])
    db.commit()
    logs = get_operation_logs(db, filters='[{"field":"entity_name","operator":"contains","value":"target"}]')
    assert logs['total'] == 1 and len(logs['items']) == 1
print('archive pagination contract passed')
