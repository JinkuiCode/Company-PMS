"""Bounded synchronous exports of scoped business list data, never ERP jobs."""
import heapq
import json
from contextlib import ExitStack
from decimal import Decimal
import os
import tempfile
from pathlib import Path
from fastapi import HTTPException
from app.models.dict import SysDict, SysDictItem
from app.models.product_line import SysProductLine
from app.services import project
from app.services.authorization import enforce_permission
from app.services.field_policy import get_effective_field_policies, MODULE_PROJECT_PROGRESS
from app.services.list_query import invalid_query, query_items
from app.services.operation_log import record_operation_log
from app.services.report_workbook import ReportWorkbook
from app.services.business_list_query import compile_business_query, business_sort_key
from app.services.report_filters import matches_filters

BATCH_SIZE = 500
NAMES = {'archive': '项目档案', 'project': '项目列表', 'task': '项目进度'}


def enum_labels(db, code):
    return {int(value): label for value, label in db.query(SysDictItem.item_value, SysDictItem.item_label)
            .join(SysDict, SysDict.id == SysDictItem.dict_id).filter(SysDict.dict_code == code).all()}


def _kind(value_type, enum_code=None):
    if enum_code:
        return 'enum_number'
    return 'number' if value_type in ('number', 'progress', 'percent') else 'date' if value_type in ('date', 'datetime') else 'enum_text' if value_type in ('select', 'user', 'department') else 'text'


def export_fields(db, kind):
    if kind == 'archive':
        fields = {}
        for item in project.get_archive_field_metadata(db)['items']:
            if not item['visible'] or not item['list_available']:
                continue
            field = 'manager_name' if item['field_key'] == 'manager_id' else item['field_key']
            fields[field] = dict(label=item['label'], kind=_kind(item['value_type'], item.get('enum_code')),
                                 labels=enum_labels(db, item['enum_code']) if item.get('enum_code') else {})
        fields.update(status=dict(label='状态', kind='enum_number', labels=enum_labels(db, 'archive_status')),
                      is_enabled=dict(label='启用状态', kind='enum_number', labels={1: '启用', 0: '禁用'}))
        if 'product_line_id' in fields:
            fields['product_line_id']['kind'] = 'enum_number'
            fields['product_line_id']['labels'] = {id_: name for id_, name in db.query(SysProductLine.id, SysProductLine.display_name)}
        from app.services.erp_queue import STATUS_LABELS
        for key, labels in {'erp_sync_status': {**STATUS_LABELS, 'pending': '同步中', 'historical': '金蝶历史档案'},
                            'data_origin': {'pms': 'PMS新建', 'kingdee_initial': '金蝶期初', 'erp': '金蝶历史档案', 'offline_initial': '线下期初'},
                            'erp_sync_policy': {'manual': '仅手动同步', 'auto': '自动同步', 'conditional': '条件同步'}}.items():
            if key in fields:
                fields[key].update(kind='enum_text', labels=labels)
        if 'erp_sync_status' in fields:
            fields['erp_sync_status']['labels'].update({None: '未同步', '': '未同步'})
            fields['erp_sync_state'] = {**fields['erp_sync_status'], 'label': '同步状态'}
        return fields
    if kind == 'task':
        return {key: dict(label=label, kind=type_, labels=enum_labels(db, 'task_status') if key == 'status' else {})
                for key, label, type_ in (
                    ('task_name', '任务名称', 'text'), ('assignee_name', '负责人', 'enum_text'),
                    ('status', '状态', 'enum_number'), ('progress', '进度%', 'number'), ('sort', '排序', 'number'),
                    ('start_date', '开始日期', 'date'), ('due_date', '截止日期', 'date'))}
    policies = {item['field_key']: item for item in get_effective_field_policies(db, MODULE_PROJECT_PROGRESS)['items']}
    fields = {}
    fixed = [('project_code', '项目编号', 'text', 'project_code'), ('project_name', '项目名称', 'text', 'project_name'),
             ('status', '节点', 'enum_number', 'node_status'), ('pm_name', '负责人', 'enum_text', 'pm_id'),
             ('dept_name', '所属部门', 'enum_text', 'dept_id'), ('budget', '预算', 'number', 'budget'),
             ('start_date', '立项日期', 'date', 'project_start_date'), ('end_date', '原计划发货', 'date', 'original_planned_ship_date'),
             ('total_progress', '总进度', 'number', None), ('task_count', '任务数', 'number', None)]
    for key, label, type_, policy in fixed:
        if policy is None or policies[policy]['visible']:
            fields[key] = dict(label=label, kind=type_, labels=enum_labels(db, 'project_status') if key == 'status' else {})
    for item in project.get_project_sheet_field_metadata(db)['fields']:
        if not item['list_available']:
            continue
        key = item['key']
        spec = dict(label=item['label'], kind=_kind(item['value_type'], item.get('enum_code')),
                    labels=enum_labels(db, item['enum_code']) if item.get('enum_code') else {})
        fields['sheet:' + key] = spec
        if key not in fields:
            fields[key] = spec
    return fields


