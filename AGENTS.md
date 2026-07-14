# PMS Project Instructions

## 项目定位

- 本项目是企业内部 PMS 项目管理系统，重点覆盖项目档案管理、项目进度管理，并预留售后管理扩展。
- 系统需要集成泛微 OA，并对接金蝶云星空 ERP。
- 项目进度体验参考企业微信智能表格，强调在线维护、协同操作、表格内直接编辑和自动保存。
- 项目档案当前属于半成品模块，后续调整要兼顾 ERP 同步、人员字段、状态字段和数据权限。

## 技术栈

- 前端：Vue 3 + TypeScript + Element Plus + AG Grid。
- 后端：Python FastAPI + SQLAlchemy。
- 数据库：生产目标为 MSSQL 2017，本地开发可使用 SQLite。
- 前端入口在 `frontend/`，后端入口在 `backend/`。

## UI 风格

- PMS UI 采用浅色、简洁、紧凑、B2B SaaS 风格。
- 主背景使用冷灰浅色，内容面板使用白色。
- 主色保持克制靛蓝，成功色青绿，警告色琥珀，危险色红色。
- 表格优先清晰、密集、可扫描，避免粗糙按钮和拥挤布局。
- 状态使用胶囊标签、小圆点、柔和背景和清晰文字。
- 当前全局主题入口是 `frontend/src/styles/pms-theme.css`。
- 中文界面统一使用项目内置 `Noto Sans SC`；Element Plus、AG Grid 和业务页面都必须继承 `--pms-font`，不得在页面内另写平台字体栈，避免 Windows 与 macOS 显示漂移。
- 系统管理等非标准列表页面使用 `.pms-system-page`、`.pms-surface-section` 和 `.pms-dense-table`；颜色、字号、边框、圆角和状态样式优先复用全局 token，禁止重新引入 Element Plus 旧默认色。
- 动态菜单使用的新图标名称必须同步注册到 `frontend/src/layout/AppLayout.vue` 的 `iconMap`，业务图标不得使用 emoji。
- 完整前端实现规范见 `docs/PMS-UI-STANDARD.md`。
- 旧版 UI 诉求可参考 `UI要求/UI风格.md`，但实现时以现有 `pms-theme.css` 和已落地组件为准。

## 标准列表页面

新增或重构列表页面时，优先使用以下标准模块：

- `frontend/src/components/PmsDataList.vue`
- `frontend/src/components/PmsListFilters.vue`
- `frontend/src/composables/useListFilters.ts`

列表页面应尽量只维护业务数据、列定义、接口调用和业务动作。布局、工具栏区域、筛选区、表格滚动条和分页应交给标准组件。

项目档案、项目进度、后续售后管理等列表页面都应遵循这一模式。

## 项目档案与项目进度

- 项目档案是项目主数据入口，修改时注意 ERP 同步、创建人、编辑人、同步状态等字段。
- 项目进度功能结构未最终定稿前，不要大改信息架构；先保证风格和基础交互一致。
- 项目进度页面必须保留表格内编辑和自动保存体验，避免改成繁琐弹窗表单。
- 引用自项目档案、主数据或外部系统的字段，在消费页面默认只读展示；如需修改，应回到字段来源模块维护，避免在项目进度、售后等页面直接改引用值。
- 从企业微信智能表格迁移功能时，优先保留用户熟悉的字段、筛选、协作和批量维护习惯。

## OA、ERP 与权限

- 不随意改变 OA 登录流程、SSO 回调、金蝶同步接口和权限逻辑。
- 涉及 OA、ERP、认证、菜单权限、数据权限的改动，需要先说明接口影响和回滚风险。
- 后端业务接口必须通过统一 RBAC 依赖校验按钮权限，并在读写项目、任务、档案和 ERP 数据时同时校验数据范围与产品线范围。
- 运行时权限以数据库中当前有效用户、有效角色和有效权限为准；JWT 不固化权限，撤权后下一次请求立即生效。
- 前端的路由、按钮和表格编辑状态要消费同一权限码，但前端隐藏只用于交互体验，后端始终是最终授权防线。
- 不得为 `admin` 或其他超级角色设置运行时全权旁路，后端启动时也不得自动补回人工撤销的权限。
- `admin`、`business_admin`、`operator` 仅是首次创建时使用的可编辑角色模板，不是代码级角色层级；新增权限节点只能做一次迁移授权，不得在后续启动中持续回补。
- OA 自动开户只能分配启用的 `operator` 角色；角色缺失或禁用时必须失败关闭，禁止回退为任意角色。
- 权限体系需预留用户、角色、菜单、部门等能力。

