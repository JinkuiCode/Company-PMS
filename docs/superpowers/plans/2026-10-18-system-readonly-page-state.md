# 字段目录与操作审计页面状态迁移

> **For agentic workers:** 使用executing-plans继续当前对话，保留既有工作区及其他任务资料。

**Goal:** 两个只读系统列表使用同一请求生命周期，离页及异步详情切换后的旧响应不能覆盖当前状态或总数。

**Architecture:** 复用usePageLoad，保留已有错误段落/刷新入口、字段目录完整读取、审计服务端分页/查询协议及详情切换。无新接口、角色授权、业务写入或视觉重做。

**Tech Stack:** Vue3、现有查询/分页模块、全API模拟的真实浏览器测试。

## Global Constraints

- 继续用户批准的共享模块旧页分批接入，本批仅Mac；审计可见权限和数据范围不变，不新增导出/日志清理，不部署、通知或Git提交推送。
- 字段目录仍为只读自动生成元数据，不能通过迁移开放编辑。审计仍只显示已有授权内容，后台过滤先于分页。
- loading/failed来自共享状态，查询只允许本次完整成功；错误文案和刷新动作保留。客户端页码夹取须依据成功后的完整结果，不依赖加载期间的空视图。

## Task 1：行为与架构测试

**Files:** 新建`frontend/tests/system-readonly-page-state-browser.mjs`；修改`frontend/tests/list-pagination-contract.test.mjs`。

- [x] 全API模拟真实两页：失败/刷新重试、旧成功/错误、空结果、卸载；审计打开详情时延迟旧select，检查新请求期间旧总数不可回写；字段目录跨页完整读取和成功刷新页码夹取。拒绝任何非GET。
- [x] 执行`cd frontend && node tests/system-readonly-page-state-browser.mjs`，观察旧目录卸载后仍应用结果或审计异步旧总数回写的RED。
- [x] 架构契约要求目录使用共享isCurrent，保留完整数据集检查；用户页未迁移的原serial约束暂保留。
- [x] 审计旧契约若要求已淘汰的PmsListFilters/el-drawer/综合keyword，先在未修改HEAD隔离副本证明原有失败，再对齐已批准的查询工作区、侧边审计和独立字段条件；不为旧检查退回页面布局。

## Task 2：共享状态接入

**Files:** `frontend/src/views/system/DataDictionaryList.vue`、`OperationLogList.vue`。

**Interfaces:** `usePageLoad`的begin/isCurrent/succeed/fail/invalidate；请求前取ticket，业务赋值前检查；异步nextTick/详情切换后再次检查；分页防抖立即invalidate(true)，卸载invalidate并保留旧清理。

- [x] 目录将loading引用共享状态，完整读取取消谓词改为isCurrent，成功后按完整过滤结果夹取页码，失败清行并fail，卸载废弃请求。
- [x] 审计替换serial，保留querySupported及查询v2门禁；详情await后检查ticket再改总数/成功状态；防抖立即失效旧请求，卸载清理timer和详情切换。
- [x] 两页及架构测试GREEN；`node tests/page-load.test.mjs`、`node tests/list-pagination-contract.test.mjs`、`node tests/data-dictionary-contract.test.mjs`和相关审计/说明契约；三项强制规范及`npm run build`。
- [x] 独立审查；更新change.md、模块索引与计划，仅标记本批两个只读列表的状态能力，其他系统表单仍待后续。

## 实际结果

2026-10-18：目录卸载仍应用结果、审计详情异步回写旧total两项真实RED→GREEN。两页接入usePageLoad，保留完整读取、服务端查询版本和分页，失败/刷新/过期错误/空结果/卸载及审计历史总数交错、目录300行跨页与页码验证通过；所有API模拟，非GET拒绝。

共享状态5项、分页/字段目录/审计/说明契约、三项强制规范和构建exit0，独立复跑与审查无Critical/Important。审计旧契约在未改HEAD隔离副本也失败，已仅对齐早已批准的查询工作区、侧边审计及独立业务字段条件；没有退回旧布局。证据outputs/system-readonly-page-state-20261018，含historical-contract-baseline.json。

本批只接入两个只读系统列表的请求状态；没有真实业务、配置、权限或数据库写入，没有部署/提交/通知，正式v1.1.0保持。其他系统列表/表单仍分批继续。
