#!/usr/bin/env python3
"""Preflight Kingdee sales-project archives; apply only with an approved backup."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from app.core.config import settings, validate_runtime_config
from app.core.database import engine
from app.models.project import PmsProject, PmsProjectArchive
from app.models.user import SysUser
from app.services.database_revision import check_database_ready
from app.services.kingdee_initial_archive import (
    insert_initial_archives,
    preflight_fingerprint,
    preflight_initial_archives,
)


SOURCE = "[10.10.1.248].[AIS20231211221516].[dbo].[YD_JIN_SALL_ASSISTANTDATA]"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="金蝶销售项目期初档案预检与受控导入")
    parser.add_argument("--report", type=Path, required=True, help="仅保存在运行机器上的 JSON 报告路径")
    parser.add_argument("--apply", action="store_true", help="显式允许写入 PMS")
    parser.add_argument("--approved-report-sha256", help="已人工审阅的预检报告指纹")
    parser.add_argument("--backup-reference", help="已验证备份的人工登记编号")
    parser.add_argument("--operator-id", type=int, help="执行导入的 PMS 用户 ID")
    parser.add_argument("--accept-exceptions", action="store_true", help="异常记录留待人工处理，只导入无异常行")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_runtime_config(settings)
    with engine.connect() as connection:
        rows = connection.exec_driver_sql(f"""
            SELECT TypeCode, ProjectCode, ProjectName, Remarks, ProjectID
            FROM {SOURCE} WHERE TypeCode = 'xsxm'
        """).mappings().all()
    with Session(engine) as db:
        existing = db.query(PmsProjectArchive.project_code).all()
        progress_codes = db.query(PmsProject.project_code).all()
        report = preflight_initial_archives(
            rows,
            existing_codes=[item.project_code for item in existing] + [item.project_code for item in progress_codes],
        )
        fingerprint = preflight_fingerprint(report)
        issue_counts = dict(Counter(item["reason"] for item in report["issues"]))
        report_file = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": SOURCE,
            "source_count": report["source_count"],
            "ready_count": len(report["ready"]),
            "blank_name_ready_count": sum(item["project_name"] is None for item in report["ready"]),
            "issue_counts": issue_counts,
            "issues": report["issues"],
            "legacy_name_differences": report["legacy_name_differences"],
            "preflight_sha256": fingerprint,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report_file, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps({key: report_file[key] for key in (
            "source_count", "ready_count", "blank_name_ready_count", "issue_counts", "preflight_sha256",
        )}, ensure_ascii=False))
        print(f"报告已留在运行机器: {args.report}")
        if not args.apply:
            return
        if not args.approved_report_sha256 or args.approved_report_sha256 != fingerprint:
            raise SystemExit("预检指纹不一致，拒绝导入")
        if not args.backup_reference or not args.backup_reference.strip():
            raise SystemExit("缺少已验证备份登记编号，拒绝导入")
        if not args.operator_id or not db.get(SysUser, args.operator_id):
            raise SystemExit("缺少有效 PMS 操作人，拒绝导入")
        if report["issues"] and not args.accept_exceptions:
            raise SystemExit("存在异常记录；确认异常留待人工处理后才能导入无异常行")
        check_database_ready(engine)
        try:
            imported = insert_initial_archives(db, report["ready"], operator_id=args.operator_id)
            db.commit()
        except Exception:
            db.rollback()
            raise
        print(f"导入完成: {imported} 条；异常 {len(report['issues'])} 条未写入")


if __name__ == "__main__":
    main()
