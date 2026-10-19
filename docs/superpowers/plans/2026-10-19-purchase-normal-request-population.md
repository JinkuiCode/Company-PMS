# 采购申请正常业务统计范围 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Reuse the user's approved inline Mac scope; no Git or production actions.

**Goal:** 固定采购申请为已审核且业务终止正常，取消数据状态查询条件并更新说明。

**Architecture:** `purchase_reader.py` 以共用 `REQUEST_ELIGIBILITY` 同时约束基础选择和详情；总表、明细、候选及后台导出沿用既有基础选择。`report_filters.py` 从查询元数据中剔除 `document_status`，保留展示字段，共享查询方案框架负责失效条件拦截。

**Tech Stack:** FastAPI / Python / SQL / Vue 3 / TypeScript。

## Global Constraints

- 用户确认范围：当前对话原方案及追加取消数据状态条件；仅Mac代码与隔离验证，不操作生产、金蝶业务数据、数据库结构、权限或Git。
- 复用当前 `/Users/jin/Code/PMS`、`codex/pms-unified-query`，保留其他任务文件。
- 日期、授权范围、作废判定、下游关联、计量换算和状态计算保持既有实现。
- 旧方案含已取消字段须明确提示并阻止执行，不自动保存或扩大查询。

## Task 1: 固定申请范围及查询元数据

Files: `backend/app/services/purchase_reader.py`、`report_filters.py`、`purchase_fields.py`；测试 `backend/tests/purchase_population_contract.py` 及现有采购/类型筛选契约。

- [x] 基线采购读取11项、总进度7项、类型筛选8项通过。
- [x] 先新增真实离线关系数据测试：混合审核/终止/未知/空状态，检查分页、详情、候选、导出及比率；5项测试在旧实现出现预期失败。
- [x] 最小实现：`REQUEST_ELIGIBILITY = "h.FDOCUMENTSTATUS='C' AND e.FMRPTERMINATESTATUS='A'"`，共同用于 `request_query` 与 `load_request`；查询字段目录去掉 `document_status`，展示保留。
- [x] 执行采购及报表筛选、导出、权限和字段目录/枚举契约；旧测试枚举行为改用仍可查询的关闭状态，通用测试夹具显式模拟业务终止正常默认值。

## Task 2: 说明、交互和收尾

Files: `frontend/src/page-guide/registry.ts`、`docs/采购进度查询报表说明.md`、`change.md`、本计划及隔离验证记录。

- [x] 更新统计范围、分母、旧方案处理及状态展示说明。
- [x] 浏览器隔离验收：添加条件及方案设置无数据状态，旧方案提示/查询禁用，说明包含新规则；无真实业务写入。
- [x] 前端 `node tests/style-contract.test.mjs`、`node tests/list-standard-contract.test.mjs`、`node tests/system-ui-consistency-contract.test.mjs`、`npm run build`；字段目录/枚举相关后端及前端契约；相关页面说明及采购现有测试。
- [x] 复核差异，记录实际结果到 `change.md`；运行 `python3 ops/check_work_continuity.py`。无Git提交、推送或正式部署。

## 验证结果

采购83项、报表73项契约通过；字段/枚举与必需前端检查、构建通过。隔离浏览器验证完成，审查无阻断项。证据：`outputs/purchase-population-20261019/verification.json`、`browser-verification.json`和截图。源码保留当前功能分支，未提交、合并、推送或发布；日常本机后端未重启。
