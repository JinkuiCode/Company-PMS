# 项目进度共享页面状态迁移

> **For agentic workers:** 使用 executing-plans 在当前对话逐项执行；复用已批准治理方案和现有工作区，不新建分支或委派实现。

**Goal:** 项目进度工作台和任务列表共用页面状态控制器，加载失败可重试，过期及离页响应不覆盖页面。

**Architecture:** 两页直接接入已有 `usePageLoad`，保留各页业务数据适配。错误行沿用档案页的提示及重试入口，不新增布局、协议、权限或存储。

**Tech Stack:** Vue3、TypeScript、AG Grid、现有 Playwright 隔离测试。

## Global Constraints

- 依据已批准治理方案中的旧页分批迁移及用户“按顺序完成任务”，本批仅 Mac 前端代码及隔离验证。
- 当前 `codex/pms-unified-query` 工作区保留其他资料；不部署、不发邮件、不操作金蝶、不修改数据库或授权，不提交/合并/推送本批代码。
- 保留项目列表完整性校验、查询就绪条件、分页、列偏好、表格编辑和自动保存，保留任务记录联动。
- 使用已有布局、令牌及错误提示模式，不改新增表单结构。

## Task 1：两页共享请求生命周期

**Files:** 修改 `frontend/src/views/project/ProjectList.vue`、`ProjectProgress.vue`；测试 `frontend/tests/progress-page-load-browser.mjs`、`project-progress-workbench-contract.test.mjs`。

**Interfaces:** 使用 `usePageLoad().begin():number`、`isCurrent(ticket):boolean`、`succeed(ticket,empty):boolean`、`fail(ticket,error):boolean`、`invalidate():void`。页面通过 `loading`、`failed`、`phase` 派生查询就绪状态；失败不能沿用上次成功的可查询标志。

- [x] 写隔离浏览器行为测试：真实两页、所有 API 模拟；失败显示重试、重试恢复、空结果结束加载、后发先到及迟到错误不覆盖、卸载废弃请求；禁止任何真实 API 写入。
- [x] 执行 `cd frontend && node tests/progress-page-load-browser.mjs`，确认因缺少失败重试入口而 RED，不把运行环境错误算作 RED。
- [x] 替换手写 serial/loading 状态：`const ticket=state.begin()`；响应应用前 `if(!state.isCurrent(ticket))return`；成功 `state.succeed(ticket, rows.length===0)`；失败清空列表及总数并 `state.fail(ticket,error)`。
- [x] 查询允许条件使用 `phase==='ready'||phase==='empty'`；不以历史 `hasQueried` 代替本次成功。任务记录异步切换后再次检查 ticket；卸载调用 invalidate，保留原记录切换清理。
- [x] 模板沿用 `<div v-if="listError" class="pms-list-load-error" role="alert">加载失败，请重试 <el-button size="small" @click="fetchList">重试</el-button></div>`；任务页同理，并补上已有共享加载状态绑定。
- [x] 原旧 serial 源码契约改为共享控制器准入及卸载约束，不删除“旧响应不能覆盖”的要求。
- [x] 隔离行为测试 GREEN；执行 `node tests/page-load.test.mjs`、`node tests/project-progress-workbench-contract.test.mjs`、`node tests/list-pagination-contract.test.mjs`。

## Task 2：验收与记录

- [x] 执行 `node tests/style-contract.test.mjs`、`node tests/list-standard-contract.test.mjs`、`node tests/system-ui-consistency-contract.test.mjs`、`npm run build`，保存命令、退出码及输出。
- [x] 独立代码审查，处理本批相关缺陷；已有完整证据、源码未变时复用，不重复无关检查。
- [x] 在 `change.md`、`docs/PMS-SHARED-MODULES.md` 和本计划记录实际结果；仅标记这两页的页面状态迁移，不宣称列偏好/表单会话/全页权限验收完成。

后续批次：列偏好兼容适配、表单会话和字段元数据、系统页面迁移；各批仍以已批准的行为及视觉基线为准，新增接口/授权或正式切换按独立边界处理。

## 实际结果

2026-10-18完成本机两页状态迁移。隔离Vite5198启动：`cd frontend && node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5198 --strictPort`；所有API被测试路由模拟，任何非GET拒绝。初始RED为缺少内联失败重试；GREEN覆盖两页失败/重试、空结果、旧成功/错误、卸载，任务另覆盖历史异步切换后旧请求不得增加revision或结束新查询。独立审查无Critical/Important，提出的历史分支覆盖已补充。

页面状态5项、工作台/分页契约、三项强制规范契约与构建均退出0。构建保留原有大文件提示，未在本批拆包。独立测试见outputs/progress-page-load-20261018；5174原进程返回旧模块，已仅刷新本机前端，源模块核对及ael实页列表通过，后端PID4640保持；正式不变。没有宣称抑制Axios全局迟到错误提示，也没有真实写入验收自动保存。
