# Department Leader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. User already selected inline execution.

**Goal:** 在开发机提供部门负责人维护入口，允许有效PMS用户跨部门兼任，供后续档案审批准备基础资料。

**Architecture:** 复用SysDept.leader_id、现有部门CRUD和用户选项接口，不迁移数据库、不变更角色授权。用户管理抽屉使用现有统一表单控件，人员选项与按部门筛选的用户列表分离；说明复用PmsPageGuide。

**Tech Stack:** Vue3 / TypeScript / Element Plus / FastAPI / SQLAlchemy / SQLite contracts.

## Global Constraints
- 新增档案保持project:archive:add授权，本阶段不启用档案编辑收紧或审批。
- 所有启用PMS用户均可选择；同一用户可担任多个部门负责人，不自动调整用户部门、角色或业务数据。
- 新增/维护部门负责人必输；历史空值读取仍兼容，无默认人员；历史禁用人员显示但不能新选。
- 复用32px编辑控件、中文字体和既有抽屉，不新增局部第三方内部样式。
- 不升级正式或开发库、不部署正式环境、不合并或推送；后续档案/审批交互样稿单独验收。

### Task 1: Department service validation and display metadata
**Files:** backend/tests/department_leader_contract.py; backend/app/services/rbac.py; backend/app/schemas/rbac.py; backend/app/services/field_catalog.py.
**Interfaces:** DeptCreate/DeptUpdate keep leader_id; DeptResponse adds readonly leader_label. get_user_options returns id, real_name, username, dept_id only.
- [x] Write isolated SQLite/TestClient contracts covering missing/null/disabled/nonexistent leader rejection, enabled cross-department leader, two departments sharing one leader, unchanged user/role membership, operation log leader diff, historical-null reads, readonly historical leader label and unchanged endpoint authorization.
```python
response = client.post('/api/depts', json={'dept_name': '第二部门', 'leader_id': outside_user.id})
assert response.status_code == 200
assert db.get(SysDept, response.json()['id']).leader_id == outside_user.id
assert client.post('/api/depts', json={'dept_name': '缺负责人'}).status_code == 422
```
- [x] Run RED: `PYTHONPATH=.venv-deps312:.:tests python3 tests/department_leader_contract.py`; observed missing-leader rejection failure.
- [x] Validate merged department before mutating, including partial hierarchy updates; invalid result raises structured422. Existing null departments remain readable. Add username to active minimal user options and build leader_label from batch-loaded associated users in get_dept_tree.
```python
def _validate_department_leader(db, leader_id):
    if leader_id is None:
        raise HTTPException(422, detail={'field_key': 'leader_id', 'message': '请选择部门负责人'})
    user = db.get(SysUser, leader_id)
    if not user or user.status != 1:
        raise HTTPException(422, detail={'field_key': 'leader_id', 'message': '部门负责人必须是启用的PMS用户'})
```
- [x] Run GREEN and field_catalog/enum_management contracts. No schema migration because only existing persisted leader_id is used.

### Task 2: Unified department editor and guide
**Files:** frontend/tests/department-leader-browser.mjs; frontend/tests/system-form-drawer-browser.mjs; frontend/src/views/system/UserList.vue; frontend/src/page-guide/{types.ts,navigation.ts,registry.ts}; frontend/tests/page-guide.test.mjs if applicable.
**Interfaces:** PmsSelectControl receives `{value:number,label:string,disabled?:boolean}[]`; `/users/options` response all enabled people; deptForm.leader_id nullable initially, never auto-filled.
- [x] Write browser RED using actual UserList with isolated HTTP fixtures. Test required empty leader, independent all-user options, cross-dept choice, sharing one leader, saving failure draft preservation, loading/error retry and guide/new-tab behavior. Existing department browser fixture explicitly selects its required leader.
```javascript
await drawer.getByRole('button', {name:'保存',exact:true}).click()
await expect(drawer.getByText('请选择部门负责人', {exact:true})).toBeVisible()
await drawer.locator('[aria-label="部门负责人"] .el-select__wrapper').click()
await page.getByRole('option', {name:'负责人（A002）',exact:true}).click()
```
- [x] Run `node tests/department-leader-browser.mjs`; observed missing field assertion failure.
- [x] Add required field after dept_name; load options each open, disable selection/save during loading, retain historical disabled leader_label. On fetch error show inline retry, not stale options. Guard closed/switched drawer against stale response.
```typescript
const deptForm = reactive({id:0,parent_id:0,dept_name:'',leader_id:null as number|null,sort:0,status:1})
const deptRules: FormRules = {
  dept_name:[{required:true,message:'请输入部门名称'}],
  leader_id:[{required:true,message:'请选择部门负责人',trigger:'change'}],
}
```
- [x] Register users guide and add PmsPageGuide in toolbar; guide describes actual current department/user rules, not unimplemented approval behavior.
- [x] Run browser GREEN, existing system-form-drawer browser and required style/list/system-ui/build/data-dictionary/enum-management checks.

### Task 3: Actual developer page and record
- [x] Review only this diff, no blocking findings; added existing-role preservation, close/reopen race and guide-new-tab regressions.
- [x] Restart local backend only; verify dev browser signed-in page, department dropdown, no automatic leader assignment, user-maintained archive managers preserved. Open department edit for user's choice, do not save a person on user's behalf.
- [x] Update change.md with actual files, reason, evidence; mark task statuses. Full archive approval is not yet implemented.
- [x] Interactive archive drawer/approval mockup created for user confirmation; no actual workflow hookup until that confirmation.
