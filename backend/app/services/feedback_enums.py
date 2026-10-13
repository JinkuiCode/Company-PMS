"""Stable numeric workflow values and administrator-maintained classifications."""
from app.models.feedback import FeedbackReport, FeedbackFollowup

DEFINITIONS = {
    'type': ('提报类型', 'workflow', ['问题', '需求']),
    'module': ('涉及模块', 'configurable', ['项目档案', '项目进度', '采购进度查询', '即时库存查询', '物料收发明细', '系统管理', '登录与OA集成', '通用功能']),
    'issue_category': ('问题类别', 'configurable', ['功能异常', '数据异常', '界面体验', '权限访问', '性能稳定', '操作咨询']),
    'request_category': ('需求类别', 'configurable', ['新增功能', '流程优化', '报表需求', '字段调整', '体验优化']),
    'impact': ('影响程度', 'configurable', ['业务无法继续', '影响部分操作', '不影响正常使用']),
    'status': ('处理状态', 'workflow', ['待受理', '处理中', '待补充', '已排期', '已完成', '已关闭']),
    'outcome': ('处理结论', 'workflow', ['已修复', '已交付', '使用指导', '无需调整', '暂不采纳', '重复提报']),
    'cause': ('处理归因', 'configurable', ['程序逻辑', '业务规则', '基础数据', '角色权限', '网络与环境', '操作使用', '功能缺失', '其他']),
}
FEEDBACK_ENUMS = {
    'feedback_' + key: dict(name=name, description='问题提报：' + name, mode=mode,
        value_strategy='numeric_sequence', visible=True, sort=70 + index,
        table_name='pms_feedback_report', field_name='category_id' if key.endswith('_category') else key + '_id',
        bindings=['问题提报.' + key], items=[(str(i), label) for i, label in enumerate(labels, 1)])
    for index, (key, (name, mode, labels)) in enumerate(DEFINITIONS.items())
}


def count_feedback_references(db, code, value):
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 0
    key = code.removeprefix('feedback_')
    if key.endswith('_category'):
        return db.query(FeedbackReport).filter(FeedbackReport.type_id == (1 if key == 'issue_category' else 2), FeedbackReport.category_id == numeric).count()
    column = getattr(FeedbackReport, key + '_id')
    count = db.query(FeedbackReport).filter(column == numeric).count()
    if key in ('status', 'outcome', 'cause'):
        count += db.query(FeedbackFollowup).filter(getattr(FeedbackFollowup, key + '_id') == numeric).count()
    return count
