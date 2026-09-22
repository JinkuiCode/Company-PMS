# 两张报表后台 Excel 导出实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 库存隐藏内码；两张报表按筛选与权限后台导出，不设业务条数上限，采购同时包含主表和订单、入库明细。

**Architecture:** PMS 保存持久化导出任务；单工作任务串行读取金蝶只读数据源，分批写 Excel。复用当前产品线、项目范围和采购来源关联校验；执行与下载均重新校验权限。

**Tech Stack:** FastAPI、SQLAlchemy、XlsxWriter constant_memory、现有 Vue 标准列表。

## Global Constraints

- 不改 OA 登录、金蝶业务数据或已有角色授权；继续使用两个独立 export 权限。
- 不重启服务器、SQL Server 或 OA；生产升级须单独备份校验和升级身份。
- 主表按显示列顺序导出，采购强制保留申请单号与行号用于关联。
- 每张 Excel 表达到行数上限后自动续表，不静默截断。
- 文件仅通过鉴权接口下载，保留24小时；失败删除残缺文件。
- 同一用户只允许一个待完成任务，全系统同时执行一个任务；不限制结果条数。

## Task 1: 工作簿与字段

Files: `backend/app/services/report_workbook.py`、`inventory_fields.py`、`inventory_reader.py`；`backend/tests/report_export_contract.py`。

- [x] 先测试分Sheet、公式文本安全、FID不可见不可筛选，确认失败。
- [x] 实现按行写入和超限续表，测试通过。

## Task 2: 后台任务与权限

Files: `backend/app/models/report_export.py`、`services/report_export_jobs.py`、`services/report_export_data.py`、`api/report_exports.py`、`main.py`、数据库版本和初始化。

- [x] 先测试独立权限、任务所属用户、重复任务、范围变化和采购关联，确认失败。
- [x] 实现提交、查询、下载、串行工作线程、失败与过期处理。
- [x] 补充实际队列执行、大数据、异常与升级回归验证。

Interfaces: `POST /api/report-exports` 接收 report、parameters、columns；`GET /api/report-exports?report=` 返回本人最近20次任务；`GET /api/report-exports/{id}/download` 鉴权下载。

## Task 3: 统一导出入口

Files: `frontend/src/components/ReportExportControl.vue`、`api/reportExport.ts`、两个报表列表。

- [x] 先增加前端导出契约并确认失败。
- [x] 接入导出按钮、任务进度、下载，构建通过。
- [x] 浏览器检查提交、恢复任务、下载、权限和两种屏幕尺寸。

## Task 4: 验证与交付

- [x] 运行前端标准样式、列表、系统UI、字典、枚举与报表检查。
- [x] 运行后端报表、RBAC、数据库升级、字段目录与枚举检查。
- [x] 只读检查真实金蝶导出；代码复核发现的临时表扫描、筛选状态不一致及任务按钮禁用均已修复，最终复核通过。
- [x] 更新报表说明及 change.md。
- [ ] 生产发布独立执行升级与验证；需要凭据时由用户本地输入。未完成发布不得声称服务器已更新。

2026-09-22：用户已单独批准本次数据库升级及PMS部署，进入发布准备。
