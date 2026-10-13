"""Scoped feedback operations with history, audit and notification in one commit."""
from collections import Counter
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import case, cast, select, String, update, func, text
from sqlalchemy.exc import IntegrityError
from app.models.feedback import FeedbackReport as Report, FeedbackFollowup, FeedbackNotification, FeedbackAttachment
from app.models.user import SysUser
from app.models.dict import SysDict, SysDictItem
from app.services.authorization import enforce_permission
from app.services.enum_registry import validate_enum_value
from app.services.operation_log import serialize_model, record_operation_log
from app.services.list_query import apply_list_query
from app.services.business_list_query import compile_business_query
from app.services.query_conditions import build_query_clause

ENUM_FIELDS = {'type_id': 'feedback_type', 'module_id': 'feedback_module', 'impact_id': 'feedback_impact', 'status_id': 'feedback_status'}
MAIL_LABELS = {'pending': '待发送', 'waiting': '待配置', 'processing': '发送中', 'sent': '已发送', 'failed': '发送失败', 'unknown': '结果待核查'}


def business_time(value):
    return value.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))) if value.tzinfo is None else value.astimezone(timezone(timedelta(hours=8)))


def serialize_feedback(row, exclude=None):
    data = serialize_model(row, exclude=exclude)
    for key in data:
        value = getattr(row, key, None)
        if isinstance(value, datetime):
            data[key] = business_time(value).isoformat()
    return data


def category_code(type_id):
    return 'feedback_issue_category' if type_id == 1 else 'feedback_request_category'


def scoped_query(db, context, mine=False):
    enforce_permission(context, 'feedback:view')
    query = db.query(Report)
    if mine or 'feedback:handle' not in context['permissions']:
        query = query.filter(Report.author_id == context['user_id'])
    return query


def require_report(db, context, report_id):
    row = scoped_query(db, context).filter(Report.id == report_id).first()
    if row is None:
        raise HTTPException(404, '提报不存在或无权访问')
    return row


def output(db, row, detail=False):
    data = serialize_feedback(row)
    for field, user_id in (('author_name', row.author_id), ('handler_name', row.handler_id)):
        user = db.get(SysUser, user_id) if user_id else None
        data[field] = user.real_name if user else ''
    latest = db.query(FeedbackNotification).filter_by(report_id=row.id).order_by(FeedbackNotification.id.desc()).first()
    data['mail_status'] = latest.status if latest else ''
    definition = db.query(SysDict).filter_by(dict_code=category_code(row.type_id)).first()
    item = db.query(SysDictItem).filter_by(dict_id=definition.id, item_value=str(row.category_id)).first() if definition else None
    data['category_name'] = item.item_label if item else str(row.category_id)
    if detail:
        data['followups'] = [serialize_feedback(item) | {'actor_name': db.get(SysUser, item.actor_id).real_name} for item in db.query(FeedbackFollowup).filter_by(report_id=row.id).order_by(FeedbackFollowup.id)]
        data['notifications'] = [serialize_feedback(item) for item in db.query(FeedbackNotification).filter_by(report_id=row.id).order_by(FeedbackNotification.id.desc())]
        data['attachments'] = [serialize_feedback(item, exclude={'storage_name'}) for item in db.query(FeedbackAttachment).filter_by(report_id=row.id).order_by(FeedbackAttachment.id)]
    return data


def get_report(db, context, report_id):
    return output(db, require_report(db, context, report_id), True)


def enum_labels(db, code):
    return {int(value): label for value, label in db.query(SysDictItem.item_value, SysDictItem.item_label).join(SysDict, SysDict.id == SysDictItem.dict_id).filter(SysDict.dict_code == code) if value.isdigit()}


