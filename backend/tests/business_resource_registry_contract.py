"""Admission contract: new API modules must declare a scope strategy."""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TMP = tempfile.TemporaryDirectory()
os.environ.update(DB_DIALECT='sqlite', SQLITE_DB_PATH=str(Path(TMP.name)/'unused.db'))
from main import app
from app.services.business_resources import BUSINESS_RESOURCES, DOCUMENT_RESOURCES, resource_for_route

for route in app.routes:
    path = getattr(route, 'path', '')
    if path.startswith('/api/'):
        policy = resource_for_route(path)
        assert policy.scope and policy.view_permission, path
for policy in BUSINESS_RESOURCES.values():
    if policy.scope in ('product_line_and_personnel','parent_project','authorized_erp_organizations'):
        assert policy.product_line_source
assert set(DOCUMENT_RESOURCES) == {'archive','project','task','feedback'}
assert resource_for_route('/api/releases/notices/1/read').scope == 'owner_only'
# FastAPI declarations contain parameter names, not a caller-provided raw URL.
assert resource_for_route('/api/releases/{release_id}/deliveries').scope == 'explicit_support_management'
try:
    resource_for_route('/api/unregistered-business-module')
except KeyError:
    pass
else:
    raise AssertionError('新业务模块不得静默沿用默认全量范围')
print('business resource registry contract passed; registration is not runtime authorization acceptance')
