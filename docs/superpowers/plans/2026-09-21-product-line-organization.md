# 产品线组织权限 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目档案、项目进度及项目报表统一按明确授权的产品线和金蝶组织隔离，并提供可审计的历史迁移。

**Architecture:** 独立产品线主数据保存金蝶组织稳定标识，角色通过关联表授权；统一授权上下文驱动业务查询、写校验及 ERP 报表过滤。旧枚举归属与新主数据编号分开存储，历史迁移使用经确认的固定映射清单，不猜测组织。

**Tech Stack:** Vue 3、TypeScript、Element Plus、AG Grid、FastAPI、SQLAlchemy；本地 SQLite，生产 MSSQL 2017；金蝶通过现有独立 pymssql 只读连接访问。

## Global Constraints

- 已确认设计：`docs/superpowers/specs/2026-09-21-product-line-organization-design.md`；用户确认不存在跨组织代采购或入库。
- 复用 `codex/pms-db-permission-split` 当前工作区，不新建分支、不合并 master、不推送；保留其他任务尚未提交的文档。
- 实施先在开发机进行。服务器授权变更、历史映射及正式部署在各自明确清单获批后执行。
- 不重启 SQL Server、OA 或服务器；部署只允许按批准重启 PMS。数据库升级使用独立身份及有效备份。
- 不读取或输出私密配置内容，不记录密码；需要管理员时由用户本机交互输入。
- 不修改 OA SSO 协议，不修改金蝶基础资料编码/名称/备注映射。
- 不改变已验收采购报表的数量公式、主从联动及布局；保留申请日期 2026-01-01 起、默认 50 条分页。
- 所有业务动作同时受按钮权限、原本人/部门范围和产品线范围约束；产品线空集即无权限，无 admin 特例。
- 当前“产品类别空值不限”不能迁移为“产品线空值不限”。
- 新页面复用 PmsDataList、PmsListFilters、PmsFormDrawer 与统一字段控件、字体及视觉令牌，不重做表单框架。
- 每项按 RED、最小实现、GREEN、回归、记录、提交顺序推进；仅提交本项文件，实际实现记录到 `change.md`。

## 执行顺序与批准边界

1. 任务 1 只读发现，形成真实组织字段证据；任务 2 至 6 可在开发机使用确定接口和测试夹具实施。
2. 不因无法访问正式组织候选就停止不受影响的模型、授权、页面及测试开发；真实字段接入和验收保留为受阻项。
3. 任务 7 先生成只读清单；真实数据写入必须等待组织名单、档案归属和角色分配获批。
4. 任务 8 完成开发机交付后，另行批准生产升级和发布，不把总体设计确认当作管理员授权操作许可。

## 任务 1：组织数据源核对与权限清单

**Files:** 新建 `backend/scripts/inspect_product_line_organizations.py`、`backend/tests/product_line_discovery_contract.py`、`docs/产品线组织字段映射.md`；核对 `backend/scripts/provision_purchase_reader.py`、`backend/app/services/purchase_reader.py`。

**Interfaces:** 输出脱敏的组织字段和关联证据，不输出凭据或完整业务明细。后续组织读取器统一返回 `OrganizationOption(source_key, organization_id, code, name, active)`。

- [ ] 先写测试，确认发现工具只允许固定数据源、固定 SELECT 元数据及有界样本；失败报告只含阶段和错误类别，不执行 GRANT 或业务写入。
- [ ] 运行 `cd backend && PYTHONPATH=. .venv-security312/bin/python tests/product_line_discovery_contract.py`，新工具缺失时应失败。
- [ ] 使用现有只读连接核对已授权的 `T_PUR_REQUISITION.FAPPLICATIONORGID`、`T_PUR_POORDER.FPURCHASEORGID`、`T_STK_INSTOCK.FSTOCKORGID`。已有发现文件仅作为线索，不作为当前生产事实。
- [ ] 从实际元数据确认组织主表、中文名称表和启停字段，以及收料、退料的归属字段。权限不足时输出准确的表/列缺口，等待用户输入身份执行只读发现或批准最小 SELECT 授权，不扩大到全库 SELECT。
- [ ] 有界抽查同一项目的申请、订单、入库、退料组织；发现冲突时保留冲突清单，不能改变用户“不跨组织”的规则。
- [ ] 文档列明实际表/列、连接键、语言条件、是否已有读取权限、抽样结果和未覆盖范围；测试通过后提交本任务。

