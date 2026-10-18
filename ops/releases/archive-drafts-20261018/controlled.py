"""Process-only maintenance acceptance wrapper; deployed candidate files stay exact."""
import asyncio
import json
import os
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from cutover import pause_workers,allowed_request,PAUSED_WORKERS,h
pause_workers()
sys.path.insert(0,'C:/PMS/backend')
from main import app
from app.services.runtime_release import load_runtime_manifest
from starlette.responses import JSONResponse

@app.middleware('http')
async def maintenance_writes(request,call_next):
    if not allowed_request(request.method,request.url.path):
        return JSONResponse({'detail':'系统升级验收中，暂不支持修改，请稍后再试。'},status_code=503)
    return await call_next(request)

original=app.router.lifespan_context
@asynccontextmanager
async def controlled_lifespan(application):
    async with original(application):
        running=[t.name for t in threading.enumerate() if t.name in PAUSED_WORKERS]
        h.check(not running,'Business worker unexpectedly started')
        manifest=load_runtime_manifest()
        proof=dict(version=manifest['version'],commit=manifest['commit'],background_workers_running=running,maintenance_writes_blocked=True,pid=os.getpid())
        h.save(HERE/'controlled-ready.json',proof,new=True)
        yield
app.router.lifespan_context=controlled_lifespan

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8000,log_level='warning',access_log=False)
