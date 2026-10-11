# 统一查询模块与档案试点实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 按已确认样稿落地独立查询模块，并交付项目档案试点供逐批验收。

**Architecture:** 新建 query-system，集中类型、操作目录、校验、条件编辑器和列表适配。档案通过 PmsListFilters 的显式开关接入；后端仅档案接入版本2谓词，未标记旧条件继续原路径。

**Tech Stack:** Vue 3/TypeScript、Element Plus、FastAPI/SQLAlchemy；测试使用本地临时 SQLite 和浏览器隔离数据。

## Global Constraints

- 沿用修复后的样稿、24px查询控件、12px文字、小尺寸多选标签、居中字段名；不修改普通编辑器。
- 条件 AND、多选内部 OR、数字0不是空、区间含两端；新否定匹配不包含NULL/空字符串，旧条件保留原语义。
- 本批不部署、不改数据库结构、认证、RBAC、OA、金蝶；不合并或推送。复用 codex/pms-unified-query。
- 仅档案试点，其他页面逐批验收后迁移。保存方案复用现有方案容器及列偏好，不删除旧缓存；恢复后手动查询。

## Task 1: 独立协议与档案后端适配

Files: frontend/src/query-system/core.ts、backend/app/services/query_conditions.py、backend/app/services/list_query.py；测试 frontend/tests/unified-query-core.test.mjs、backend/tests/unified_archive_query_contract.py。

- [x] RED：新增真实条件行为测试，Node导入共享协议，SQLite经 get_archive_list 验证包含/不包含/首尾、枚举集合、空值/0、日期边界、区间、非法字段和值、旧语义、分页及权限范围；SQL Server编译检查。
- [x] GREEN：统一 operatorsFor / operatorLabel / validateConditions / adaptConditions；后端 build_query_clause 只消费服务端字段目录，条件 schemaVersion=2 才进入新路径；未知版本拒绝422。
- [x] 回归：运行模型测试及档案默认查询/分页/业务字段契约，保持既有排序和类别IN。

## Task 2: 标准编辑器与档案试点

Files: frontend/src/query-system/PmsQueryConditions.vue、PmsUnifiedListFilters.vue、frontend/src/components/PmsListFilters.vue、frontend/src/composables/useListFilters.ts、frontend/src/views/project/ProjectArchive.vue。

- [x] RED：浏览器检查新增属于/不属于、空值无输入、区间typed控件；草稿取消无请求、应用才查询并回页1；多选标签在框内；方案恢复不自动查询、分页沿用条件。
- [x] GREEN：按样稿将编辑器独立移植，官方small配置与弹层归属、外部点击、错误ARIA及焦点恢复；档案显式 unified 开关，字段/枚举/产品线仍来自原目录及权限选项。
- [x] 档案方案：使用现有 PmsReportPlans，保存当前条件、固定查询、每页条数和原列偏好；先校验再恢复，失效字段提示且不改变当前结果；恢复后点击查询生效。
- [x] 浏览器：隔离测试数据覆盖枚举/文本/数字/日期、旧方案、查询/分页/列偏好、无权限及1920/1182/390窗口。真实开发页仅观察，不写业务记录。

## Task 3: 规范与验收收尾

- [x] 更新 docs/PMS-UI-STANDARD.md、规格状态和本项目 change.md，注明试点范围及后续批次。
- [x] 必需前端：style-contract、list-standard-contract、system-ui-consistency-contract、archive-filter-contract、npm run build。
- [x] 审查新旧路径与样稿直接比对，确认数据权限先于筛选、SQL参数化、默认类别/排序及编辑功能未变化。
- [x] 交付开发机档案试点，等待本批验收再接其他页面；不把试点报告为全系统完成。

## 验证记录

2026-10-10：协议/SQL/浏览器测试均经历RED到GREEN；独立审查补充历史人员、MSSQL方括号及键盘焦点三项P2，修复并复核关闭。最终类型构建和规定四项前端契约退出0；后端统一、默认、分页及业务字段契约退出0。浏览器125条隔离数据覆盖方案、旧方案、分页/列宽、无编辑权限、人员、多选边界及日期键盘操作；默认/停用/隐藏类别回归通过。真实开发页当前停在登录页，用户登录后验收；Windows/OA和生产SQL实测未执行。