def query_spec(db):
    columns = {key: (getattr(Report, key), 'text') for key in ('report_no', 'title')}
    for name in ('author_name', 'handler_name'):
        columns[name] = (select(SysUser.real_name).where(SysUser.id == getattr(Report, name.replace('_name', '_id'))).scalar_subquery(), 'text')
    columns['category_name'] = (select(SysDictItem.item_label).join(SysDict, SysDict.id == SysDictItem.dict_id).where(
        SysDict.dict_code == case((Report.type_id == 1, 'feedback_issue_category'), else_='feedback_request_category'),
        SysDictItem.item_value == cast(Report.category_id, String(64))).correlate(Report).scalar_subquery(), 'text')
    # Storage and worker clocks stay UTC; date conditions use the displayed China day.
    for key in ('created_at', 'updated_at'):
        source = getattr(Report, key)
        local_date = func.dateadd(text('hour'), 8, source) if db.get_bind().dialect.name == 'mssql' else func.datetime(source, '+8 hours')
        columns[key] = (local_date, 'date')
    columns.update({key: (getattr(Report, key), 'number') for key in ENUM_FIELDS})
    columns['mail_status'] = (select(FeedbackNotification.status).where(FeedbackNotification.report_id == Report.id).order_by(FeedbackNotification.id.desc()).limit(1).correlate(Report).scalar_subquery(), 'text')
    category_labels = {value: value for code in ('feedback_issue_category', 'feedback_request_category') for value in enum_labels(db, code).values()}
    fields = {key: {'kind': 'enum_number' if key in ENUM_FIELDS else 'enum_text' if key in ('mail_status', 'category_name') else kind,
                    'labels': enum_labels(db, ENUM_FIELDS[key]) if key in ENUM_FIELDS else MAIL_LABELS if key == 'mail_status' else category_labels if key == 'category_name' else {}}
              for key, (_, kind) in columns.items()}
    return columns, fields


def filtered_query(db, context, filters=None, sort=None, mine=False, status_id=None):
    query = scoped_query(db, context, mine)
    if status_id is not None:
        query = query.filter(Report.status_id.in_([1, 2, 3, 4]) if status_id == 0 else Report.status_id == status_id)
    columns, fields = query_spec(db)
    for condition in compile_business_query(fields, filters):
        kind = fields[condition.field]['kind']
        value = condition.value
        if kind == 'enum_number' and value is not None:
            value = [int(item) for item in value] if isinstance(value, list) else int(value)
        item = {'schemaVersion': 2, 'operator': condition.operator, 'value': value,
                'valueEnd': condition.valueEnd.isoformat() if hasattr(condition.valueEnd, 'isoformat') else condition.valueEnd}
        if hasattr(value, 'isoformat'):
            item['value'] = value.isoformat()
        # An empty label match is a valid condition with no matching records.
        clause = columns[condition.field][0].in_([]) if condition.operator == 'in' and value == [] else build_query_clause(columns[condition.field][0], kind, item, membership=True)
        query = query.filter(clause)
    return apply_list_query(query, columns, [], sort, (Report.id.desc(),), unified_kinds={key: field['kind'] for key, field in fields.items()})


def list_reports(db, context, *, page=1, page_size=50, filters=None, sort=None, mine=False, status_id=None):
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 500:
        raise HTTPException(422, '分页参数无效')
    query = filtered_query(db, context, filters, sort, mine, status_id)
    total = query.order_by(None).count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return dict(items=[output(db, row) for row in rows], total=total, query_version=2)


def statistics(db, context, mine=False):
    rows = scoped_query(db, context, mine).all()
    counts = Counter(row.status_id for row in rows)
    modules, categories = Counter(row.module_id for row in rows), Counter((row.type_id, row.category_id) for row in rows)
    return dict(total=len(rows), open=sum(counts[value] for value in (1, 2, 3, 4)), completed=counts[5],
                issues=sum(row.type_id == 1 for row in rows), requests=sum(row.type_id == 2 for row in rows),
                statuses=dict(counts), modules=[{'module_id': key, 'count': count,
                    'issues': sum(row.module_id == key and row.type_id == 1 for row in rows),
                    'requests': sum(row.module_id == key and row.type_id == 2 for row in rows),
                    'open': sum(row.module_id == key and row.status_id in (1, 2, 3, 4) for row in rows),
                    'completed': sum(row.module_id == key and row.status_id == 5 for row in rows)} for key, count in modules.items()],
                categories=[{'type_id': key[0], 'category_id': key[1], 'count': count} for key, count in categories.items()])


