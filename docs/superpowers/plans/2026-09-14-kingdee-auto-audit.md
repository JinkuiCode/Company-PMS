# 金蝶自动审核实施计划

> 执行方式：本任务 inline executing-plans；复用已有批准，不另建工作区。

**Goal:** PMS 同步保存后完成金蝶提交审核，回查已审核才返回成功。
**Architecture:** 保留低层 Save；新增状态查询与 ensure_assistant_data_audited，复用签名传输及日志，明确状态转换与结果不确定保护。
**Tech Stack:** FastAPI/Python、httpx、官方金蝶 SDK、SQLAlchemy。

## 约束

仅 I0001；目标类别 xsxm；生产仅批准样本；不反审核、不绕过权限、不推送合并；验收后只读。沿用已批准规格。

## Task 1：行为契约与实现

- [x] 写 backend/tests/kingdee_auto_audit_contract.py：A→B→C、B→C、已C不重复提交审核、只读不联网、Submit失败停止、Audit失败停止、未知状态/重复记录/内码漂移停止、业务200失败、超时不重试、仅保存不能标记同步成功。
- [x] 执行新测试，确认缺少 ensure 方法/集成导致 RED。
- [x] kingdee.py 的 query_assistant_data 增加可选 include_status=False；True 时 FieldKeys 多取 FDocumentStatus 并严格要求4列，原默认返回不变。
- [x] 增加受限 Submit/Audit 调用及状态驱动的 ensure_assistant_data_audited(form_id,category_code,project_code,project_name)，状态回查内码和名称一致才成功；网络不确定沿用 KingdeeSaveOutcomeAmbiguous。
- [x] 在同步 Save 成功分支调用 ensure，失败转入既有失败日志路径，不能更新 success 状态。
- [x] 新测试 GREEN；回归 app_auth、query_scope、project_archive_lifecycle、并发、operation_log；必要时只更新成功客户端测试替身实现审核成功语义。

测试运行：`PYTHONPATH=. /Users/jin/Code/PMS/backend/.venv311/bin/python tests/kingdee_auto_audit_contract.py`，其它契约同方式执行；各退出0。

## Task 2：现场测试与审查

- [x] 测试账套读取状态字段，验证对已有测试样本执行提交审核；回查C与内码。
- [x] 测试已审核样本正常更新，确认状态结果；不执行反审核。
- [x] 测试新建唯一测试样本后自动提交审核，回查C。
- [x] 复查代码错误处理、只读及样本边界；处理阻断意见。

## Task 3：发布与交付

- [x] 只读验证正式当前PID/版本/配置/待同步，备份受影响代码，按明确文件列表发布、测试与重启，失败恢复旧程序并验证。
- [x] 正式仅对既有样本进行提交审核，回查内码、名称和C；同账号正常PMS接口记录操作与同步结果。
- [x] 停止临时限时入口，恢复普通只读服务并验证健康、拒绝联网前写入；清理临时传输。
- [x] 完成 SOP、change.md、脱敏验收记录；文档差异检查。保留工作区，不推送或合并。

已完成：用户退出占用后生产样本补审为 C，成功增量日志 34/75；恢复只读 PID 6576，SOP 和记录已更新。占用提示随后已获批并完成发布；最终生产日常同步已于 14:35 开放，以 SOP 5.0 为准。