## 任务 2：产品线主数据与独立升级

**Files:** 新建 `backend/app/models/product_line.py`、`backend/app/schemas/product_line.py`、`backend/app/services/product_line.py`、`backend/app/services/product_line_migration.py`、`backend/tests/product_line_contract.py`；修改 `backend/app/models/project.py`、`backend/app/models/init_db.py`、`backend/app/services/database_revision.py`、`backend/tests/database_upgrade_contract.py`。

**Interfaces:** `get_product_line(db, line_id)` 返回主数据或 404；`list_product_lines(db, keyword, page, page_size)` 返回分页；`save_product_line(db, data, actor, expected_updated_at)` 校验唯一性并记录日志；`delete_product_line(db, line_id, actor)` 拒绝引用删除。

模型边界：新建 `SysProductLine`、`SysRoleProductLine`。档案新建 `business_product_line_id` 外键保留旧 `product_line_id` 枚举值；API 中现有 `product_line_id` 在正式切换后代表新主数据，前后端必须同批发布。导出迁移清单时明确使用 `legacy_product_line_id`，禁止含糊命名。

```python
def test_old_enum_id_does_not_authorize_new_line(db, archive_factory, line_factory):
    line = line_factory(id=12, organization_id=200292)
    archive = archive_factory(product_line_id=12, business_product_line_id=None)
    assert archive.business_product_line_id is None
    assert archive.product_line_id == line.id
    # 相同数字不是映射；此记录必须等待明确迁移。
```

- [ ] 补充唯一组织绑定、重命名不换绑、重复显示名校验、引用删除、禁用历史保留、并发 409 的行为测试。
- [ ] 运行 `PYTHONPATH=. .venv-security312/bin/python tests/product_line_contract.py`，确认新模型/服务测试先失败。
- [ ] 实现主数据与关联表，唯一键分别为 `(source_key, organization_id)`、`(role_id, product_line_id)`；外键限制错误引用。所有组织绑定只能来自核对过的候选。
- [ ] 独立升级创建结构并添加新档案归属字段，不自动填值、不自动授权角色产品线；版本从当前 `2026-09-21-01` 提升到 `2026-09-21-02`，如其他已批准任务先占用版本则采用新的递增版本并记录。
- [ ] 本地新库和已有库升级、重复执行及失败路径通过；不在正式环境运行迁移。
- [ ] GREEN 后记录实际实现并提交本任务。

## 任务 3：统一实时授权和角色接口

**Files:** 新建 `backend/app/services/product_line_scope.py`、`backend/tests/product_line_authorization_contract.py`；修改 `backend/app/services/authorization.py`、`backend/app/services/rbac.py`、`backend/app/services/auth.py`、`backend/app/schemas/rbac.py`、`backend/app/schemas/user.py`、`backend/app/api/auth.py`、`backend/app/services/role_templates.py`。

**Interfaces:** `get_authorized_product_line_ids(db, roles) -> list[int]`，`require_line_access(db, context, line_id, selectable=False)`，`get_project_organization_scope(db, context) -> list[ProjectOrganizationGrant]`；授权上下文始终返回 `product_line_ids: list[int]`，没有 `None` 表示不限的分支。

```python
def test_empty_role_selection_is_denied(db, user_factory, role_factory):
    user = user_factory(roles=[role_factory(data_scope=4, product_line_ids=[])])
    ctx = build_authorization_context(db, user.id)
    assert ctx['product_line_ids'] == []
```