def add_event(db, row, context, action, description, audience):
    db.add(FeedbackFollowup(report_id=row.id, actor_id=context['user_id'], action=action, description=description,
        status_id=row.status_id, outcome_id=row.outcome_id, cause_id=row.cause_id, version=row.version))
    db.add(FeedbackNotification(report_id=row.id, version=row.version, audience=audience, status='pending'))


def audit(db, context, row, action, before=None, request=None):
    record_operation_log(db, module='问题提报', action=action, entity_type='pms_feedback_report',
        entity_id=row.id, entity_name=row.report_no, operator_id=context['user_id'], request=request,
        summary=f'{row.report_no}：{row.title}', before_data=before, after_data=serialize_model(row))


def create_report(db, context, data, request=None):
    enforce_permission(context, 'feedback:add')
    enforce_permission(context, 'feedback:view')
    def existing_submission():
        existing = db.query(Report).filter_by(author_id=context['user_id'], submission_id=data.submission_id).first()
        if existing:
            if any(getattr(existing, key) != value for key, value in data.model_dump().items()):
                raise HTTPException(409, '同一提交标识不能用于不同提报内容')
            return output(db, existing, True)
        return None
    existing = existing_submission()
    if existing:
        return existing
    for field in ('type_id', 'module_id', 'impact_id'):
        validate_enum_value(db, ENUM_FIELDS[field], getattr(data, field))
    validate_enum_value(db, category_code(data.type_id), data.category_id)
    validate_enum_value(db, 'feedback_status', 1)
    row = Report(**data.model_dump(), report_no='draft-' + uuid4().hex, author_id=context['user_id'], status_id=1, version=1)
    try:
        db.add(row)
        db.flush()
        row.report_no = f'FB-{business_time(datetime.utcnow()):%Y%m}-{row.id:06d}'
        add_event(db, row, context, 'create', row.description, 'admins')
        audit(db, context, row, 'create', request=request)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = existing_submission()
        if existing:
            return existing
        raise
    except Exception:
        db.rollback()
        raise
    return output(db, row, True)


def update_report(db, context, report_id, data, action, values, audience, request=None):
    row = require_report(db, context, report_id)
    before = serialize_model(row)
    try:
        changed = db.execute(update(Report).where(Report.id == row.id, Report.version == data.version).values(**values, version=data.version + 1, updated_at=datetime.utcnow()), execution_options={'synchronize_session': False})
        if changed.rowcount != 1:
            raise HTTPException(409, '提报已被修改，请刷新详情后重试')
        db.refresh(row)
        add_event(db, row, context, action, data.opinion if action == 'handle' else data.description, audience)
        audit(db, context, row, 'update', before, request)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return output(db, row, True)


def handle_report(db, context, report_id, data, request=None):
    enforce_permission(context, 'feedback:handle')
    validate_enum_value(db, 'feedback_status', data.status_id)
    if data.outcome_id:
        validate_enum_value(db, 'feedback_outcome', data.outcome_id)
    if data.cause_id:
        validate_enum_value(db, 'feedback_cause', data.cause_id)
    return update_report(db, context, report_id, data, 'handle', dict(status_id=data.status_id,
        opinion=data.opinion, outcome_id=data.outcome_id, cause_id=data.cause_id, handler_id=context['user_id']), 'author', request)


def supplement_report(db, context, report_id, data, request=None):
    enforce_permission(context, 'feedback:supplement')
    row = require_report(db, context, report_id)
    if row.author_id != context['user_id']:
        raise HTTPException(403, '仅提报人可补充信息；处理人员请记录处理意见')
    return update_report(db, context, report_id, data, 'supplement', {}, 'admins', request)
