# Archive Governance Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Reuse user's inline execution choice.

**Goal:** 将已确认档案字段和变更审批样稿接入开发机真实服务，并更新标准说明。

**Architecture:** 独立archive_change模型/Schema/服务/API保存申请与中文差异，复用档案生命周期行锁、字段规则、业务范围和现有写入/同步队列。原PUT保持接口路径但改为关系授权和审批入口；复用事务内验证/应用函数，提交不改正式值，审批通过和部门负责人直改才实际写入。前端复用统一抽屉控件及查询/列表/说明，不创建第二套全局模块。

**Tech Stack:** FastAPI / SQLAlchemy / SQLite and MSSQL2017 / Vue3 / Element Plus / AG Grid.

## Global Constraints
- 2026-10-14追加状态：用户批准仅开发机-02、最小测试账号配置及历史导入例外，全部已实施。开关回归及历史导入RED已转GREEN；开发机实际用户授权的私有副本审批闭环通过，无日常库测试单或外部ERP写入。148项组合、前端必要检查及最终只读复核完成；用户页面验收待进行，正式环境不动。
- 基线：2026-10-14批准规格与archive-governance样稿；复用codex/pms-unified-query和上一批未提交部门维护。
- 新增需要project:archive:add；编辑/提交/审批保留project:archive:edit后端RBAC，并追加原负责人/原部门负责人关系判定。查看和产品线/人员范围不放宽，无超级角色旁路，不创建/自动补回权限。
- 审批人取原负责人所属有效部门当前负责人，人员关系撤销下一请求立即生效；不采用草稿新负责人路由。
- 新必输规则记录升级生效时间，历史缺值不自动补；主机为既有数字枚举值1，重命名不改变语义。
- 客户全名有值只读、空值隐藏；档案计划移除，不影响项目/任务或历史日志。
- 一个档案只能有一项活动申请；提交重试以submission_id去重，申请版本与正式档案业务快照校验，拒绝陈旧审批或草稿覆盖。
- 不增加OA审批/邮件或ERP写入范围；不部署、合并或推送。开发机备份与限定升级须独立批准。

### Task 1: Transactional governance service
**Files:** backend/app/models/archive_change.py; backend/app/schemas/archive_change.py; backend/app/services/archive_change.py; backend/app/api/archive_changes.py; backend/app/services/project.py; backend/app/schemas/project.py; backend/main.py; backend/app/models/init_db.py; backend/tests/archive_change_contract.py.
**Interfaces:** archive_business_version(archive)->str; archive_edit_context(db,archive,scope)->dict; preview_archive_change(db,id,data,user_id,scope)->dict; submit_archive_change(...)->dict; decide_archive_change(db,id,decision,expected_version,user_id,scope)->dict. ArchiveUpdate.expected_version optimistic guard. Application helpers validate_archive_updates/apply_archive_updates do not commit; their caller owns rollback/commit.
- [x] RED隔离数据库+TestClient：有新增码可新增、无码拒绝；单角色码无关系拒绝、owner待批不改变档案或队列、原部门leader直改、跨部门兼任、缺路由拒绝、变更owner走原路由、审批重试/重复提交、同档案活动冲突、撤权/撤关系、版本冲突、事务失败无部分写入。
```python
before = archive.project_name
result = submit_archive_change(db, archive.id, payload, owner.id, scope_context=owner_scope)
assert result['status'] == 2
assert archive.project_name == before
assert db.query(ErpSyncTask).count() == queue_count
```
- [x] Run RED `PYTHONPATH=.venv-deps312:.:tests python3 tests/archive_change_contract.py`.
- [x] 模型保存原档案ID、活动档案ID、提交幂等ID、原业务快照hash、修改字典/中文差异、提交/审批人和部门、原因、结论、状态/版本/时间；活动ID非空唯一索引、提交人+submission_id唯一索引。读写先按既有范围查档案；新服务关系校验后调用统一验证/实际写入。保存pending时仅写申请和日志，实际应用同一事务内写关联/队列/日志。撤回/退回保留记录，重提新申请。
```python
if actor_id != archive.manager_id and actor_id != department.leader_id:
    raise HTTPException(403, '只有项目负责人或其部门负责人可以修改')
if supplied_version != archive_business_version(archive):
    raise HTTPException(409, '档案已变化，请刷新后重试')
```
- [x] GREEN，保持创建/手动同步/启停/删除各自独立授权；申请引用纳入现有删除保护，避免审批丢失。

