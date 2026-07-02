"""
金蝶云星空 ERP 对接服务层
使用 Session 认证模式（账号密码登录）
"""
import json
import logging
from datetime import datetime
from typing import Optional
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import PmsProjectArchive, ErpSyncLog

logger = logging.getLogger(__name__)


class KingdeeClient:
    """金蝶云星空 WebAPI 客户端"""

    def __init__(self):
        self.base_url = settings.K3_URL
        self.acct_id = settings.K3_ACCT_ID
        self.username = settings.K3_USERNAME
        self.password = settings.K3_PASSWORD
        self.client = httpx.Client(timeout=30.0, verify=False)  # 内网环境禁用证书验证

    def login(self) -> bool:
        """
        登录金蝶获取 Session
        返回 True 表示登录成功，False 表示失败
        """
        try:
            url = f"{self.base_url}/Kingdee.BOS.WebApi.ServicesStub.AuthService.ValidateUser.common.kdsvc"
            payload = {
                "acctID": self.acct_id,
                "username": self.username,
                "password": self.password,
                "lcid": 2052
            }

            response = self.client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            login_type = result.get("LoginResultType", 0)

            if login_type == 1:
                logger.info(f"金蝶登录成功: {self.username}")
                return True
            else:
                logger.error(f"金蝶登录失败: LoginResultType={login_type}")
                return False

        except Exception as e:
            logger.error(f"金蝶登录异常: {str(e)}")
            return False

    def query_assistant_data(self, form_id: str, category_code: str, project_code: str) -> Optional[dict]:
        """
        查询辅助资料是否存在，返回含 FEntryID 的字典（用于更新时传内码）
        :param form_id: 表单ID，如 BOS_ASSISTANTDATA_DETAIL
        :param category_code: 类别编码，如 xsxm（销售项目）
        :param project_code: 项目编号
        :return: 存在则返回数据字典，不存在返回 None
        """
        try:
            url = f"{self.base_url}/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.ExecuteBillQuery.common.kdsvc"

            # 该金蝶实例的 ExecuteBillQuery 需要把参数包装为 data JSON 字符串字段
            filter_string = f"FNumber = '{project_code}'"
            data_content = json.dumps({
                "FormId": form_id,
                "FieldKeys": "FEntryID,FNumber,FDataValue",
                "FilterString": filter_string,
                "TopRowCount": 1,
                "StartRow": 0,
                "Limit": 1,
            }, ensure_ascii=False)

            response = self.client.post(url, json={"data": data_content})
            response.raise_for_status()

            result = response.json()
            logger.info(f"查询辅助资料返回: {json.dumps(result, ensure_ascii=False)[:300]}")

            # ExecuteBillQuery 返回二维数组 [[FEntryID, FNumber, FDataValue], ...]
            if result and isinstance(result, list) and len(result) > 0:
                row = result[0]
                if isinstance(row, list) and len(row) >= 2:
                    return {
                        "FEntryID": row[0],   # 内码（用于更新）
                        "FNumber": row[1],    # 编码
                        "FDataValue": row[2] if len(row) > 2 else ""
                    }

            return None

        except Exception as e:
            logger.error(f"查询辅助资料异常: {str(e)}")
            return None

    def save_assistant_data(self, form_id: str, category_code: str, project_code: str,
                            project_name: str, description: str = "",
                            entry_id: str = "") -> dict:
        """
        保存辅助资料（创建或更新）
        :param form_id: 表单ID
        :param category_code: 类别编码
        :param project_code: 项目编号
        :param project_name: 项目名称
        :param description: 描述
        :param entry_id: 记录内码（FEntryID），有值时为更新，空时为新建
        :return: 包含 success 和 message 的结果字典
        """
        try:
            url = f"{self.base_url}/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.Save.common.kdsvc"

            is_update = bool(entry_id)

            # 构建 Model 数据，更新时必须带 FEntryID（内码）
            model = {
                "FEntryID": entry_id,
                "FId": {"FNumber": category_code},  # 类别：销售项目
                "FNumber": project_code,
                "FDataValue": project_name,
                "FDescription": description
            }

            # 金蝶要求 data 必须是 JSON 字符串，不是对象
            # 更新时通过 NeedUpDateFields 指定要修改的字段
            data_str = json.dumps({
                "NeedUpDateFields": ["FDataValue", "FDescription"] if is_update else [],
                "NeedReturnFields": [],
                "IsDeleteEntry": "true",
                "IsVerifyBaseDataField": "false",
                "IsEntryBatchFill": "true",
                "ValidateFlag": "true",
                "NumberSearch": "true",
                "Model": model
            }, ensure_ascii=False)

            payload = {
                "formid": form_id,
                "data": data_str,
            }

            logger.info(f"金蝶Save请求 - formid: {form_id}")
            logger.info(f"金蝶Save请求 - data: {data_str[:300]}")

            response = self.client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(f"金蝶Save返回: {json.dumps(result, ensure_ascii=False)[:500]}")

            # 检查返回结果
            if "Result" in result:
                result_data = result["Result"]
                if isinstance(result_data, dict):
                    status = result_data.get("ResponseStatus", {})
                    if status.get("IsSuccess"):
                        return {
                            "success": True,
                            "message": "保存成功",
                            "data": result_data
                        }
                    else:
                        errors = status.get("Errors", [])
                        error_msg = errors[0].get("Message", "未知错误") if errors else "未知错误"
                        return {
                            "success": False,
                            "message": f"保存失败: {error_msg}"
                        }

            return {
                "success": False,
                "message": f"返回格式异常: {result}"
            }

        except Exception as e:
            logger.error(f"保存辅助资料异常: {str(e)}")
            return {
                "success": False,
                "message": f"保存异常: {str(e)}"
            }

    def close(self):
        """关闭 HTTP 客户端"""
        self.client.close()


