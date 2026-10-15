#!/usr/bin/env python3
"""Publish the running build after verified deployment. Requires current RBAC."""
import argparse
import json
import sys
from getpass import getpass
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings, validate_runtime_config
from app.core.database import engine, SessionLocal
from app.services.database_revision import check_database_ready
from app.services.authorization import build_authorization_context
from app.services.runtime_release import load_runtime_manifest
from app.services.releases import publish_release
from app.schemas.user import LoginRequest
from app.services.auth import login
from app.services.authorization import authenticate_session
from fastapi.security import HTTPAuthorizationCredentials


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acceptance-report', required=True, type=Path, help='已完成部署验收的凭据；不包含密码')
    args = parser.parse_args()
    validate_runtime_config(settings); check_database_ready(engine)
    manifest = load_runtime_manifest()
    if not manifest: raise SystemExit('没有当前构建的运行版本清单，未发布')
    receipt = json.loads(args.acceptance_report.read_text(encoding='utf-8'))
    with SessionLocal() as db:
        username = input('PMS发布操作人用户名：').strip()
        password = getpass('PMS密码（隐藏输入，不保存）：')
        token = login(db, LoginRequest(username=username, password=password, remember_me=False))
        del password
        session = authenticate_session(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token.access_token), db)
        context = build_authorization_context(db, session['user_id'])
        row = publish_release(db, context, manifest, receipt)
        print(f'{row.version} 发布记录及个人通知已保存；邮件由独立投递开关控制')
