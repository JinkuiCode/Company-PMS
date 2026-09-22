"""
金蝶云星空 ERP 对接服务层
支持官方 SDK 应用签名；密码会话仅用于显式回退。
"""
import json
import logging
from datetime import datetime
from typing import Optional
import httpx
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import PmsProjectArchive, ErpSyncLog
from app.services.operation_log import record_operation_log, serialize_model
from app.services.project import get_scoped_archive_query, validate_archive_for_business_operation
from app.services.project_archive_lifecycle import (
    claim_archive_for_sync,
)

logger = logging.getLogger(__name__)


class KingdeeSaveOutcomeAmbiguous(RuntimeError):
    """保存请求已开始，但无法可靠确认金蝶是否落库。"""


class KingdeeDuplicateProjectCode(RuntimeError):
    """The target category contains multiple entries with the same code."""


class KingdeeClient:
    """金蝶云星空 WebAPI 客户端"""

    def __init__(self):
        self.base_url = settings.K3_URL
        self.acct_id = settings.K3_ACCT_ID
        self.username = settings.K3_USERNAME
        self.password = settings.K3_PASSWORD
        self.auth_mode = settings.K3_AUTH_MODE
        self.read_only = settings.K3_READ_ONLY
        self.app_id = settings.K3_APP_ID
        self.app_secret = settings.K3_APP_SECRET
        self.lcid = settings.K3_LCID
        self.org_num = settings.K3_ORG_NUM
        self._sensitive_values = {value for value in (self.password, self.app_secret) if value}
        self.sdk = None
        self.client = httpx.Client(timeout=30.0, verify=False)  # 内网环境禁用证书验证

    def _post(self, url: str, *, json: dict):
        """官方 SDK 生成每次请求的签名；沿用现有 HTTP 传输，不自动重试。"""
        if self.auth_mode == "app":
            if self.sdk is None:
                if not all((self.acct_id, self.username, self.app_id, self.app_secret)):
                    raise ValueError("金蝶应用配置不完整")
                from k3cloud_webapi_sdk.main import K3CloudApiSdk
                self.sdk = K3CloudApiSdk()
                self.sdk.InitConfig(
                    self.acct_id, self.username, self.app_id, self.app_secret,
                    server_url=self.base_url, lcid=self.lcid, org_num=self.org_num,
                )
            headers = self.sdk.BuildHeader(url)
            self._sensitive_values.update(
                value for key, value in headers.items() if "signature" in key.lower() and value
            )
            return self.client.post(url, json=json, headers=headers)
        if self.auth_mode != "password":
            raise ValueError("金蝶认证模式无效")
        return self.client.post(url, json=json)

    def _business_error_message(self, message) -> str:
        """Translate explicit record locks into a manual recovery instruction."""
        text = self._redact_message(message)
        operation_conflict = all(word in text for word in ("使用业务单据", "业务操作", "冲突", "请稍候"))
        record_occupied = "占用" in text and any(word in text for word in ("单据", "资料", "表单"))
        if operation_conflict or record_occupied:
            return (
                "金蝶当前单据被占用。请在金蝶端退出当前单据后，再次点击 PMS 的“同步”。"
                f"如由其他用户占用，请联系该用户退出。金蝶返回：{text}"
            )
        return text

    def _redact_message(self, message) -> str:
        if not isinstance(message, str):
            return "金蝶返回错误信息格式异常"
        for value in sorted(self._sensitive_values, key=len, reverse=True):
            message = message.replace(value, "[已脱敏]")
        return message

    @staticmethod
    def _query_rows(result, min_columns: int) -> list:
        """查询业务错误可能也返回 HTTP 200，不能将错误当作不存在。"""
        if not isinstance(result, list) or any(
            not isinstance(row, list) or len(row) < min_columns
            or any(isinstance(value, (dict, list)) for value in row)
            for row in result
        ):
            raise RuntimeError("金蝶查询未成功，请检查应用授权、账套及用户查询权限")
        return result

    def login(self) -> bool:
        """
        应用模式通过真实的签名只读查询验证授权；密码模式登录获取会话。
        不因应用认证失败自动退回密码模式。
        """
        self.login_retryable = False
        try:
            if self.auth_mode == "app":
                url = f"{self.base_url}/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.ExecuteBillQuery.common.kdsvc"
                response = self._post(url, json={"data": json.dumps({
                    "FormId": "BOS_ASSISTANTDATA_DETAIL", "FieldKeys": "FEntryID",
                    "FilterString": "1=0", "TopRowCount": 1, "StartRow": 0, "Limit": 1,
                })})
                response.raise_for_status()
                self._query_rows(response.json(), 1)
                logger.info("金蝶应用授权只读验证成功")
                return True
            if self.auth_mode != "password" or not all((self.acct_id, self.username, self.password)):
                return False
            url = f"{self.base_url}/Kingdee.BOS.WebApi.ServicesStub.AuthService.ValidateUser.common.kdsvc"
            payload = {
                "acctID": self.acct_id,
                "username": self.username,
                "password": self.password,
                "lcid": self.lcid
            }

            response = self._post(url, json=payload)
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
            self.login_retryable = isinstance(e, (httpx.TimeoutException, httpx.NetworkError))
            # 服务端错误或第三方异常可能含凭据/签名，不输出其原文。
            logger.error("金蝶认证失败（%s），请检查认证模式、应用授权与连接配置", type(e).__name__)
            return False

    def query_assistant_data(self, form_id: str, category_code: str, project_code: str,
                             *, include_status: bool = False) -> Optional[dict]:
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
            category_literal = category_code.replace("'", "''")
            project_literal = project_code.replace("'", "''")
            filter_string = f"FId.FNumber = '{category_literal}' AND FNumber = '{project_literal}'"
            field_keys = "FEntryID,FNumber,FDataValue,FDescription"
            if include_status:
                field_keys += ",FDocumentStatus"
            data_content = json.dumps({
                "FormId": form_id,
                "FieldKeys": field_keys,
                "FilterString": filter_string,
                "TopRowCount": 2,
                "StartRow": 0,
                "Limit": 2,
            }, ensure_ascii=False)

            response = self._post(url, json={"data": data_content})
            response.raise_for_status()

            result = self._query_rows(response.json(), 5 if include_status else 4)
            if len(result) > 1:
                raise KingdeeDuplicateProjectCode("金蝶同类别项目编号存在重复记录，已停止同步")

            # ExecuteBillQuery 返回二维数组，字段顺序与 FieldKeys 一致。
            if result and isinstance(result, list) and len(result) > 0:
                row = result[0]
                if isinstance(row, list) and len(row) >= 2:
                    if row[1] != project_code or type(row[0]) not in (str, int) or not str(row[0]).strip() or str(row[0]) == '0':
                        raise RuntimeError('金蝶返回的项目编号或内码不符合目标，禁止写入')
                    return {
                        "FEntryID": row[0],   # 内码（用于更新）
                        "FNumber": row[1],    # 编码
                        "FDataValue": row[2] if len(row) > 2 else "",
                        "FDescription": row[3] if len(row) > 3 else "",
                        **({"FDocumentStatus": row[4]} if include_status else {})
                    }

            return None

        except KingdeeDuplicateProjectCode:
            raise
        except Exception as e:
            logger.error("查询辅助资料失败（%s）", type(e).__name__)
            raise RuntimeError("金蝶辅助资料查询失败，本次同步已停止；请检查授权及连接") from e

    def save_assistant_data(self, form_id: str, category_code: str, project_code: str,
                            project_name: str, entry_id: str = "") -> dict:
        """
        保存辅助资料（创建或更新）
        :param form_id: 表单ID
        :param category_code: 类别编码
        :param project_code: 项目编号
        :param project_name: 项目名称，写入金蝶备注
        :param entry_id: 记录内码（FEntryID），有值时为更新，空时为新建
        :return: 包含 success 和 message 的结果字典
        """
        if self.read_only:
            return {"success": False, "message": "金蝶当前为只读验证模式，未发送保存请求"}
        request_started = False
        try:
            url = f"{self.base_url}/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.Save.common.kdsvc"

            is_update = bool(entry_id)

            # 构建 Model 数据，更新时必须带 FEntryID（内码）
            model = {
                "FEntryID": entry_id,
                "FId": {"FNumber": category_code},  # 类别：销售项目
                "FNumber": project_code,
                "FDataValue": project_code,
                "FDescription": project_name
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

            request_started = True
            response = self._post(url, json=payload)
            response.raise_for_status()

            result = response.json()

            result_data = result.get("Result") if isinstance(result, dict) else None
            status = (
                result_data.get("ResponseStatus")
                if isinstance(result_data, dict)
                else None
            )
            if not isinstance(status, dict) or "IsSuccess" not in status:
                raise KingdeeSaveOutcomeAmbiguous("金蝶保存返回格式异常，需核对金蝶实际保存结果")

            is_success = status["IsSuccess"]
            if is_success is True:
                return {
                    "success": True,
                    "message": "保存成功",
                    "data": result_data,
                }
            if is_success is False:
                errors = status.get("Errors", [])
                first_error = errors[0] if isinstance(errors, list) and errors else None
                error_msg = (
                    first_error.get("Message", "未知错误")
                    if isinstance(first_error, dict)
                    else "未知错误"
                )
                return {
                    "success": False,
                    "message": f"保存失败: {self._business_error_message(error_msg)}",
                }
            raise KingdeeSaveOutcomeAmbiguous(
                "金蝶保存返回未知成功标记，需核对金蝶实际保存结果"
            )

        except KingdeeSaveOutcomeAmbiguous:
            raise
        except Exception as e:
            logger.error("保存辅助资料异常（%s）", type(e).__name__)
            if request_started:
                raise KingdeeSaveOutcomeAmbiguous(
                    "金蝶保存结果不确定，请先核对金蝶实际资料，勿直接重试"
                ) from e
            return {
                "success": False,
                "message": "金蝶保存准备失败，请检查配置"
            }

    def _operate_assistant_data(self, operation: str, form_id: str, entry_id: str) -> dict:
        """Only Submit/Audit are permitted; never automatically undo approval."""
        if self.read_only:
            return {"success": False, "message": "金蝶当前为只读模式，未发送提交或审核请求"}
        if operation not in {"Submit", "Audit"} or not str(entry_id).strip():
            return {"success": False, "message": "金蝶操作或资料内码无效，已停止"}
        label = "提交" if operation == "Submit" else "审核"
        payload = {"formid": form_id, "data": json.dumps({"Ids": str(entry_id), "Numbers": []})}
        try:
            response = self._post(
                f"{self.base_url}/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.{operation}.common.kdsvc",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            body = result.get("Result") if isinstance(result, dict) else None
            status = body.get("ResponseStatus") if isinstance(body, dict) else None
            if not isinstance(status, dict) or type(status.get("IsSuccess")) is not bool:
                raise KingdeeSaveOutcomeAmbiguous(f"金蝶{label}返回格式异常，请先回查状态，勿直接重试")
            if status["IsSuccess"]:
                return {"success": True}
            errors = status.get("Errors", [])
            first = errors[0] if isinstance(errors, list) and errors else None
            message = first.get("Message", "未知错误") if isinstance(first, dict) else "未知错误"
            return {"success": False, "message": f"保存已完成，但金蝶{label}失败：{self._business_error_message(message)}"}
        except KingdeeSaveOutcomeAmbiguous:
            raise
        except Exception:
            raise KingdeeSaveOutcomeAmbiguous(f"金蝶{label}结果不确定，请先回查实际状态，勿直接重试") from None

    def ensure_assistant_data_audited(self, form_id: str, category_code: str,
                                     project_code: str, project_name: str,
                                     *, expected_entry_id: str) -> dict:
        """Complete only missing transitions and verify persisted status and field mapping."""
        if self.read_only:
            return {"success": False, "message": "金蝶当前为只读模式，未发送提交或审核请求"}
        row = self.query_assistant_data(form_id, category_code, project_code, include_status=True)
        if (
            not row
            or not row.get("FEntryID")
            or row["FNumber"] != project_code
            or row["FDataValue"] != project_code
            or row["FDescription"] != project_name
        ):
            return {"success": False, "message": "金蝶保存后资料核对不一致，未继续提交审核"}
        entry_id = str(row["FEntryID"])
        if not expected_entry_id or entry_id != str(expected_entry_id):
            raise KingdeeSaveOutcomeAmbiguous("金蝶保存与审核资料内码不一致，已停止，请人工核对")
        for operation, from_states, to_states in (
            ("Submit", {"Z", "A", "D"}, {"B", "C"}),
            ("Audit", {"B"}, {"C"}),
        ):
            state = row.get("FDocumentStatus")
            if state == "C":
                return {"success": True, "message": "金蝶资料已审核", "entry_id": entry_id}
            if state not in from_states:
                if operation == "Submit" and state == "B":
                    continue
                return {"success": False, "message": "金蝶资料状态不支持自动提交审核，请人工核对"}
            outcome = self._operate_assistant_data(operation, form_id, entry_id)
            if not outcome["success"]:
                return outcome
            try:
                row = self.query_assistant_data(form_id, category_code, project_code, include_status=True)
            except Exception:
                raise KingdeeSaveOutcomeAmbiguous("金蝶提交或审核后回查失败，请先核对实际状态，勿直接重试") from None
            if (
                not row
                or str(row.get("FEntryID")) != entry_id
                or row["FNumber"] != project_code
                or row["FDataValue"] != project_code
                or row["FDescription"] != project_name
            ):
                raise KingdeeSaveOutcomeAmbiguous("金蝶提交或审核后资料身份发生变化，已停止，请人工核对")
            if row.get("FDocumentStatus") not in to_states:
                return {"success": False, "message": "金蝶接口返回成功，但实际提交或审核状态未生效，请人工核对"}
        return {"success": True, "message": "金蝶资料已审核", "entry_id": entry_id}

    def close(self):
        """关闭 HTTP 客户端"""
        self.client.close()


def sync_project_archive_to_erp(
    db: Session,
    archive_id: int,
    user_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
    queue_task_id: int | None = None,
) -> dict:
    """
    同步单个项目档案到金蝶 ERP
    :param db: 数据库会话
    :param archive_id: 项目档案 ID
    :return: 包含 success 和 message 的结果字典
    """
    def validate_claim(current):
        validate_archive_for_business_operation(db, current)
        if queue_task_id is not None:
            from app.models.erp_task import ErpSyncTask
            from fastapi import HTTPException
            latest = db.query(ErpSyncTask.id).filter(ErpSyncTask.archive_id == archive_id).order_by(ErpSyncTask.id.desc()).first()
            if not latest or latest.id != queue_task_id:
                raise HTTPException(409, detail={'code': 'ERP_TASK_SUPERSEDED'})
            from app.services.erp_queue import validate_task_target
            validate_task_target(db, db.get(ErpSyncTask, queue_task_id, populate_existing=True), current)

    claimed = claim_archive_for_sync(
        db,
        archive_id,
        archive_query=get_scoped_archive_query(db, scope_context),
        validator=validate_claim,
    )
    if claimed is None:
        try:
            record_operation_log(
                db,
                module="ERP同步",
                action="sync",
                entity_type="pms_project_archive",
                entity_id=archive_id,
                operator_id=user_id,
                request=request,
                status="failed",
                summary=f"同步项目档案失败：档案不存在（ID {archive_id}）",
                error_msg="项目档案不存在",
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return {"success": False, "message": "项目档案不存在"}

    archive, before = claimed
    client: KingdeeClient | None = None
    external_save_started = False

    try:
        # pending 已通过条件 mutation 独立提交，随后才允许创建客户端并访问外部系统。
        client = KingdeeClient()

        # 1. 登录金蝶
        if not client.login():
            error_msg = "金蝶登录失败，请检查配置"
            archive.erp_sync_status = "failed"
            archive.erp_error_msg = error_msg
            log = ErpSyncLog(
                source_id=archive_id,
                action="sync",
                status="failed",
                error_msg=error_msg
            )
            db.add(log)
            record_operation_log(
                db,
                module="ERP同步",
                action="sync",
                entity_type="pms_project_archive",
                entity_id=archive.id,
                entity_name=archive.project_name,
                operator_id=user_id,
                request=request,
                status="failed",
                summary=f"同步项目档案失败：{archive.project_name}",
                before_data=before,
                after_data=serialize_model(archive),
                error_msg=error_msg,
            )
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise

            return {"success": False, "message": error_msg, "retryable": getattr(client, 'login_retryable', False) is True}

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
        external_save_started = True
        save_result = client.save_assistant_data(
            form_id=form_id,
            category_code=category_code,
            project_code=archive.project_code,
            project_name=archive.project_name,
            entry_id=entry_id
        )

        # 保存不等于审核完成；失败继续由原同步与操作日志统一记录。
        if save_result["success"]:
            saved_data = save_result.get("data")
            saved_id = saved_data.get("Id") if isinstance(saved_data, dict) else None
            if type(saved_id) not in (str, int) or not str(saved_id).strip() or str(saved_id) == "0":
                raise KingdeeSaveOutcomeAmbiguous("金蝶保存成功但未返回有效内码，请回查资料，勿直接重试")
            if entry_id and str(saved_id) != entry_id:
                raise KingdeeSaveOutcomeAmbiguous("金蝶保存返回的内码与目标不一致，请人工核对")
            # External identity exists even if the subsequent audit is rejected.
            archive.erp_synced = 1
            save_result = client.ensure_assistant_data_audited(
                form_id, category_code, archive.project_code, archive.project_name,
                expected_entry_id=str(saved_id),
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
            record_operation_log(
                db,
                module="ERP同步",
                action="sync",
                entity_type="pms_project_archive",
                entity_id=archive.id,
                entity_name=archive.project_name,
                operator_id=user_id,
                request=request,
                summary=f"同步项目档案成功：{archive.project_name}（{action}）",
                before_data=before,
                after_data=serialize_model(archive),
            )
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise

            return {"success": True, "message": f"同步成功，金蝶已审核（{action}）"}
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
            record_operation_log(
                db,
                module="ERP同步",
                action="sync",
                entity_type="pms_project_archive",
                entity_id=archive.id,
                entity_name=archive.project_name,
                operator_id=user_id,
                request=request,
                status="failed",
                summary=f"同步项目档案失败：{archive.project_name}",
                before_data=before,
                after_data=serialize_model(archive),
                error_msg=save_result["message"],
            )
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise

            return save_result

    except Exception as e:
        db.rollback()
        redact = getattr(client, '_redact_message', None)
        error_msg = f"同步异常: {redact(str(e)) if callable(redact) else '后台执行失败，请核查连接及实际结果'}"
        archive = (
            get_scoped_archive_query(db, scope_context)
            .populate_existing()
            .filter(PmsProjectArchive.id == archive_id)
            .first()
        )
        if archive is None:
            return {"success": False, "message": "项目档案不存在"}
        if external_save_started:
            try:
                log = ErpSyncLog(
                    source_id=archive_id,
                    action="sync",
                    status="failed",
                    error_msg=error_msg,
                )
                db.add(log)
                record_operation_log(
                    db,
                    module="ERP同步",
                    action="sync",
                    entity_type="pms_project_archive",
                    entity_id=archive.id,
                    entity_name=archive.project_name,
                    operator_id=user_id,
                    request=request,
                    status="failed",
                    summary=f"同步项目档案结果不确定：{archive.project_name}",
                    before_data=before,
                    after_data=serialize_model(archive),
                    error_msg=error_msg,
                )
                db.commit()
            except Exception:
                db.rollback()
            return {"success": False, "message": error_msg}

        archive.erp_sync_status = "failed"
        archive.erp_error_msg = error_msg

        log = ErpSyncLog(
            source_id=archive_id,
            action="sync",
            status="failed",
            error_msg=error_msg
        )
        db.add(log)
        record_operation_log(
            db,
            module="ERP同步",
            action="sync",
            entity_type="pms_project_archive",
            entity_id=archive.id,
            entity_name=archive.project_name,
            operator_id=user_id,
            request=request,
            status="failed",
            summary=f"同步项目档案异常：{archive.project_name}",
            before_data=before,
            after_data=serialize_model(archive),
            error_msg=error_msg,
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        return {"success": False, "message": error_msg, "retryable": isinstance(e, (httpx.TimeoutException, httpx.NetworkError))}

    finally:
        if client is not None:
            client.close()


def batch_sync_project_archives(
    db: Session,
    archive_ids: list[int],
    user_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
) -> dict:
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
        try:
            result = sync_project_archive_to_erp(
                db,
                archive_id,
                user_id=user_id,
                request=request,
                scope_context=scope_context,
            )
        except HTTPException as exc:
            if not isinstance(exc.detail, dict) or exc.detail.get("code") != "ARCHIVE_DISABLED":
                raise
            result = {"success": False, "message": exc.detail["message"]}
        if result["success"]:
            success_count += 1
        else:
            failed_count += 1
            errors.append(f"ID {archive_id}: {result['message']}")

    occupancy_errors = [error for error in errors if "金蝶当前单据被占用。" in error]
    message = f"批量同步完成：成功 {success_count}，失败 {failed_count}"
    if occupancy_errors:
        message += "；" + "；".join(occupancy_errors)

    result = {
        "success": True,
        "message": message,
        "success_count": success_count,
        "failed_count": failed_count,
        "errors": errors
    }
    record_operation_log(
        db,
        module="ERP同步",
        action="batch_sync",
        entity_type="pms_project_archive",
        operator_id=user_id,
        request=request,
        status="success" if failed_count == 0 else "failed",
        summary=result["message"],
        after_data={"archive_ids": archive_ids, **result},
        error_msg="；".join(errors) if errors else None,
        commit=True,
    )
    return result


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
    client: KingdeeClient | None = None
    try:
        client = KingdeeClient()
        if client.login():
            return {"success": True, "message": "金蝶连接测试成功"}
        else:
            return {"success": False, "message": "金蝶认证失败，请检查认证模式、应用授权、账套及用户权限"}
    except Exception:
        return {"success": False, "message": "金蝶连接异常，请检查认证与连接配置"}
    finally:
        if client is not None:
            client.close()
