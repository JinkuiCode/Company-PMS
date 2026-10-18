# 页面数据状态与过期响应控制实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans 内联执行。

**Goal:** 落实已确认治理第四节的页面状态和迟到响应控制，以项目档案现有列表试点。

**Architecture:** 新增无业务耦合的 `usePageLoad` 管理待查询、加载、有结果、空结果、失败及请求代次；页面继续管理数据/查询/分页/错误文案。只替换原来分散的请求序号和加载布尔量，不新增控件。

**Tech Stack:** Vue3、TypeScript、Node test、模拟API的Edge。

## Global Constraints

仅本机、当前已批准工作区；不改API、权限、字段、数据库、实际业务数据、默认查询/排序/列筛选口径；不合并推送、部署或通知。

## Task 1：状态控制器

Files: 新增 `frontend/src/composables/usePageLoad.ts`、`frontend/tests/page-load.test.mjs`。
接口：`usePageLoad()` 返回只读 `phase/loading/failed/hasQueried/error`，`begin():number`、`isCurrent(ticket):boolean`、`succeed(ticket,empty):boolean`、`fail(ticket,error):boolean`、`invalidate(pending=false):void`。

- [x] 先写测试，覆盖初始待查、加载、空/非空、错误后重试、旧成功/旧失败不得污染新状态、等待防抖立即使旧请求失效、销毁后拒绝结果和各页面独立。
- [x] `cd frontend && node --test tests/page-load.test.mjs`确认缺少控制器的RED，再实现状态转换并验证GREEN。

## Task 2：档案试点

Files: `frontend/src/views/project/ProjectArchive.vue`、`frontend/tests/list-pagination-contract.test.mjs`，新增 `frontend/tests/archive-page-load-browser.mjs`。

- [x] 写全模拟API浏览器测试：制造旧查询慢于新查询、新数据先到后旧数据不得覆盖；失败显示重试，重试成功；卸载后旧响应不得污染重新进入页面。
- [x] 保留现有数据赋值和分页纠正路径，使用 `isCurrent` 拒绝旧结果，使用 `succeed/fail`更新状态；排序防抖用 `invalidate(true)`，销毁用 `invalidate()`。
- [x] 运行相关状态/分页/档案表单回归、必需3项规范及build，实际Mac列表只读核验。
- [x] 更新文档/跨批跟踪/change.md，保存结果；不据此宣称其他页面已迁移。
