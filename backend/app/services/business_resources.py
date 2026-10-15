"""Shared resource policy registry. Support policies are explicit exceptions."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ResourcePolicy:
    entity_type: str
    view_permission: str
    scope: str
    guide: str | None
    field_policy: str | None = None
    label: str = ''
    product_line_source: str | None = None
    log_root: str | None = None


BUSINESS_RESOURCES = {
    'archive': ResourcePolicy('pms_project_archive', 'project:archive:view', 'product_line_and_personnel', 'archive', 'project_archive', '项目档案', 'business_product_line_id', 'pms_project_archive'),
    'project': ResourcePolicy('pms_project', 'project:list:view', 'product_line_and_personnel', 'progress', 'project_progress', '项目进度', 'archive.business_product_line_id', 'pms_project'),
    'task': ResourcePolicy('pms_task', 'project:list:view', 'parent_project', 'tasks', None, '任务', 'project.archive.business_product_line_id', 'pms_project'),
    'archive_change': ResourcePolicy('pms_archive_change', 'project:archive:view', 'parent_archive_and_participant', 'archiveChanges', None, '档案变更申请', 'archive.business_product_line_id', 'pms_project_archive'),
    'dashboard': ResourcePolicy('pms_project', 'dashboard:view', 'product_line_and_personnel', 'progress', product_line_source='archive.business_product_line_id'),
    'purchase': ResourcePolicy('erp_purchase', 'report:purchase:view', 'authorized_erp_organizations', 'purchase', product_line_source='product_line.organization_id'),
    'inventory': ResourcePolicy('erp_inventory', 'report:inventory:view', 'authorized_erp_organizations', 'inventory', product_line_source='product_line.organization_id'),
    'stock': ResourcePolicy('erp_stock_detail', 'report:stock-detail:list', 'authorized_erp_organizations', 'stock', product_line_source='product_line.organization_id'),
    'sync_task': ResourcePolicy('erp_sync_task', 'system:sync:view', 'parent_archive_and_live_actor', 'archive', product_line_source='archive.business_product_line_id', log_root='pms_project_archive'),
    'export_task': ResourcePolicy('report_export', 'resource_specific', 'owner_and_live_resource_scope', None),
    'initial_archive': ResourcePolicy('pms_archive_import_batch', 'project:archive:import', 'explicit_all_business_data', 'archive'),
    'feedback': ResourcePolicy('pms_feedback_report', 'feedback:view', 'owner_or_authorized_handler', 'feedback', None, '问题提报', log_root='pms_feedback_report'),
    'feedback_attachment': ResourcePolicy('pms_feedback_attachment', 'feedback:view', 'parent_feedback', 'feedback', log_root='pms_feedback_report'),
    'release_notice': ResourcePolicy('pms_release_notice', 'authenticated', 'owner_only', None),
    'release_delivery': ResourcePolicy('pms_release_mail', 'system:release:manage', 'explicit_support_management', None),
    'audit': ResourcePolicy('sys_operation_log', 'system:operation-log:view', 'explicit_global_audit', 'audit'),
    'system_management': ResourcePolicy('system_configuration', 'resource_specific', 'explicit_action_permission', None),
    'release_publication': ResourcePolicy('pms_release', 'system:release:publish', 'live_actor_and_accepted_runtime', None),
    'release_history': ResourcePolicy('pms_release', 'authenticated', 'published_content_only', None),
    'document_history': ResourcePolicy('registered_document', 'resource_specific', 'current_registered_entity_and_fields', None),
    'session': ResourcePolicy('authentication', 'session_specific', 'verified_session_or_login_policy', None),
    'health': ResourcePolicy('service_health', 'public', 'public_health_only', None),
}

DOCUMENT_RESOURCES = {key: BUSINESS_RESOURCES[key] for key in ('archive', 'project', 'task', 'feedback')}

# Longest prefix first, with the path-parameter spellings from FastAPI routes.
ROUTE_RESOURCES = {
    '/api/document-history': 'document_history',
    '/api/releases/notices': 'release_notice', '/api/releases/mail': 'release_delivery',
    '/api/releases/{release_id}/deliveries': 'release_delivery', '/api/releases/publish': 'release_publication',
    '/api/releases': 'release_history', '/api/offline-archives/archives': 'archive',
    '/api/offline-archives': 'initial_archive', '/api/projects/archive-changes': 'archive_change',
    '/api/projects/archives': 'archive', '/api/projects/{project_id}/tasks': 'task',
    '/api/projects': 'project', '/api/dashboard': 'dashboard', '/api/sync-tasks': 'sync_task',
    '/api/erp': 'archive', '/api/reports/purchase': 'purchase', '/api/reports/inventory': 'inventory',
    '/api/reports/stock-detail': 'stock', '/api/report-exports': 'export_task',
    '/api/feedback/attachments': 'feedback_attachment', '/api/feedback': 'feedback',
    '/api/operation-logs': 'audit', '/api/auth': 'session', '/api/sso': 'session',
    '/api/health': 'health',
    **{f'/api/{name}': 'system_management' for name in ('users','roles','menus','depts','parameters','product-lines','dicts','field-catalog','field-policies','my-menus')},
}


def resource_for_route(path):
    for prefix in sorted(ROUTE_RESOURCES, key=len, reverse=True):
        if path == prefix or path.startswith(prefix + '/'):
            return BUSINESS_RESOURCES[ROUTE_RESOURCES[prefix]]
    raise KeyError(f'未登记的业务接口：{path}')
