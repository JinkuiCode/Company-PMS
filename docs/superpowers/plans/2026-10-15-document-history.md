# 单据日志与管理员审计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用户在有权查看的单据中读取所有人的业务操作记录；管理员使用已批准的标准审计列表和并排详情。

**Architecture:** 统一操作底账增加无外键的主单关联及中文差异快照；独立资源适配与安全投影服务输出业务记录，管理员接口继续独立。前端独立document-history模块先接档案，再接进度／任务及支持提报；保留已批准时间线、字段对照和状态。

**Tech Stack:** FastAPI、SQLAlchemy、Pydantic、Vue3、现有标准查询／列表／表单和日志服务。

## Global Constraints

- 采用已定稿规范及样稿，不给业务用户全局日志权；无实体授权404，字段隐藏及脱敏应用于前后值、摘要、关联申请和技术输出。
- 删整单只留管理员审计；父单存在时子记录删除可追溯。操作者快照与主单关联不依赖级联外键。
- 成功日志与业务同事务，无变化不生成修改日志；失败、越权另在回滚后独立短事务并限流，不采集凭据或请求正文。
- 首期保留全部，不清理、不加日志导出。新事件保存中文名称快照，旧事件没有的历史名称不伪造。
- 模型变更统一纳入governance-01限定升级及契约，实际库升级仍需备份校验和独立批准；此阶段仅内存／临时数据库验证。

## Task 1：底账与安全业务读取

**Files:** Modify `backend/app/models/operation_log.py`、`services/operation_log.py`；Create `services/operation_log_metadata.py`、`services/document_history.py`、`api/document_history.py`、`schemas/document_history.py`、`tests/document_history_contract.py`；Register API in `backend/main.py`。

**Interfaces:**
- 底账新增可空`root_entity_type`、`root_entity_id`、`diff_items_data`与主单索引；旧行保持兼容、不伪造历史标签。
- `resolve_log_root(db, entity_type, entity_id, before, after)`：档案申请→档案，任务→项目，提报子记录→提报，其余记录→自身，无法证明来源时不猜测。
- `get_document_history(db, resource, entity_id, scope, *, page=1, page_size=50, action=None)`：先实体和动作授权，再查询、计数、分页，返回安全`items/total/actions`。
- GET `/api/document-history/{resource}/{entity_id}`，资源白名单archive/project/task/feedback，动态资源适配各自view及范围，始终使用当前授权上下文。

- [x] 行为测试先证明原路由缺失：非全局管理员可读当前单据其他人记录；跨产品线／撤权／删除根实体404；隐藏字段连摘要都不泄露；审批关联不漏；新事件引用名重命名仍保留原显示；无原始快照/IP/异常；分页及操作筛选正确。
- [x] 统一record服务递归脱敏及文本凭据清理，捕获主单和中文字段快照；审批提交引用现有请求差异，不把updates_json／differences_json整段送业务用户；普通修改前后快照完全相同不写事件；仅更新时间变化尚未统一去除。
- [x] 业务投影只返回操作者快照、时间、中文动作／结果、受控摘要和可见中文差异；不返回before/after原始JSON、错误、IP或请求信息。旧日志从可证明实体关系关联，不能用用户传的entity_type构造任意查询。
- [x] 新契约GREEN、原operation_log、字段目录／枚举、档案维护／审批、项目范围回归。

## Task 2：共享时间线和档案试点

**Files:** Create `frontend/src/document-history/PmsDocumentHistory.vue`（独立模块内聚类型、请求和样式，未拆成四个仅供单组件使用的文件）；Modify `ProjectArchive.vue`、页面说明；Create独立浏览器契约。

- [x] 浏览器测试先失败：档案详情业务信息默认、操作记录页签、其他人事件、中文差异展开、操作筛选、分页／空／错误重试／拒权、快速切档案不混记录。
- [x] 从已批准DocumentHistory样稿提取独立模块，使用PMS主题和控件，真实API数据代替合成模型。请求票据在实体、筛选、页码变化及卸载时失效；失败／拒权先清旧数据；保留键盘语义和窄窗口。
- [x] 档案抽屉加入业务信息／操作记录页签，默认业务信息，切档案复用主从保护；日志浏览不触发编辑，普通业务信息及维护／审批入口保留。

## Task 3：管理员审计及覆盖

**Files:** Modify `frontend/src/views/system/OperationLogList.vue`、`page-guide`及相应契约；Modify `backend/app/services/project.py`、认证/SSO、后台导出及统一异常审计适配。

- [x] 管理员审计按已批准样稿排列时间、模块、操作者、单据、动作、结果、摘要、详情；复用标准查询和分页，技术信息折叠、详情并排及主从切换。动态中文动作由后端目录提供，不再维护前端重复翻译。
- [x] 项目级联删除保存完整任务快照；SSO自动开户／姓名变更补同事务快照；后台过程实际结果写统一日志，排队不冒充成功。
- [x] 失败审计模块只记录固定原因分类、模板路径及必要身份，回滚后独立提交；服务内和入口之间避免递归及重复自动重试，限流只合并审计事件、不影响真实业务响应。
- [x] 单据模块按已登记写入路径分批接入；完成的逐项记录，未接入不得标完成。完整前后端必需检查、浏览器与独立安全审查后更新change.md和覆盖矩阵。

本计划中的新增结构与V1通知表一起进入统一限定升级；升级批准前代码／隔离验收继续，真实页面数据库验收暂停。回退材料保留旧表兼容及原始日志，不删审计底账。

## 2026-10-15开发验证结论

以上勾选表示代码、隔离契约、模拟接口浏览器及独立审查完成，不代表真实账号授权、数据库升级或正式发布完成。详见[本批验证与覆盖记录](../../releases/2026-10-15-governance-development-validation.md)。实际数据库升级、现场用户闭环和真实邮件投递仍待独立批准。