- [ ] 添加多角色并集、停用角色、同 JWT 实时撤权、admin 无授权、强制改密、禁用产品线历史访问及新建拒绝测试。
- [ ] RED：`PYTHONPATH=. .venv-security312/bin/python tests/product_line_authorization_contract.py`。
- [ ] 用关联表计算明确 ID 集合；部门范围和按钮权限沿用现有计算规则。角色保存事务内校验主数据 ID，防止重复或不存在的授权。
- [ ] 新建模板不默认授权未来产品线；产品线管理菜单仅一次性授予管理员，已有菜单不启动回补。
- [ ] `/api/auth/me` 和业务产品线 options 返回一致范围；移除消费端对旧产品类别权限接口的依赖，旧接口不再产生业务授权旁路。
- [ ] GREEN 并回归 `rbac_permission_contract.py`、`role_home_contract.py`，记录并提交。

## 任务 4：档案、进度、任务及同步写路径

**Files:** 新建 `backend/tests/product_line_project_scope_contract.py`；修改 `backend/app/services/project.py`、`backend/app/services/project_archive_lifecycle.py`、`backend/app/services/erp_queue.py`、`backend/app/services/dashboard.py`、`backend/app/services/field_policy.py`、`backend/app/schemas/project.py`、`backend/app/services/list_query.py` 及对应项目 API。

**Interfaces:** `_apply_archive_scope` 过滤档案 `business_product_line_id`；`_apply_project_scope` 必须关联档案归属，不再回退到进度产品类别。`require_line_access(..., selectable=True)` 用于创建和变更目标。

```python
def test_change_requires_source_and_target_scope(db, scoped_actor, archive_factory):
    archive = archive_factory(business_product_line_id=2)
    with pytest.raises(HTTPException) as error:
        update_archive_as(scoped_actor(lines=[2]), archive.id, product_line_id=3)
    assert error.value.status_code in (403, 404)
    db.refresh(archive)
    assert archive.business_product_line_id == 2
```

测试模块使用项目现有测试框架实现等价断言；以上 `update_archive_as` 和 `scoped_actor` 为该测试文件定义的夹具助手，不加入业务服务。

- [ ] 先测列表/总数/详情/候选/新增/修改/删除/启停/任务/批量/同步重试越权，包含未归属历史记录、进度无档案引用。
- [ ] RED：`PYTHONPATH=. .venv-security312/bin/python tests/product_line_project_scope_contract.py`。
- [ ] 收敛到统一对象过滤；新建产品线强制必填，字段规则不能解除安全必填或开放未授权值；保留历史未归属仅在迁移入口可处理。
- [ ] 同步队列区分已接受的系统任务和当前交互重试；逐条确认目标项目归属，不将组织缺失当作全量访问；测试撤权后新发起/重试拒绝，执行身份不绕过固定目标校验。
- [ ] 已同步项目更改组织，若现有金蝶写接口不能证明外部归属一致则拒绝，并提示管理员迁移；不修改金蝶目标匹配算法来绕过该限制。
- [ ] GREEN 并执行档案生命周期、并发、自动同步队列、进度及操作日志契约；记录并提交。

## 任务 5：金蝶组织读取与报表隔离

**Files:** 新建 `backend/app/services/kingdee_organizations.py`、`backend/tests/purchase_organization_scope_contract.py`、`backend/scripts/extend_purchase_reader_organizations.py`；修改 `backend/app/services/purchase_reader.py`、`backend/app/services/purchase_progress.py`、`backend/app/api/purchase_reports.py` 及读取账号权限契约。

**Interfaces:** `list_kingdee_organizations(connection, keyword, page, page_size)` 返回任务 1 定义的候选；采购读取器接收 `list[ProjectOrganizationGrant]` 而非可用 `None` 绕过的编码集合。`ProjectOrganizationGrant` 固定字段为 `project_code: str`、`organization_id: int`。

```python
def test_scope_keeps_project_organization_pairs(report_fixture):
    grants = [ProjectOrganizationGrant('P-A', 1), ProjectOrganizationGrant('P-B', 2)]
    rows = report_fixture.query(grants)
    assert ('P-A', 2) not in {(r['project_code'], r['organization_id']) for r in rows}
```