def _parameters(kind, parameters):
    allowed = {'archive': {'keyword', 'status', 'product_category', 'enabled', 'archive_id'},
               'project': {'dept_id', 'status'}, 'task': set()}[kind]
    if not isinstance(parameters, dict) or set(parameters) - allowed:
        raise invalid_query()
    result = dict(parameters)
    if kind == 'archive':
        enabled = result.pop('enabled', True)
        if enabled in ('true', 'false', 'all'):
            enabled = {'true': True, 'false': False, 'all': None}[enabled]
        if enabled is not None and type(enabled) is not bool:
            raise invalid_query()
        result['enabled'] = enabled
    for key, value in result.items():
        if key == 'keyword':
            if value is not None and (not isinstance(value, str) or len(value) > 256):
                raise invalid_query()
        elif key != 'enabled' and value is not None and (type(value) is not int or value < 0):
            raise invalid_query()
    return result


def _normalized_record(row, fields):
    record = {key: row.get(key) for key in fields}
    for key, spec in fields.items():
        value = record[key]
        if isinstance(value, str) and not value.strip():
            record[key] = None
        elif spec['kind'] == 'date' and isinstance(value, str):
            record[key] = value[:10]
    return record


def _row_batches(db, kind, parameters, scope, fields, filters, column_filters, project_id, conditions):
    sheet_keys = [key[6:] for key in fields if key.startswith('sheet:')]
    def fetch(before_id, upper_id):
        common = dict(page_size=BATCH_SIZE, scope_context=scope, export_scan=True,
                      before_id=before_id, upper_id=upper_id, **parameters)
        if kind == 'archive':
            return project.get_archive_list(db, **common, filters=filters, column_filters=column_filters)['items']
        if kind == 'task':
            return project.get_tasks(db, project_id, **common)
        return project.get_project_list(db, **common, sheet_field_keys=sheet_keys)['items']
    before_id = upper_id = None
    while True:
        items = fetch(before_id, upper_id)
        if not items:
            break
        # The first descending PK batch defines the scan ceiling, not a DB snapshot.
        if upper_id is None:
            upper_id = items[0].id
        before_id = items[-1].id
        rows = []
        for item in items:
            row = item.model_dump()
            sheet_fields = row.pop('sheet_fields', {})
            for key, value in sheet_fields.items():
                row['sheet:' + key] = value
                if key not in row:
                    row[key] = value
            if kind == 'archive':
                row['erp_sync_state'] = row.get('erp_sync_status') or ('historical' if row.get('data_origin') == 'kingdee_initial' else 'success' if row.get('erp_synced') else '')
            # Query getters override colliding keys; grid/export columns do not.
            query_record = _normalized_record({**row, **sheet_fields}, fields)
            if conditions is None or matches_filters(query_record, conditions):
                rows.append({**_normalized_record(row, fields), '_source_id': item.id})
        yield rows
        if len(items) < BATCH_SIZE:
            break


def _read_run(handle):
    for line in handle:
        yield json.loads(line)


def _validate_archive_query_shapes(filters, column_filters):
    from app.services.list_query import archive_columns
    fields = (set(archive_columns()) - {'id'}) | {'keyword'}
    def condition(item):
        if (not isinstance(item, dict) or set(item) - {'id', 'field', 'schemaVersion', 'operator', 'value', 'valueEnd'} or
                type(item.get('schemaVersion')) is not int or item['schemaVersion'] != 2 or
                not isinstance(item.get('field'), str) or item['field'] not in fields or
                ('id' in item and type(item['id']) is not int)):
            raise invalid_query()
    for item in query_items(filters):
        condition(item)
    for item in query_items(column_filters):
        if not isinstance(item.get('field'), str) or item['field'] not in fields - {'keyword'}:
            raise invalid_query()
        if item.get('mode') == 'condition':
            if set(item) != {'field', 'mode', 'condition'}:
                raise invalid_query()
            condition(item['condition'])
        elif item.get('mode') == 'values':
            if set(item) != {'field', 'mode', 'values'}:
                raise invalid_query()
        else:
            raise invalid_query()