def sync_project_archive_to_erp(db: Session, archive_id: int, user_id: int | None = None) -> dict:
    """
    同步单个项目档案到金蝶 ERP
    :param db: 数据库会话
    :param archive_id: 项目档案 ID
    :return: 包含 success 和 message 的结果字典
    """
    # 查询项目档案
    archive = db.query(PmsProjectArchive).filter(PmsProjectArchive.id == archive_id).first()
    if not archive:
        return {"success": False, "message": "项目档案不存在"}

    # 更新状态为 pending
    archive.erp_sync_status = "pending"
    db.commit()

    # 创建金蝶客户端
    client = KingdeeClient()

    try:
        # 1. 登录金蝶
        if not client.login():
            error_msg = "金蝶登录失败，请检查配置"
            archive.erp_sync_status = "failed"
            archive.erp_error_msg = error_msg
            db.commit()

            # 记录日志
            log = ErpSyncLog(
                source_id=archive_id,
                action="sync",
                status="failed",
                error_msg=error_msg
            )
            db.add(log)
            db.commit()

            return {"success": False, "message": error_msg}

        # 2. 查询是否已存在
        form_id = "BOS_ASSISTANTDATA_DETAIL"
        category_code = "xsxm"  # 销售项目

        existing = client.query_assistant_data(
            form_id=form_id,
            category_code=category_code,
            project_code=archive.project_code
        )

        action = "update" if existing else "create"
        entry_id = str(existing["FEntryID"]) if existing else ""

        # 3. 保存（创建或更新）
        save_result = client.save_assistant_data(
            form_id=form_id,
            category_code=category_code,
            project_code=archive.project_code,
            project_name=archive.project_name,
            description=f"PMS 项目档案同步",
            entry_id=entry_id
        )

        # 4. 更新同步状态
        if save_result["success"]:
            archive.erp_synced = 1
            archive.erp_sync_status = "success"
            archive.erp_sync_time = datetime.now()
            archive.erp_sync_by = user_id
            archive.erp_error_msg = None

            log = ErpSyncLog(
                source_id=archive_id,
                action=action,
                status="success",
                error_msg=None
            )
            db.add(log)
            db.commit()

            return {"success": True, "message": f"同步成功（{action}）"}
        else:
            archive.erp_sync_status = "failed"
            archive.erp_error_msg = save_result["message"]

            log = ErpSyncLog(
                source_id=archive_id,
                action=action,
                status="failed",
                error_msg=save_result["message"]
            )
            db.add(log)
            db.commit()

            return save_result

    except Exception as e:
        error_msg = f"同步异常: {str(e)}"
        archive.erp_sync_status = "failed"
        archive.erp_error_msg = error_msg

        log = ErpSyncLog(
            source_id=archive_id,
            action="sync",
            status="failed",
            error_msg=error_msg
        )
        db.add(log)
        db.commit()

        return {"success": False, "message": error_msg}

    finally:
        client.close()


def batch_sync_project_archives(db: Session, archive_ids: list[int], user_id: int | None = None) -> dict:
    """
    批量同步项目档案到金蝶 ERP
    :param db: 数据库会话
    :param archive_ids: 项目档案 ID 列表
    :return: 包含成功数和失败数的结果字典
    """
    success_count = 0
    failed_count = 0
    errors = []

    for archive_id in archive_ids:
        result = sync_project_archive_to_erp(db, archive_id, user_id=user_id)
        if result["success"]:
            success_count += 1
        else:
            failed_count += 1
            errors.append(f"ID {archive_id}: {result['message']}")

    return {
        "success": True,
        "message": f"批量同步完成：成功 {success_count}，失败 {failed_count}",
        "success_count": success_count,
        "failed_count": failed_count,
        "errors": errors
    }


def get_sync_logs(db: Session, archive_id: int, limit: int = 10) -> list:
    """
    获取指定项目档案的同步日志
    :param db: 数据库会话
    :param archive_id: 项目档案 ID
    :param limit: 返回条数限制
    :return: 日志列表
    """
    logs = db.query(ErpSyncLog)\
        .filter(ErpSyncLog.source_id == archive_id)\
        .order_by(ErpSyncLog.created_at.desc())\
        .limit(limit)\
        .all()

    return [
        {
            "id": log.id,
            "action": log.action,
            "status": log.status,
            "error_msg": log.error_msg,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in logs
    ]


def test_erp_connection() -> dict:
    """
    测试金蝶 ERP 连接
    :return: 包含 success 和 message 的结果字典
    """
    client = KingdeeClient()
    try:
        if client.login():
            return {"success": True, "message": "金蝶连接测试成功"}
        else:
            return {"success": False, "message": "金蝶登录失败，请检查账号密码"}
    except Exception as e:
        return {"success": False, "message": f"连接异常: {str(e)}"}
    finally:
        client.close()