- [ ] 添加主表、候选、数量、进度筛选、详情、导出双维度隔离测试；必须按项目与组织的配对匹配，不能两个独立 IN 形成错误笛卡尔授权。
- [ ] 添加跨组织订单/入库/退料异常测试：明细不可见、合计不可误报完整、不得从异常消息泄漏他组织单号。
- [ ] RED：`PYTHONPATH=. .venv-security312/bin/python tests/purchase_organization_scope_contract.py`。
- [ ] 根据任务 1 实证字段实现固定参数化 SQL，授权限制早于分页；大量项目授权使用受限会话临时映射，不能拼接未转义编码或超过 SQL 参数上限。
- [ ] 每一层来源关联验证组织；无法证实的链路按现有待核对策略返回空合计，保留已有合法分批公式和 Decimal 运算。
- [ ] 权限扩展脚本仅处理确需新增的组织表列和收料/退料组织字段，默认只输出脱敏检查结果；执行授权需用户批准并交互输入管理员凭据。不重建已有账号、不轮换既有密码。
- [ ] GREEN 并回归全部 `purchase_*contract.py`，保留真实样本对比与性能记录；记录并提交。

## 任务 6：产品线页面、角色勾选及业务选项

**Files:** 新建 `backend/app/api/product_lines.py`、`frontend/src/api/productLine.ts`、`frontend/src/views/system/ProductLineList.vue`、`frontend/src/composables/useProductLineOptions.ts`、`frontend/tests/product-line-contract.test.mjs`、`frontend/tests/product-line-browser.mjs`；修改 `backend/main.py`、`frontend/src/views/system/RoleList.vue`、`frontend/src/views/project/ProjectArchive.vue`、`frontend/src/views/project/ProjectList.vue`、`frontend/src/router/index.ts`、`frontend/src/layout/AppLayout.vue`、实际 auth store、字段目录及操作日志字段注册。

**Interfaces:** `/api/product-lines` 管理列表/新增，`/api/product-lines/{id}` 更新/删除，`/api/product-lines/options` 业务候选，`/api/product-lines/organizations` 管理员组织候选。静态路由声明在 `{id}` 之前；管理与业务 options 使用不同依赖。

```js
test('empty authorized options cannot create an archive', async () => {
  await mockProductLineOptions([])
  await openArchiveCreate()
  await expectCreateBlocked('没有可用的产品线权限')
})
```

上述三个浏览器辅助函数在 `product-line-browser.mjs` 内基于现有项目浏览器测试工具定义，分别模拟 options 响应、点击新增和断言提交阻止及错误提示。

- [ ] 先测无权限菜单/按钮隐藏、复选保存、单个默认/多个主动选择/零个阻止创建、禁用历史显示、来源失败重试、组织候选模糊分页与乱序响应。
- [ ] RED：`node tests/product-line-contract.test.mjs` 和新行为测试。
- [ ] 主数据页面用标准列表和用户 B 抽屉，区分金蝶原名称与 PMS 显示名；绑定字段不可编辑，加载/空/错误/并发状态统一组件处理。
- [ ] 角色将产品类别授权改为产品线勾选并标注未选无权限；创建档案使用受控 options。普通产品类别字段仍从原枚举读取，不删除该业务枚举。
- [ ] 旧产品线枚举从枚举管理隐藏，字段目录声明主数据来源；查询方案校验旧字段语义，旧枚举编号不得自动恢复成新产品线条件。
- [ ] 更新所有受影响引用、路由权限、图标注册和日志中文差异；UI 不覆盖第三方控件内部样式。
- [ ] GREEN，运行标准样式、列表、系统 UI、档案筛选、字段目录和枚举契约；1366×768、1600×900、窄窗口截图及鼠标/键盘验收；记录并提交。

## 任务 7：历史归属与角色授权迁移

