# 单字段查询与问题提报说明 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline; reuse current approved branch and UI.

**Goal:** 查询方案每项只查询一个业务字段，保留自由组合及旧方案安全提示。

**Architecture:** 复用共享PmsQueryWorkspace及既有元数据；报告默认字段取消综合keyword；收发源读取复用单字段物料谓词，范围验证由reportScope及后端请求边界共同执行。说明复用page-guide注册表。

**Tech Stack:** Vue3/TypeScript/Element Plus/AG Grid，FastAPI/SQLAlchemy。

## Global Constraints

开发机实施，不升级数据库、不部署、不改权限、不合并或推送；现有24px控件与12px查询文字不变。多个条件维持AND。

### Task 1: 默认字段与旧方案安全

Files: frontend/src/views/reports/{PurchaseOverviewList,PurchaseProgressList,InventoryList,StockDetailList}.vue，query-system/report-adapter.ts，views/project/ProjectArchive.vue，views/system/SyncTaskList.vue；frontend/tests/single-field-query.test.mjs及隔离列表行为测试。

- [x] 先测试reportScope新物料字段正向条件与空值、失效旧字段禁查（RED），再实现；新请求库存/采购keyword为空，精确filters分字段。
- [x] 取消各页面综合字段及默认值，收发默认material_code，共享requiredGroup支持至少一项正向条件、动态红星及只保存名称方案；共享控件prepareDefinitions保留旧存储、禁止未确认查询。
- [x] 验证旧默认方案含keyword/material时不首查，独立默认方案首查/报表待查不回归。

### Task 2: 收发数据边界

Files: backend/app/services/stock_detail_{reader,sources,snapshots,catalog}.py，report_filters.py，新stock_detail_material_query.py；frontend/src/views/reports/stockDetailState.ts；backend/tests/single_field_query_contract.py。

- [x] 单字段物料谓词测试先RED：同值在不同字段不交叉命中；snapshot_sql和source_sql都按同一material_field和material_operator生成，只绑定值；等于不误匹配前后缀。
- [x] 使用allowlist物料编码/名称/规格；名称与规格均对应中文2052；新增查询specification元数据及运行描述值，不新增数据库列。
- [x] 运行库存/采购独立过滤、收发源/快照/目录/过滤相关契约，并验证拒绝非法material_field。

### Task 3: 问题提报说明（独立追加批准后）

Files: frontend/src/page-guide/{registry,types}.ts、views/feedback/FeedbackList.vue；说明模型/新页签测试。

- [x] 先测试feedback说明页注册及操作/字段搜索（RED）；复用PmsPageGuide page=feedback。
- [x] 按实际反馈服务核对分类、范围、附件、处理状态、邮件通知与重试说明，保留新页签能力；新增页面接入写入AGENTS.md及UI标准。

### Task 4: 完成验证与记录

- [x] 前端style/list-standard/system-ui/archive-filter契约、相关query/guide测试、npm run build；后端字段目录和枚举契约。
- [x] 隔离真实页面行为＋用户已登录开发机页面核对独立字段、旧方案禁查、物料至少一项、说明弹窗/新页签；只读实查物料编码等于返回1条入库，不改正式数据。
- [x] 独立只读代码复核，修复已确认范围内问题，change.md及开发机验收记录写实际结果。交付开发机待用户验收，不部署或合并。
