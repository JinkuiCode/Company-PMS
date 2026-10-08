# PMS紧凑工作区实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 按已确认的compact-workspace样稿迁移正式页面，恢复采购快捷筛选。

**Architecture:** 复用共享主题、表单、列表和报表查询模块；密度只影响布局和控件，不修改业务接口。采购快捷项操作现有conditions，分页、排序和导出继续使用已成功查询的快照。

**Tech Stack:** Vue 3、TypeScript、Element Plus、AG Grid、Playwright。

## 全局约束

- 2026-10-08用户“可以，开始调整”批准本地正式实施；复用当前codex/pms-stock-detail-report，不新建分支，不提交、合并、推送或部署。
- 唯一视觉基线：`frontend/prototypes/compact-workspace/`最终24px版本；字体修复及正式44px勾选列保留。
- 页头44、外边距6、面板内距8、查询24/12px、正文13、行32、表头30/分组26、分页26、抽屉460/普通输入32。
- 不修改OA外层、认证、权限、数据库、ERP口径及现有个人列偏好存储键。
- 浏览器用隔离模拟API验收，不登录真实账号、不写真实业务数据。

## 任务1：共享布局和档案试点

文件：`AppLayout.vue`、`pms-theme.css`、`form-tokens.css`、`PmsDataList.vue`、`PmsListFilters.vue`、`CustomPagination.vue`、`GridHorizontalScrollbar.vue`、`PmsFormDrawer.vue`、`config/listUi.ts`。

- [x] 添加正式浏览器密度验收，先验证当前页头56/菜单展开与目标不符。
- [x] 将尺寸集中为主题令牌，查询容器标记`.pms-query-density`；表单模块只在该容器缩小查询控件。保留表格单元格编辑和详情行内编辑32px。
- [x] 默认菜单收起为64px图标栏，悬停展示下级菜单，提供可键盘操作及展开状态提示的菜单按钮，展开仍184px；保留PMS标识。此项按用户验收反馈修订，覆盖原完全隐藏样稿。
- [x] 全局AG Grid配置`rowHeight:32, headerHeight:30, groupHeaderHeight:26`，移除页面重复尺寸；普通及分组标题居中，正文保持原语义对齐。
- [x] 共享新增/编辑抽屉460px，头部12px/16px、内容0/16px/12px、底部8px/16px、字段行5px；不将现有详情编辑改交互。
- [x] 运行试点浏览器及契约，核对查询24、勾选列44、新增32、分页26和可视高度。

## 任务2：项目进度及三报表

文件：`report-query/query-surface.css`、共享查询组件、`PurchaseProgressList.vue`、`InventoryList.vue`、`StockDetailList.vue`、`purchaseQuickFilter.ts`及测试。

- [x] 添加快捷状态函数测试，先运行确认缺少实现。
- [x] `selectedPurchaseProgress(conditions, values)`识别全部、单一equals、自定义；`withPurchaseProgress(conditions,value)`仅替换progress条件；`restorePurchaseProgress(conditions,legacy)`只在不存在规范条件时补入旧progress。
- [x] 添加六个轻量按钮，使用metadata.progress_labels显示名；点击提交当前条件，成功后第一页。全部仅清除progress，保留其他条件；错误仍保留旧结果。
- [x] 保存、恢复、条件弹层与快捷选中态共用conditions；恢复不自动查询。未查询草稿不影响旧分页/导出快照。
- [x] 查询/方案控件统一24px，常用宽112、搜索180、日期220、方案144；多选标签不越框。移除报告强制36px行高，清理小屏700px分页撑出页面的覆盖。
- [x] 浏览器验证六状态、条件替换、自定义、旧方案、分页、导出快照、错误重试及三报表必填条件。

## 任务3：系统页面、规范及收尾

文件：共享主题、系统列表必要局部布局、`docs/PMS-UI-STANDARD.md`、`AGENTS.md`、`change.md`及既有验收规格。

- [x] 管理页工具栏24、表格32/30、分页26；字段目录使用全局Grid尺寸；所有字段标题居中，不改变表格业务操作。
- [x] 检查用户、角色、枚举、参数、产品线、字段规则、日志、同步、菜单等页面，保留各自信息结构。窄屏换行或内部滚动，不让页面横向溢出。
- [x] 更新过时尺寸测试和项目规范，注明规范适用查询区/普通表单/行内编辑三类容器；记录当前实施验证结果。
- [x] 运行：`node tests/style-contract.test.mjs`、`list-standard-contract`、`system-ui-consistency-contract`、`archive-filter-contract`、`list-density-contract`、`list-navigation-polish-contract`、`form-system-layout-contract`、`report-query-state`、`purchase-quick-filter`、相关模拟浏览器、`npm run build`与`git diff --check`。
- [x] 浏览器1366/1920/390px及OA剩余宽度检查、截图与批准样稿直接比对。完成后交付开发机验收，不部署。

## 交付证据

2026-10-08：16项契约/单测、档案/进度/三报表/系统抽屉浏览器回归、字体DPR1/2检查及最终构建退出0。OA剩余宽度使用1182px隔离视口，不代表真实OA与Windows实机验收。截图位于`.runtime/compact-formal-*`及相应浏览器输出目录。保持当前分支未提交改动，不部署、不合并、不推送；详见`change.md`本批记录。
