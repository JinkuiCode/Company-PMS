"""只读验证金蝶认证，可选查询一个项目编号，不执行业务保存。"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-code", help="可选：读取一个已知编号，不输出业务名称")
    args = parser.parse_args()
    # 诊断进程只访问金蝶，不连接 PMS 业务数据库，也不要求本机安装 MSSQL 驱动。
    os.environ["DB_DIALECT"] = "sqlite"
    os.environ["SQLITE_DB_PATH"] = ":memory:"
    from app.core.config import settings
    from app.services.kingdee import KingdeeClient

    result = dict(auth_mode=settings.K3_AUTH_MODE, account_id=settings.K3_ACCT_ID,
                  username=settings.K3_USERNAME, read_only=True, success=False)
    client = KingdeeClient()
    try:
        result["success"] = client.login()
        if not result["success"]:
            result["message"] = "认证检查失败；核对账套、应用授权与受保护配置"
        elif args.project_code:
            row = client.query_assistant_data("BOS_ASSISTANTDATA_DETAIL", "xsxm", args.project_code)
            result["project_found"] = row is not None
            result["message"] = "认证及指定编号只读查询成功"
        else:
            result["message"] = "认证检查成功；未执行业务保存"
    except Exception:
        result["success"] = False
        result["message"] = "只读检查失败；未执行业务保存"
    finally:
        client.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
