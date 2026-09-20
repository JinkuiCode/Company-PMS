"""Process-spanning execution mutex, separate from short business transactions."""
from contextlib import contextmanager
from pathlib import Path
import threading
from sqlalchemy import text

_memory_locks = {}
_registry_lock = threading.Lock()


@contextmanager
def archive_execution_lock(db, archive_id):
    engine = db.get_bind()
    if engine.dialect.name == 'mssql':
        with engine.connect() as connection:
            name = f'pms:erp:archive:{archive_id}'
            result = connection.execute(text("""
                DECLARE @result int;
                EXEC @result = sys.sp_getapplock @Resource=:name,
                    @LockMode='Exclusive', @LockOwner='Session', @LockTimeout=0;
                SELECT @result;
            """), {'name': name}).scalar()
            acquired = result is not None and result >= 0
            try:
                yield acquired
            finally:
                if acquired:
                    try:
                        connection.execute(text("EXEC sys.sp_releaseapplock @Resource=:name, @LockOwner='Session'"), {'name': name})
                    except Exception:
                        connection.invalidate()
                        raise
        return
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('Unsupported ERP execution-lock database')
    database = engine.url.database
    if not database or database == ':memory:':
        with _registry_lock:
            lock = _memory_locks.setdefault((id(engine), archive_id), threading.Lock())
        acquired = lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                lock.release()
        return
    import os
    folder = Path(database).resolve().with_suffix('.erp-locks')
    folder.mkdir(exist_ok=True)
    with (folder / str(archive_id)).open('a+b') as handle:
        acquired = False
        if os.name == 'nt':
            import msvcrt
            if handle.tell() == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                pass
        try:
            yield acquired
        finally:
            if acquired:
                if os.name == 'nt':
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
