"""Process-only acceptance wrapper. All business workers remain paused."""
import json,os,sys,threading
from contextlib import asynccontextmanager
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from program_update import WORKERS,allowed_request,check,save

def pause_workers():
    start,join=threading.Thread.start,threading.Thread.join;paused=set()
    def guarded_start(thread,*args,**kw):
        if thread.name in WORKERS:paused.add(thread);return
        return start(thread,*args,**kw)
    def guarded_join(thread,*args,**kw):
        if thread in paused:return
        return join(thread,*args,**kw)
    threading.Thread.start=guarded_start;threading.Thread.join=guarded_join
    def restore():threading.Thread.start=start;threading.Thread.join=join
    return restore

def configure(app,manifest_loader,proof_path=HERE/'controlled-ready.json'):
    from starlette.responses import JSONResponse
    @app.middleware('http')
    async def maintenance(request,call_next):
        if not allowed_request(request.method,request.url.path):return JSONResponse({'detail':'系统升级验收中，暂不支持修改，请稍后再试。'},status_code=503)
        return await call_next(request)
    original=app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            running=[t.name for t in threading.enumerate() if t.name in WORKERS];check(not running,'Business worker unexpectedly running')
            manifest=manifest_loader();save(proof_path,dict(version=manifest['version'],commit=manifest['commit'],background_workers_running=running,maintenance_writes_blocked=True,pid=os.getpid()))
            yield
    app.router.lifespan_context=lifespan
    return app

if __name__=='__main__':
    from windows_update import guard_host,ROOT,load_pins
    import socket
    pins=load_pins();guard_host(os.name,ROOT,HERE,socket.gethostbyname_ex(socket.gethostname())[2],pins)
    pause_workers();sys.path.insert(0,str(ROOT/'backend'))
    from main import app
    from app.services.runtime_release import load_runtime_manifest
    configure(app,load_runtime_manifest)
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8000,log_level='warning',access_log=False)