**Files:** 新建 `backend/scripts/migrate_product_line_assignments.py`、`backend/tests/product_line_assignment_migration_contract.py`、`docs/产品线迁移操作说明.md`；扩展任务 2 的迁移服务，必要时增加专用受控清单 API。

**Interfaces:** 固定输入结构包含 `source_revision`、`source_fingerprint`、`lines`、`archives`、`roles`；每条档案为 `archive_id`、`project_code`、`legacy_product_line_id`、`target_product_line_key`；每条角色包含 `role_id`、明确产品线 key 列表。只读检查返回分组中文异常，不输出密码。

```python
def test_migration_conflict_rolls_back_all_assignments(migration_fixture):
    before = migration_fixture.snapshot()
    result = migration_fixture.apply_with_conflicting_archive()
    assert result.committed is False
    assert migration_fixture.snapshot() == before
```

- [ ] 先测陈旧快照、重复组织、重复编码、未知角色、空角色授权、旧新编号相同、重复执行、部分写入失败全回滚及日志。
- [ ] RED：`PYTHONPATH=. .venv-security312/bin/python tests/product_line_assignment_migration_contract.py`。
- [ ] 默认 dry-run，分组展示未归属、单一候选、多个组织冲突、缺失档案关联、旧角色范围不能转换；不从订单活动自动决定项目归属。
- [ ] 用户确认真实组织名称和映射清单前，只在本地测试事务；不得对正式库运行 apply。
- [ ] 应用时在事务内复核源指纹、唯一性、引用和管理员治理权限，写归属与角色关系及统一日志；旧字段保留审计，不回填错误默认值。
- [ ] 幂等通过迁移批次及实际目标值判断；不允许重复执行覆盖后来人工撤权。
- [ ] GREEN，交付中文清单和操作说明，记录并提交。

## 任务 8：整体回归、正式切换与验收

**Files:** `change.md`、`docs/采购进度查询报表说明.md`、`docs/采购报表只读账号运维.md`、本计划、任务 1 与任务 7 文档；发布文件仅在项目 `release/` 和服务器 `C:\PMS\.runtime` 下。

- [ ] 开发机执行后端产品线全套契约、`rbac_permission_contract.py`、`database_upgrade_contract.py`、`field_catalog_contract.py`、`enum_management_contract.py`、档案/进度/同步/操作日志及采购契约。逐个按测试入口运行，避免以 unittest 发现零项当通过。
- [ ] 前端运行 `node tests/style-contract.test.mjs`、`node tests/list-standard-contract.test.mjs`、`node tests/system-ui-consistency-contract.test.mjs`、`node tests/archive-filter-contract.test.mjs`、`node tests/data-dictionary-contract.test.mjs`、`node tests/enum-management-contract.test.mjs`、新产品线测试及 `npm run build`。
- [ ] 对照规格逐项复核，保留真实组织链路未验证项，不把夹具测试写成真实验收。
- [ ] 提交开发机验收版和真实映射清单，等待用户批准数据内容、权限变更及部署。
- [ ] 正式维护前验证备份、程序版本/运行目录、受保护配置和同步任务状态；保存程序与数据库配套回退依据。
- [ ] PMS 维护期间独立升级、应用已确认映射、核对角色及原业务哈希，再发布与启动。失败停留在明确阶段，不伪造数据库版本或直接运行旧宽权限代码。
- [ ] 两个不同组织账号和一个多组织账号验证列表、详情、创建、伪造请求、报表候选、分页、主从明细、导出；管理员撤权后同样拒绝。OA 嵌入另验收，不改变 OA 协议。
- [ ] 更新逐字段说明中的组织来源与可见范围，记录实测性能、发布结果和剩余异常；仅在证据齐全后标记完成。

## 自检

- 设计 1–4：任务 1–3、6；设计 5：任务 4；设计 6：任务 5；设计 7：任务 7–8；设计 8–9：任务 6、8。
- 复用已批准的方案和当前分支，不追加产品线多组织合并、自动全权或新的动态表单能力。
- 确认名单和正式授权是受控数据执行关口，不阻止开发机模型、页面及权限契约实施。
