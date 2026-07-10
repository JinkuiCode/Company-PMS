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
- 后端业务接口要考虑 RBAC 和数据权限。
- 权限体系需预留用户、角色、菜单、部门等能力。

## 操作日志

- 后续任何新模块只要存在新增、编辑、删除、导入、同步、登录、退出等写操作，必须接入统一操作日志服务。
- 后端统一使用 `backend/app/services/operation_log.py` 记录日志，业务模块传入 before/after 快照，由日志服务负责脱敏、diff 和写入。
- 敏感字段不得明文入库，包括 password、password_hash、token、remember_token、secret、sign、key 等。
- 日志表自身不记录日志，避免递归。
- 前端日志查询页面为 `frontend/src/views/system/OperationLogList.vue`，应继续沿用标准列表与筛选组件。

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
npm run build
```

项目档案筛选相关改动还应运行：

```bash
cd frontend
node tests/archive-filter-contract.test.mjs
```

后端配置或初始化逻辑改动时，检查 `backend/tests/` 下对应契约测试。

## GitHub 工作流

- 默认从 `master` 拉出 `codex/` 前缀功能分支。
- 合并到 `master` 属于正式程序更新，执行前需要用户明确确认。
- 合并后可删除已合并的临时功能分支。
