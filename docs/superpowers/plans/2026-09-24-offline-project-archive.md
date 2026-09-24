# 线下项目档案实施计划
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 接入第四版历史档案，提供手动同步及产品线批量分配，停用产品类别。
**Architecture:** 扩展现有档案模型、统一字段规则和队列策略。独立 offline_archive 服务负责预检、批次事务与回退，复用当前权限与日志。
**Tech Stack:** FastAPI / SQLAlchemy / Vue3 / TypeScript / MSSQL；测试 SQLite。

## Global Constraints
- 书面规格：docs/superpowers/specs/2026-09-24-offline-project-archive-design.md 已批准。
- 工作区：/Users/jin/.codex/worktrees/pms-offline-archive/PMS，分支 codex/pms-offline-archive，从 master 创建。
- 不修改报表任务工作区；不实际升级共享数据库、不导入业务数据、不调用金蝶、不推送或合并。
- 数据库版本须提升并通过独立升级测试；来源和同步策略不允许由普通写入接口伪造。
- 3024条唯一编码为输入基线；产品线为空；保留人员/部门与按钮权限。
- 每个任务先运行新增行为测试观察失败，修改后回归。提交只包含本任务文件，不包含输入工作簿或客户资料。

## Task 1: 字段、来源、同步策略与独立升级
Files: backend/app/models/project.py, backend/app/schemas/project.py, backend/app/services/offline_archive_fields.py (new), backend/app/services/offline_archive_migration.py (new), backend/app/models/init_db.py, backend/app/services/database_revision.py, backend/tests/offline_archive_contract.py (new).
Interfaces: OFFLINE_FIELDS 描述新增类型；upgrade_offline_archive(engine) 幂等新增列；普通接口只能写业务字段。
- [x] RED: 测试新增字段在模型/Schema中存在、旧表连续升级两次保持auto、offline_initial+manual保存名称不入队。
```python
self.assertIn("erp_sync_policy", PmsProjectArchive.__table__.columns)
self.assertIn("archive_category", ArchiveUpdate.model_fields)
self.assertEqual(db.query(ErpSyncTask).count(), 0)
```
- [x] 模型新增可空业务列，erp_sync_policy使用auto数据库默认。明确offline_initial为历史来源。
- [x] 注册枚举、字段治理及字段目录；新枚举通过初始化与引用计数进入现有管理。
- [x] 普通创建/更新拒绝已停用product_category；历史空名称允许维护其他字段。
- [x] GREEN: Python tests/offline_archive_contract.py，以及既有archive_business_fields、field_policy、field_catalog、enum_management契约。

## Task 2: 手动同步与产品类别停用
Files: backend/app/services/project.py, erp_queue.py, authorization.py, auth.py, rbac.py, enum_registry.py, project_sheet_fields.py; backend/app/api/erp.py; backend/app/schemas/rbac.py; frontend对应auth类型。
Interfaces: enqueue(..., explicit=False)默认拒绝manual隐式入队；request_archive_sync(db, archive_id, user_id, scope_context, request=None)验证后显式入队。
- [x] RED: manual改名无任务、显式同步入队一次、缺产品线拒绝；auto保持原行为；类别写入422。
```python
with self.assertRaises(HTTPException): request_archive_sync(db, archive.id, user.id, scope)
self.assertFalse(result["sync_queued"])
```
- [x] 在档案保存处区分策略，并在队列入口增加第二道防线；手动入口先持有生命周期锁、验证同步字段、再入队和写日志。
- [x] 清理类别授权上下文/依赖及角色写入入口，保留数据库历史值；字段目录标为停用；前端隐藏旧类别。
- [x] GREEN: offline_archive、erp_queue、product_line_project_scope、all_business_data、权限相关契约。实际ERP调用用受控替身，不发送生产请求。

## Task 3: 预检、批次导入、回退与批量产品线
Files: backend/app/models/archive_import.py (new), backend/app/services/offline_archive.py (new), backend/app/api/offline_archives.py (new), backend/main.py, backend/app/schemas/offline_archive.py (new), backend/tests/offline_archive_import_contract.py (new).
Interfaces: preview_import(db, payload, scope); apply_import(db,payload,user_id,scope); rollback_import(db,batch_id,user_id,scope); assign_product_line(db,payload,user_id,scope).
- [x] RED: 同一文件幂等；碰撞不覆盖；事务失败不留半批；manual零任务；未分配产品线普通用户无权访问；回退阻止修改/引用/同步行。
```python
self.assertEqual(apply_import(db, payload, user.id, scope)["created"], 2)
self.assertEqual(apply_import(db, payload, user.id, scope)["created"], 0)
self.assertEqual(db.query(ErpSyncTask).count(), 0)
```
- [x] 输入固定列的结构化行及来源ID，后端自行生成标准内容摘要；预检只读，应用再次校验事务内唯一性。批次和明细保存版本摘要与来源，不存凭据。
- [x] 枚举映射只接受明确注册选项，不按近似名称合并；非法值预检结构化返回；批准基线的空值保留。
- [x] 管理员动作要求明确business:data:all及独立按钮权限；批量分配逐行锁定、检查expected_updated_at和组织锁，不触发队列。
- [x] GREEN: import行为契约及迁移契约；临时库演练3024行不发送ERP。

## Task 4: 页面与操作验收
Files: frontend/src/views/project/ProjectArchive.vue, frontend/src/api/project.ts, frontend/src/views/project/ProjectList.vue, frontend/src/composables/useEnumOptions.ts, frontend/tests/offline-archive-contract.test.mjs (new); docs/金蝶第三方应用对接SOP.md; change.md.
Interfaces: 新字段通过统一元数据和枚举控件展示；列表及详情手动同步、选中行批量归属；导入预检先展示统计与阻断，再应用。
- [x] RED: 前端契约验证新增字段、手动同步文案及旧类别停用；纯函数测试导入列转换和空值。
- [x] 复用标准控件与统一表单，保留现有主从切换和编辑行为。后台失败保留输入并展示原因。
- [x] GREEN: node tests/style-contract.test.mjs、list-standard-contract.test.mjs、system-ui-consistency-contract.test.mjs、archive-filter-contract.test.mjs、data-dictionary-contract.test.mjs、enum-management-contract.test.mjs；npm run build。
- [x] 页面验收显示、编辑、错误、禁用、无权限，验证普通新增仍自动同步、本批手动策略不变。
- [x] 独立升级临时库演练、更新SOP及change.md；检查本任务diff，交付验证结果与正式升级/导入待批准清单。

## Baseline
2026-09-24: archive_business_fields_contract 11 passed；product_line_project_scope_contract 14 passed。使用项目 .venv-deps312 与 bundled Python3.12；最初旧venv缺argon2为环境选择问题，未修改依赖或程序。

## 交付状态
2026-09-24：任务1至4在独立分支完成。详情见 docs/releases/PMS线下项目档案开发验收记录-20260924.md。未执行真实MSSQL升级、实际业务导入、ERP写入或GitHub推送/合并；这些是已明确分离的发布边界。
