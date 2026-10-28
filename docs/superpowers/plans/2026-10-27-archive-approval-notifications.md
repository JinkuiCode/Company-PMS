# P20 档案审批通知 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: executing-plans. 按下列复选项在当前聊天顺序实施；不启用子代理。

**Goal:** 依照已批准的设计 v1，交付独立工作区内可验证的审批站内通知、邮件队列和原申请定位入口。
**Architecture:** 原审批事务加入个人事件与邮件记录；当前权限过滤个人查询；独立线程领取邮件，未知结果禁止自动重发；统一通知窗口复用原升级中心。
**Tech Stack:** FastAPI / SQLAlchemy / SQLite 隔离测试 / MSSQL 2017 编译；Vue 3 / Pinia / Element Plus / Playwright。

## Global Constraints

- 批准：call_5660959d3d6f40cdb0711e9e65420cda/0；设计文件 `../specs/2026-10-27-archive-approval-notifications-design.md` 为唯一实现基线。
- 基线 master 53ae325c8556890040af11d9cc40b1bd2b50b664；分支 codex/archive-approval-notifications；主目录最新 AGENTS.md 优先于本分支旧规则。
- 正式通知窗口已获批准；用户明确排除外层介绍及预览控制页，按此集成。无生产、实际角色授权、真实邮件、提交、合并或推送。
- 全部后端测试使用临时数据库和模拟邮件/ERP；复用启动脚本的 Python 3.12 与既有依赖，不修改公共环境。
- 验证 RED 必须是目标缺失/行为错误，导入或环境失败先修测试环境。各批只添加必要逻辑，不重构既有发布/提报队列。

## 1. 基线与样稿

- [x] 建立工作区并固定批准、基线和分支；前端三个既有样式契约通过。
- [x] 运行 `tests/archive_change_contract.py`、`tests/release_mail_contract.py`，记录现有审批和邮件基线。
- [x] 新增 `frontend/tests/approval-notification-prototype-browser.mjs`，先验证缺失样稿的 RED。
- [x] 新增 `frontend/prototypes/approval-notifications/{index.html,main.ts,Prototype.vue}`，共享主题/表单/字体，不加载正式 API；覆盖正常、四种审批状态、未读、加载、空、失败、无权、邮件状态、键盘、三主题与窄窗。
- [x] 用本机独立端口浏览器验证及截图，展示可交互样稿并请求仅 UI 样稿批准。

## 2. 事务、读取与详情权限

- [x] 新增 `backend/tests/business_notice_contract.py`，先 RED：提交/决策唯一消息、回滚、撤回无新增、直接修改无消息、用户隔离、撤权、数据范围、精确详情与已读日志。
- [x] 新增 `backend/app/models/business_notice.py`：两表、事件版本/收件人唯一约束、邮件一对一及领取索引；在 `models/init_db.py` 注册。
- [x] 新增 `services/business_notices.py`，复用当前授权与档案范围；事务内 `queue_archive_notice` 不 commit；个人列表/详情/已读均重新构建有效授权；人员关系失效隐藏。
- [x] `services/archive_change.py` 的 submit/approve/reject 在原 commit 前排队，withdraw 不生成事件；`api/archive_changes.py` 增加有范围及人员关系检查的 GET requests/{id}。
- [x] 新增 `api/business_notices.py`：个人列表、详情、已读、范围内管理投递和重试接口；Schema 输入限制与统一 RBAC。
- [x] GREEN 并回归原审批/维护/发布契约。

## 3. 邮件交付

- [x] 新增 `backend/tests/business_notice_mail_contract.py` RED：配置关闭、无邮箱、当前权限/状态失效、CAS 争抢、已接受、明确临时拒绝最多三次、未知不重试、过期 processing、重试原因/权限/日志。
- [x] 新增 `services/business_notice_mail.py`，复用 feedback_mail.configuration/send_mail，发送前再次检查有效身份及原锁定审批关系；固定 Message-ID；最小正文与可信配置链接。
- [x] 新增 `PMS_BUSINESS_NOTICE_MAIL_WORKER_ENABLED=False`，在 `main.py` 独立启停；开发不启用真实投递。受控重试沿用同一记录。
- [x] GREEN；日志只记录状态等脱敏元数据，不保存 SMTP 凭据或完整正文。

## 4. 数据库升级与目录

- [x] 新增 `backend/tests/business_notice_migration_contract.py` RED：旧版限定升级/新库/重复升级/部分结构拒绝/启动只检查/权限无自动授予/MSSQL 约束编译。
- [x] 新增 `services/business_notice_migration.py`；前置 archive-policy-01，目标 archive-notice-01；验证两表列/索引/唯一约束/外键及两个权限节点，复用已有 MSSQL UQ 检查。
- [x] 修改 `services/database_revision.py`、`scripts/upgrade_database.py` 增加专用升级参数；新库初始化注册权限但不分配任何角色；`role_templates.py` 手动权限边界核对。
- [x] 修改 `services/field_catalog.py` 和 `operation_log.py` 的实体/状态中文目录；系统固定协议值不进入业务枚举。
- [x] GREEN，并运行字段目录、枚举、版本/启动契约。

## 5. 样稿批准后集成正式界面

- [x] 新增 `frontend/src/business-notices/` 的接口、store、窗口及样式；每频道独立错误；加载/焦点/60秒可见轮询；切换用户及退出清空，旧响应不得回写。
- [x] 顶栏 `layout/AppLayout.vue` 一个铃铛，业务消息/升级通知切换；原 ReleaseCenter 和 About 行为保留。
- [x] `ProjectArchive.vue`、`ArchiveChangeList.vue` 接入申请 ID 深链；复用 createDetailSwitch 草稿保护和旧响应防护；不可访问仅通用提示。
- [x] `page-guide/registry.ts` 注册共享说明，范围内管理信息按需展开；控制按钮使用共享语义色和表单控件。
- [x] 新增行为测试先 RED 后实现：只读不审批、已读失败、键盘、快速切换、伪造 ID、退出重入、频道失败、刷新/分页；更新旧 release-center-browser 测试。

## 6. 最终验证与交付

- [x] 前端：style-contract、list-standard-contract、system-ui-consistency-contract、archive-filter-contract、data-dictionary-contract、enum-management-contract、npm run build 与本批浏览器行为测试。
- [x] 后端：新增三组契约及受影响审批/维护/数据库版本/日志/字段枚举契约；测试真实目标行为，不用静态字符串代替授权或事务验证。
- [x] 自审差异与 spec v1 逐项比对；记录真实 MSSQL、Windows、SMTP 未验证边界。
- [x] 更新本工作区 change.md（实际实现、文件、验证），更新主目录唯一待办和私有连续性证据；不提交 Git。
- [x] 执行主目录 ops/check_work_continuity.py，确认剩余批准工作已完成或具体输入阻塞后交付候选。

## 自审

本计划未扩大获批范围；样稿与正式界面的批准门分开，所有后端工作可在等样稿时执行。投递语义使用“服务器已接受”，不以固定 Message-ID 假称严格仅一次。外部环境验收不能由本地编译替代。

## 本机交付状态

2026-10-27：14 组后端、11 组前端检查均通过；新增三组后端共 38 项。见 `docs/records/2026-10-27-approval-notifications-local.md` 及私有最终验证清单。真实 Windows／MSSQL／SMTP 和正式发布不在本次本机交付内；Git 未提交。
