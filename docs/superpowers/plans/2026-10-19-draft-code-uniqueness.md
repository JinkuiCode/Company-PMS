# 草稿与正式档案编码唯一性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. User approved Mac implementation/verification of the selected global uniqueness rule; no production, actual DB upgrades or Git operations.

**Goal:** 正式档案及所有未提交草稿之间不能重号，排除当前记录；失败保留输入且不泄露他人资料。

**Architecture:** 共享编码服务沿用正式档案的 `strip().casefold()` 规范及数据库比较语义。MSSQL事务应用锁、SQLite写事务保护检查至提交；草稿保存调用统一检查，正式档案ORM身份维护调用相同检查，覆盖正式新增、改号和既有ORM导入路径；草稿转正式在同一锁及事务内先标记使用，失败全部回滚。复用现有字段错误显示，区分编码冲突与草稿版本冲突。

**Tech Stack:** SQLAlchemy / MSSQL 2017 / SQLite / FastAPI / Vue 3。

## Global Constraints

- 用户选择“正式档案＋所有未提交草稿之间都不能重号”；只在Mac代码及隔离库、模拟页面验证。
- 不改数据库结构、权限、OA/ERP接口或真实数据，不重启常用后端，不部署、提交、合并、推送或通知。
- 不自动改写、清理历史重号草稿；当前草稿排除自身，历史重号在下次保存时明确拦截；正式保存仍须完整校验。
- 只返回“项目编号已存在，请更换编号”，不返回占用记录、用户、名称或产品线。
- 复用当前目录与功能分支；保留上一批采购及其他既有资料。

## Task 1: 跨草稿与档案的统一检查

Files: `backend/app/services/archive_code_unique.py`（新增）、`backend/app/models/project.py`现有身份事件、`backend/app/services/form_drafts.py`、`backend/tests/form_draft_unique_contract.py`（新增）及草稿测试夹具。

- [x] 实际API测试先RED：正式档案碰撞、全员/跨产品线草稿碰撞、自身重存、改号/删除释放、转正式成功及失败回滚、普通新增与ORM导入不能抢占草稿、错误不泄露内容。
- [x] 实现 `ensure_code_available(connection, code, *, exclude_draft_id=None, exclude_archive_id=None)`，事务锁覆盖查重至提交；身份事件只在新增/编码变化时调用，其他字段维护不因此受阻。
- [x] 补文件SQLite双连接并发与MSSQL锁参数/失败关闭契约。任意失败不返回成功、不保留部分修改或额外日志。

## Task 2: 用户纠错、说明与收尾

Files: `frontend/src/form-system/usePersistentDraft.ts`、`frontend/tests/persistent-draft.test.mjs`、草稿隔离浏览器测试、`frontend/src/page-guide/registry.ts`、原草稿规格和`change.md`。

- [x] 先RED验证编码409不误判版本冲突；修改编号后原草稿可继续保存，输入/身份/版本不丢失；真正版本冲突仍锁定。
- [x] 保留现有布局和字段控件，仅复用现有编码字段错误；更新我的草稿及管理页说明。
- [x] 执行草稿、档案唯一性/权限/导入相关后端契约；前端持久化草稿测试、三项必需规范、说明与构建；隔离页面验证失败留值与改号重试。
- [x] 审查本轮差异，完成实际变更记录和证据，运行连续性检查。本轮不做Git或正式发布。

## 本机验收结果

15组独立后端检查全部退出0；前端行为7项、必需规范、说明和构建通过，隔离浏览器流程通过。独立审查 Important 已修复并复审关闭。附加3组旧夹具失败已在HEAD独立副本重现，未修复无关范围。真实MSSQL驱动/排序规则/并发验证留待上线前单独隔离演练。结果位于 `outputs/draft-code-unique-20261019/`，无正式环境/Git/真实库动作。
