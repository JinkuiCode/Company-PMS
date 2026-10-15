"""Independent audit for rejected writes; never copy request bodies or tokens."""
from collections import OrderedDict
import logging
import threading
import time
from app.services.operation_log import record_operation_log

MAX_BUCKETS = 4096
WINDOW_SECONDS = 60
MAX_EVENTS_PER_SOURCE = 30
_lock = threading.Lock()
_buckets = OrderedDict()
_sources = OrderedDict()


def reset_limiter_for_tests():
    with _lock: _buckets.clear(); _sources.clear()


def limiter_size():
    with _lock: return len(_buckets)


def _claim(key):
    now = time.monotonic()
    with _lock:
        previous = _buckets.get(key)
        if previous and now - previous[0] < WINDOW_SECONDS:
            _buckets[key] = (previous[0], previous[1] + 1)
            return None
        suppressed = previous[1] if previous else 0
        source_key = key[:2]
        source = _sources.get(source_key)
        if source and now-source[0] < WINDOW_SECONDS:
            if source[1] >= MAX_EVENTS_PER_SOURCE:
                _sources[source_key] = (source[0], source[1], source[2]+1)
                return None
            _sources[source_key] = (source[0], source[1]+1, source[2])
        else:
            suppressed += source[2] if source else 0
            _sources[source_key] = (now, 1, 0)
        _sources.move_to_end(source_key)
        while len(_sources) > MAX_BUCKETS: _sources.popitem(last=False)
        _buckets[key] = (now, 0)
        _buckets.move_to_end(key)
        while len(_buckets) > MAX_BUCKETS: _buckets.popitem(last=False)
        return suppressed


def record_request_failure(request, status_code, *, session_factory=None):
    if not request.url.path.startswith('/api/'):
        return False
    if status_code not in (401, 403, 404) and request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return False
    if getattr(request.state, 'audit_failure_recorded', False):
        return False
    route = getattr(request.scope.get('route'), 'path', '[未匹配路由]')
    # A route template groups repeated object probes without persisting client data.
    actor = getattr(request.state, 'audit_actor_id', None)
    source = request.client.host if request.client else 'unknown'
    count = _claim((actor, source, request.method, route, status_code))
    if count is None: return False
    if session_factory is None:
        from app.core.database import SessionLocal
        session_factory = SessionLocal
    try:
        with session_factory() as db:
            denied = status_code in (401, 403, 404)
            record_operation_log(db, module='安全审计', action='denied' if denied else 'failed_write',
                entity_type='security_request', operator_id=actor, request=request, status='failed',
                summary=f'请求被拒绝（HTTP {status_code}）' if denied else f'写操作失败（HTTP {status_code}）',
                after_data={'status_code': status_code, 'suppressed_repeats': count}, commit=True)
        request.state.audit_failure_recorded = True
        return True
    except Exception:
        # Keep the original failure response; never turn a rejection into success.
        logging.getLogger(__name__).warning('安全审计暂时无法写入，请检查日志存储')
        return False