### Task 2: Fields and bounded migration
**Files:** backend/app/services/{field_policy,offline_archive_fields,field_catalog,list_query,business_export,enum_registry,database_revision}.py; backend/app/models/project.py; backend/app/services/archive_governance_migration.py; backend/scripts/upgrade_database.py; backend/tests/{archive_governance_upgrade_contract,archive_governance_fields_contract}.py.
**Interfaces:** upgrade_archive_governance(engine) from feedback-02 or archive-governance-01 to 2026-10-14-archive-governance-02. --archive-governance-only never calls historical init. Verify target structure/indexes/cutoff/marker on retry; never reset existing markers or repair fake revision.
- [x] RED字段/升级契约：必输生效时间、新建与历史兼容、主机条件必输且枚举改名仍执行、客户全名不可修改/新增、用户存在启用、旧plan条件拒绝；升级只改限定对象，角色/邮箱/负责人及项目日期保留；注入失败回滚、重跑不重置规则时间或回补授权、MSSQL DDL索引编译正确。
```python
upgrade_archive_governance(engine)
assert 'plan_start_date' not in {column['name'] for column in inspect(engine).get_columns('pms_project_archive')}
assert db.get(PmsProject, project_id).start_date == previous_project_date
```
- [x] Run RED targeted files, then add locked defaults/cutoffs through existing field rules; add required_when metadata for主机字段，移除计划定义/序列化/查询/导出。
- [x] 限定事务内创建申请表/状态枚举，更新新required字段规则时间，删除plan字段规则与两列，更新版本；保存角色授权及人员原值。新装初始化显式安装同一规则，不从运行时启动迁移。
- [x] GREEN并运行field_catalog、enum_management、现有档案字段/生命周期/查询/导出相关契约；旧调用测试改为合法角色关系和版本，不删业务断言。

### Task 3: Approved drawer and approval list
**Files:** frontend/src/views/project/ProjectArchive.vue; frontend/src/views/project/archiveGovernance.ts; frontend/src/views/project/ArchiveChangeList.vue; frontend/src/page-guide/{types,navigation,registry}.ts; frontend/src/api/project.ts; frontend/tests/archive-governance-browser.mjs; frontend/tests/archive-governance.test.mjs; existing affected contracts.
**Interfaces:** backend list can_edit/change_mode/change_version/approver_name/pending_change_id. Shared field order builder used by creation and editing. ArchiveChangeList consumes existing data-scope constrained API, PmsQueryWorkspace entry-mode=document/PmsDataList/PmsPageGuide.
- [x] RED model/browser：类别首位、机型/数量顺序、主机红星、无客户全名/plan新建控件、来源最后、角色与关系共同控制、owner中文diff提交、leader直改、审批列表/退回/撤回、详情行切换草稿保护及失败保留、说明准确。
```javascript
await expect(drawer.getByRole('button',{name:'提交变更',exact:true})).toBeVisible()
await drawer.getByRole('textbox',{name:'项目名称',exact:true}).fill('修改名称')
await drawer.getByRole('button',{name:'提交变更',exact:true}).click()
await expect(page.getByRole('dialog',{name:'确认档案变更',exact:true})).toContainText('审批人')
```
- [x] Run RED frontend targeted tests. 使用已批准32px控件/460px抽屉，维护创建/详情同序字段和已有主从切换；每次实际保存带版本，先获取服务器差异。审批列表独立文件，不重写共享查询/表头/说明模块。
- [x] GREEN必需style/list/system-ui/build、archive-filter及数据字典/枚举契约；检查1366x768/1100x650截图与批准样稿直接比对。

### Task 4: Local upgrade and acceptance (separate approval)
- [x] 获本机限定升级许可后，SQLite在线backup到.runtime/backups，integrity_check/行数/版本核对；在临时副本演练升级与恢复，绝不在正式环境操作。
- [x] -01及追加获批-02已完成限定升级、备份/恢复演练和保留对象核对；只重载开发机PMS，不涉及正式服务。-02不修改原业务日期、账号、授权或字段规则。
- [x] 实际登录浏览器核对部门/档案数据只读、创建/编辑字段、范围、说明；隔离真实服务数据库验证完整审批，不在用户库写测试业务或代选负责人。
- [x] 独立只读代码复核，修复范围内问题并复测。记录change.md、开发验收报告与已批准/未完成边界；没有实际验收证据不宣称全部完成。