## 操作日志

- 后续任何新模块只要存在新增、编辑、删除、导入、同步、登录、退出等写操作，必须接入统一操作日志服务。
- 后端统一使用 `backend/app/services/operation_log.py` 记录日志，业务模块传入 before/after 快照，由日志服务负责脱敏、diff 和写入。
- 敏感字段不得明文入库，包括 password、password_hash、token、remember_token、secret、sign、key 等。
- 日志表自身不记录日志，避免递归。
- 前端日志查询页面为 `frontend/src/views/system/OperationLogList.vue`，应继续沿用标准列表与筛选组件。
- 日志字段差异必须由后端根据字段目录和字段注册表生成中文 `diff_items`；前端不得为业务字段维护重复翻译表，原始字段编码只作为辅助技术信息。

## 字段目录与业务枚举

- 数据字典是由 `backend/app/services/field_catalog.py` 自动生成的只读字段目录，不作为在线数据库结构或动态表单编辑器。
- 新增、改名或删除业务字段时，必须同步维护模型、Schema 或对应字段注册表，并通过 `backend/tests/field_catalog_contract.py`，保证字段目录及时更新。
- 选择型业务字段必须声明稳定的 `enum_code`，后端通过 `backend/app/services/enum_registry.py` 注册与校验，前端通过 `frontend/src/composables/useEnumOptions.ts` 读取；禁止在多个页面重复硬编码同一组选项。
- 产品线、产品类型等可配置枚举允许维护值；档案、项目和任务状态属于固定流程枚举，存储值不可在线增删改，仅允许维护显示名、排序和启停。
- 数据权限、ERP 同步状态等系统协议值只进入字段目录并标记为系统固定，不进入枚举管理。
- 禁用枚举值不得用于新增或变更，历史数据仍须通过完整 `label_map` 正常显示；已被业务数据引用的枚举值不得删除。

## 字段规则与字段治理

- 项目档案和项目进度的全局字段规则由 `backend/app/services/field_policy.py` 统一注册和校验，前端管理页为 `frontend/src/views/system/FieldPolicyList.vue`。
- 代码字段注册表是配置上限；引用、计算和系统字段不得通过配置开放编辑，核心结构字段不得被配置到无法创建业务数据的状态。
- 字段显示、编辑、必填和列表可选状态必须由同一份生效元数据驱动；列表列偏好中已经失效的字段要自动清理。
- 新增、编辑、表格自动保存、详情保存和 ERP 同步等写路径都必须调用统一字段规则校验，前端禁用仅用于交互，后端负责最终拒绝并返回结构化 `422`。
- 后来启用的必填规则仅约束规则生效后创建的数据；存量数据继续允许维护。任何新模块接入字段规则时都要保留这一兼容策略。
- 字段规则变更必须写入统一操作日志，并使用更新时间进行并发覆盖检查。

## 本地启动与辅助脚本

- macOS 本地一键启动脚本：`start-pms.command`。
- GitHub 推送辅助脚本：`push-github.command`。
- 前端默认本地端口：`5174`。
- 后端默认本地端口：`8000`。

## 验证命令

前端改动后优先运行：

```bash
cd frontend
node tests/style-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
npm run build
```

项目档案筛选相关改动还应运行：

```bash
cd frontend
node tests/archive-filter-contract.test.mjs
```

后端配置或初始化逻辑改动时，检查 `backend/tests/` 下对应契约测试。

字段或枚举相关改动还应运行：

```bash
cd backend
python tests/field_catalog_contract.py
python tests/enum_management_contract.py

cd ../frontend
node tests/data-dictionary-contract.test.mjs
node tests/enum-management-contract.test.mjs
```

## GitHub 工作流

- 默认从 `master` 拉出 `codex/` 前缀功能分支。
- 合并到 `master` 属于正式程序更新，执行前需要用户明确确认。
- 合并后可删除已合并的临时功能分支。