def sorted_export_rows(batches, fields, sort, directory):
    key = business_sort_key(fields, sort)
    if not sort:
        for batch in batches:
            yield from batch
        return
    runs = []
    counter = 0
    def write_run(rows):
        nonlocal counter
        path = Path(directory) / f'{counter}.jsonl'
        counter += 1
        with path.open('w', encoding='utf-8') as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')
        return path
    # Bound memory to a source batch and open files to a 32-way merge.
    for batch in batches:
        if batch:
            runs.append(write_run(sorted(batch, key=key)))
    while len(runs) > 32:
        next_runs = []
        for offset in range(0, len(runs), 32):
            group = runs[offset:offset + 32]
            with ExitStack() as stack:
                readers = [_read_run(stack.enter_context(path.open(encoding='utf-8'))) for path in group]
                next_runs.append(write_run(heapq.merge(*readers, key=key)))
            for path in group:
                path.unlink()
        runs = next_runs
    with ExitStack() as stack:
        readers = [_read_run(stack.enter_context(path.open(encoding='utf-8'))) for path in runs]
        yield from heapq.merge(*readers, key=key)


def create_business_export(db, kind, data, context, request=None, *, project_id=None):
    prefix = 'project:archive' if kind == 'archive' else 'project:list'
    enforce_permission(context, prefix + ':view')
    enforce_permission(context, prefix + ':export')
    fields = export_fields(db, kind)
    columns = data.columns
    if not columns or len(columns) > 200 or len(set(columns)) != len(columns) or any(key not in fields for key in columns):
        raise HTTPException(422, '导出列包含未知、不允许显示或非业务字段')
    parameters = _parameters(kind, data.parameters)
    if kind == 'archive':
        _validate_archive_query_shapes(data.filters, data.column_filters)
    sort = query_items(data.sort)
    business_sort_key(fields, sort)
    conditions = compile_business_query(fields, data.filters, data.column_filters) if kind != 'archive' else None
    batches = _row_batches(db, kind, parameters, context, fields, data.filters, data.column_filters,
                           project_id, conditions)
    # Restore the list's default order after the stable PK scan; never expose its ID.
    fallback = ([{'colId': 'sort', 'sort': 'asc'}] if kind == 'task' else
                [{'colId': 'project_code', 'sort': 'desc'}] if kind == 'archive' else [])
    fallback.append({'colId': '_source_id', 'sort': 'asc' if kind == 'task' else 'desc'})
    ordered_fields = {item['colId'] for item in sort}
    output_sort = [*sort, *(item for item in fallback if item['colId'] not in ordered_fields)]
    sort_fields = {**fields, '_source_id': {'kind': 'number'}}
    fd, name = tempfile.mkstemp(prefix='pms-business-', suffix='.xlsx')
    os.close(fd)
    path = Path(name)
    try:
        count = 0
        with tempfile.TemporaryDirectory(prefix='pms-export-sort-') as directory, ReportWorkbook(path) as workbook:
            sheet = workbook.sheet(NAMES[kind], [(key, fields[key]['label']) for key in columns])
            rows = sorted_export_rows(batches, sort_fields, output_sort, directory)
            for row in rows:
                values = {key: fields[key].get('labels', {}).get(row.get(key), row.get(key)) for key in columns}
                for key, value in values.items():
                    if fields[key]['kind'] == 'number' and value is not None:
                        values[key] = Decimal(str(value))
                sheet.append(values)
                count += 1
        record_operation_log(db, module='项目档案' if kind == 'archive' else '项目进度', action='export',
                             entity_type='business_list_export', entity_id=project_id, entity_name=NAMES[kind],
                             operator_id=context['user_id'], request=request, summary=f"导出{NAMES[kind]}：{count}条",
                             after_data={'row_count': count, 'columns': columns, 'project_id': project_id})
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return path, NAMES[kind] + '.xlsx'
