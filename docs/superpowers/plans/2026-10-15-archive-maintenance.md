# 档案临时维护实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 指定人员经明确、可撤销的维护授权，在现有数据范围内填写原因、核对差异并直接保存单条档案，保留原普通编辑及审批流程。

**Architecture:** 独立`archive_maintenance`服务复用档案行锁、版本、字段及归属校验；原抽屉增加显式维护模式并复用已有差异确认。权限节点在后续统一限定升级中注册，不默认授予任何角色，不隐式改变真实授权。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy、Vue3、统一表单控件和当前档案抽屉。

## Global Constraints

- 以统一开发规范第十一节及用户“通过”“可以启动方案开发”为授权；继续同一功能分支。维护仅限单条，无批量、代审批、自动到期、金蝶组织迁移。
- 每次服务检查`project:archive:view`、`project:archive:edit`、`project:archive:maintain`，并使用当前实体与目标归属范围。admin与business:data:all不隐含维护授权。
- 缺负责人历史档案允许在明确范围内修复；变更新负责人时必须有有效用户／部门／部门负责人，不自动修人员资料；不追溯强制补齐其他历史缺项。
- 禁用、待审批、同步pending/review拒绝，版本不符409；编号、组织、字段规则、唯一性及引用只读沿用。维护只替代该入口的负责人身份／部门审批。
- 前后值、原因及权限依据与业务同事务，日志动作maintain；维护引发原自动同步时保存maintain＋view＋edit来源，不改变历史manual策略。
- 本批不执行真实授权、数据库升级、金蝶写入、提交、合并、推送或部署。

## Task 1：独立服务与接口

**Files:** Create `backend/app/services/archive_maintenance.py`、`backend/app/schemas/archive_maintenance.py`、`backend/tests/archive_maintenance_contract.py`；Modify `backend/app/api/projects.py`、`services/project.py`、`services/archive_change.py`、`schemas/project.py`。

**Interfaces:**
- `ArchiveMaintenanceRequest(updates: ArchiveUpdate, expected_version: str, reason: str)`，拒绝空白原因和额外信封字段。
- `maintenance_context(archive, scope, pending) -> dict`提供can_maintain及不可用原因，不改变can_edit。
- `preview_archive_maintenance(db, archive_id, data, actor, *, scope_context)`返回服务端中文differences及expected_version；仅预检，结束回滚释放锁。
- `maintain_archive(db, archive_id, data, actor, *, scope_context, request=None)`最终重新锁定／验证，直接提交，输出mode=maintenance及原sync_queued。
- POST `/api/projects/archives/{id}/maintenance/preview`及PUT `/api/projects/archives/{id}/maintenance`，路由依赖maintain，服务仍检查全部三个动作。

- [x] 用已有ArchiveChangeContract内存夹具写真实API行为测试，先观察404/元数据缺失。覆盖非负责人获授权可维护、普通编辑仍403、缺权限／跨产品线拒绝、空原因422、待批/禁用/同步锁/版本冲突拒绝、无变化不记日志、补负责人有效链、已同步编号不可改、失败事务回滚及自动/手动同步来源。
- [x] 独立服务依次调用动作校验、当前用户匹配、`_claim_enabled_archive_for_write`、`_check_version`、`_ensure_no_active`和`apply_archive_updates(..., dry_run=True)`。若更新manager_id，查询有效用户/部门/负责人；不完整返回field_key=manager_id的422。差异由统一日志服务生成。
- [x] 共享apply服务新增仅内部参数`audit_action='update'`、`audit_summary=None`、`audit_extra=None`、`queue_permission=None`，保持普通调用原语义。维护传maintain动作、原因和授权依据；元数据同时加入before/after避免制造非业务差异。queue_permission由服务端指定，API不开放。
- [x] 接口GREEN；执行原审批16项、项目范围、队列授权、生命周期、字段目录／枚举契约。权限节点尚未注册时，实际账号不能提前使用；不声称真实维护已启用。

## Task 2：复用档案抽屉与确认差异

**Files:** Modify `frontend/src/views/project/ProjectArchive.vue`、`frontend/src/page-guide/registry.ts`；Create `frontend/tests/archive-maintenance-browser.mjs`及对应行为／界面契约。

- [x] 浏览器隔离请求样本先验证：普通查看无维护入口；获维护元数据时查看抽屉底部可进入维护，进入后统一字段可编辑；原因为空不能保存，服务端差异确认后调用maintenance接口；普通审批依旧走原接口。
- [x] 扩展抽屉模式为显式maintenance，保留已有控件、字体、间距、差异弹窗及主从草稿保护；仅新增维护入口及维护模式文案，原因复用确认弹窗统一长文本控件。不在表格增加一排新重色按钮。
- [x] 切换单据、关闭、请求失败及撤权时清理旧模式／保留正确草稿，旧异步结果不得应用到新档案；保存失败不关闭。维护按钮及编辑元数据由同一权限来源决定。
- [x] 更新说明的普通编辑／维护／审批区别与日志内容。前端三项规范契约、archive-filter、字段目录／枚举及build通过；实际浏览器核对维护、普通审批、键盘及窄窗口。

## Task 3：独立权限注册与验收边界

- [x] 在统一governance限定升级内新增维护按钮节点，首次也不授给admin或模板角色；验证重复升级不补回人工撤权。该升级与版本／日志结构合并准备，一次备份并独立批准实际执行。
- [x] 独立代码审查，更新总跟踪和change.md；若实际开发库未升级或账号未授维护权，保留隔离API及浏览器证据，明确现场待验，不通过篡改账号或版本号绕过。

回退为本批独立程序差异及配套固定旧包；维护产生的真实业务数据须按具体备份／前后值处理，不承诺撤程序会自动撤销数据。当前未修改实际业务库。

## 2026-10-15开发验证结论

以上勾选表示代码、隔离契约、模拟接口浏览器及独立审查完成，不代表真实账号授权、数据库升级或正式发布完成。详见[本批验证与覆盖记录](../../releases/2026-10-15-governance-development-validation.md)。实际数据库升级、现场用户闭环和真实邮件投递仍待独立批准。
