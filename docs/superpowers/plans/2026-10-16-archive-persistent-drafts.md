# 项目档案服务器草稿 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 新增档案支持多份本人草稿，跨会话恢复，冲突不覆盖，正式保存事务内转档。

**Architecture:** 独立PmsFormDraft存储及form_drafts服务，archive-create适配负责白名单、字段规则和数据范围。新草稿接口复用实时权限；create_archive增加commit=False以支持原子转档。前端通过独立草稿适配复用现有抽屉/表单会话。

**Tech Stack:** FastAPI、SQLAlchemy、SQLite/MSSQL2017、Vue3、TypeScript、ElementPlus。

## Global Constraints

- 规则基线：docs/superpowers/specs/2026-10-16-archive-persistent-drafts-design.md；仅Mac代码与临时隔离数据库。
- 不升级真实Mac库，不访问/修改正式库，不授权，不发邮件/ERP，不提交/合并/推送。
- 数量空或正整数；草稿本人可见，实时查看/新增权限、人员/产品线范围，admin/business:data:all无归属旁路。
- 不重做现有控件；交互样稿与实际实现可直接比较，视觉验收另列。SQL2017现场演练另行批准。

### Task 1: 独立存储与受控升级

**Files:** backend/app/models/form_draft.py; services/form_draft_migration.py; services/database_revision.py; models/init_db.py; scripts/upgrade_database.py; tests/form_draft_upgrade_contract.py。

**Interfaces:** PmsFormDraft(id UUID, owner_id, resource, payload_json, product_line_id, version, status, archive_id, timestamps); upgrade_form_drafts(engine), verify_form_draft_structure(connection)。

- [x] 先写临时SQLite失败用例：旧版本限定升级、重入、结构伪标记拒绝、失败DDL/标记回滚，权限/业务数据不变；编译SQL2017 DDL检查。
- [x] 运行 `PYTHONPATH=backend:backend/.venv-deps312 PMS_CONFIG_FILE=/dev/null /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 backend/tests/form_draft_upgrade_contract.py`，确认RED。
- [x] 新版本2026-10-16-form-draft-01；仅从governance-01升级新表，独立 --form-drafts-only；启动校验实际列/索引/版本；完整安装登记模型。
- [x] 运行同命令至GREEN；历史治理测试明确针对历史revision而非伪装当前就绪。

### Task 2: 草稿服务及原子转档

**Files:** services/form_drafts.py; schemas/form_draft.py; api/form_drafts.py; main.py; services/project.py; services/business_resources.py; services/field_catalog.py; tests/form_draft_contract.py。

**Interfaces:** /api/form-drafts/archive-create GET/POST; /{id} GET/DELETE; /{id}/submit POST; UUID由客户端生成作首次保存幂等键，expected_version作CAS，提交返回archive_id且已使用草稿重查返回同一结果。

- [x] 写失败测试：不完整保存/跨会话、其他用户包括admin拒绝、撤权/范围、隐藏字段/系统/秘密拒绝、正整数、停用枚举可读不可正式提交、CAS冲突/删除、事务失败保留、成功/重试仅一份正式档案、日志/ERP隔离。
- [x] 运行 `...python3 backend/tests/form_draft_contract.py` 至RED。
- [x] 实现固定archive-create注册适配；只接受ArchiveUpdate中可维护且当前可见可编辑字段（排除expected_version/product_category）；缺省负责人仅作资格检查，不补齐草稿必填。草稿阶段不调用金蝶目录。列表按当前范围过滤、详情重新权限检查及字段投影。
- [x] 版本条件UPDATE先领取，正式创建commit=False，同事务标记used/关联正式id/记录日志/提交。任何异常回滚，重复提交返回已有结果且再次校验正式档案范围。
- [x] 完善字段目录、路由资源登记；运行测试至GREEN及档案新增/数量/RBAC回归。

### Task 3: 新增表单接入与交互样稿

**Files:** frontend/src/form-system/usePersistentDraft.ts; frontend/src/views/project/ArchiveDraftList.vue; ProjectArchive.vue; page-guide/registry.ts; frontend/tests/persistent-draft.test.mjs; archive-persistent-drafts-browser.mjs。

**Interfaces:** 草稿适配管理id/version/unknown/conflict；request回传data；草稿列表只通过本人接口加载；新增表单正式保存一律先保存当前草稿再submit，防网络重复。

- [x] 写失败测试：失败留输入、多端冲突、加载最新/另存、未知提交只允许核对、保存未填必输、关闭三选、删除确认、成功移出待办。
- [x] 运行 `cd frontend && node tests/persistent-draft.test.mjs` 至RED。
- [x] 现有控件提供我的草稿、保存草稿及关闭三选；恢复时刷新元数据，保留停用值可识别；产品线目录不可用提示重试仍可保存不完整草稿。列表必要字段/分页；所有内容本人且权限控制。
- [x] 完成可交互隔离页面/截图，按确认规格直接比较；运行模拟浏览器行为及前端单测至GREEN。

### Task 4: 交付验证与记录

- [x] 后端草稿/升级/字段目录/枚举/现有创建/治理/权限测试；前端style/list/system、archive-filter、form-system、枚举/数据字典、npm run build。
- [x] 使用requesting-code-review进行独立审查并修正范围内问题，再运行受影响测试。
- [x] docs/PMS-SHARED-MODULES.md、DEVELOPMENT-BACKLOG、治理计划、升级准备说明及change.md记录实际结果；保留输出和退出码。
- [x] 明确仅代码/隔离验证完成；真实Mac升级、真实页面写入验收、真实SQL2017演练及正式部署均待独立批准，不把未验收项目报为通过。

不执行Git提交步骤；本计划直接连续执行，不因保存计划再次请求实施确认。

## 执行结果与剩余批准边界

2026-10-16上述勾选表示本批授权的代码、模拟样稿、升级工具及隔离验证完成。用户视觉/操作验收仍待确认；真实Mac数据库仍governance-01且无草稿表。SQL2017现场演练、真实Mac升级及实际写入验收、正式部署均未执行，需分别批准。

最终证据：`outputs/archive-persistent-drafts-20261016/verification.json`；详细边界：`docs/releases/2026-10-16-archive-drafts-local.md`。不把本地代码完成当作已启用或已上线。

## 后续追加：Mac真实升级与草稿验收已完成

2026-10-16用户独立批准后，Mac库升级至form-draft-01，本人测试草稿保存、刷新恢复、修改、删除实页验收通过。保留备份及配套旧程序。详见docs/releases/2026-10-16-archive-drafts-mac-upgrade.md；本文件前文为当时阶段记录，不再代表最新Mac状态。真实SQL2017及正式发布尚未执行。
