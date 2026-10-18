# 项目进度新增表单会话与字段适配

> **For agentic workers:** 按 executing-plans 在当前对话实施，复用已批准治理规格及现有分支。

**Goal:** 进度新增表单采用共享会话和字段错误适配，防止重复保存、未保存内容误关闭，失败保留输入。

**Architecture:** 复用useFormSession、resolveFieldMetadata、mapFormFieldErrors；保持原620px新增窗口和侧详情/表格编辑路径，不进行视觉重设计。页面只负责业务快照payload、核心字段上限及字段名到表单prop映射。

**Tech Stack:** Vue3/TypeScript/Element Plus及现有隔离浏览器测试。

## Global Constraints

- 本批是用户已批准的共享行为旧页迁移，不新增接口/权限/表结构，不部署、不通知，不提交推送；真实业务写入不在本机验收范围。
- 引用和计算字段保持只读；服务端仍是最终权限/字段校验。项目档案、部门、项目经理原有三项核心必输保持。
- 保留表格自动保存及详情已有保存/切换逻辑，本批共享会话只包围新增窗口。
- 保存期间锁定输入、关闭和重复提交；失败保留输入并按当前可见表单顺序展示字段错误。未保存关闭可放弃或继续填写，不增加服务器草稿功能。

## Task 1：新增会话

**Files:** `frontend/src/views/project/ProjectList.vue`、`frontend/tests/progress-form-session-browser.mjs`。

**Interfaces:** `useFormSession({draft:form,clone:JSON语义复制})`；open重置后capture；submit使用 `validate/save(snapshot)/onError`，成功才关闭并刷新；关闭通过 `requestClose` 单次确认，路由离开复用同一入口。

- [x] 写全API模拟的真实页测试：无修改关闭、修改取消关闭保护、无效表单不POST、快速两次提交仅一次、保存期间禁用及不能离页、422处理期间保持锁、失败保留输入、按表单顺序显示字段错误、修正后重试成功。
- [x] 执行 `node tests/progress-form-session-browser.mjs`，确认原页面缺少未保存关闭保护而RED。
- [x] 新增 `projectCreateSession`；handleSubmit委托submit，payload完全来自snapshot；按钮loading、form disabled和关闭/路由保护消费相同busy/dirty状态。保留既有权限判断及业务条件。

## Task 2：字段与错误适配

**Files:** 同页、`frontend/src/page-guide/registry.ts`。

**Interfaces:** `resolveFieldMetadata(policy,ceiling)`；核心必输与引用/计算只读用ceiling表达。`mapFormFieldErrors(error,fieldsInOrder,visible)` 后由页面映射 `project_start_date→start_date`、`original_planned_ship_date→end_date` 和动态 `project_values/sheet_values`。

- [x] 为当前新增控件按顺序建立key/prop目录；刷新字段规则后，统一映射结构化错误，仅保留仍可见的新增控件；沿用档案的PmsFormField错误及控件ARIA关联，定位第一项，输入改变清理已过时的提示。验证和保存期间各统一控件显式消费busy禁用状态。
- [x] 原visible/editable/required函数消费共享解析器；产品类别隐藏和引用/计算只读保持，核心三项必输与校验一致；动态新增控件保留既有来源和required筛选。
- [x] 说明补充新增保存、关闭保护、失败重试和列偏好/加载规则，不放技术标识到业务界面；将已有说明入口从详情体移到标准列表工具栏，避免必须打开单据才能查看说明，不重复展示两个按钮。
- [x] 浏览器GREEN；`node tests/form-session.test.mjs`、`node tests/field-metadata.test.mjs`、`node tests/field-policy-contract.test.mjs`、工作台/分页及两页状态、列偏好隔离回归；三项强制规范和`npm run build`。
- [x] 独立审查及Mac5174只读入口复核；不做本机真实项目新增。记录change.md、索引和当前计划，仅标记本批适用能力。

## 实际结果

2026-10-18完成Mac接入及独立审查。新增会话使用独立快照，验证/保存/异步错误定位互斥；统一控件显式消费busy。未保存关闭及路由离开复用同一确认，失败保留输入。PmsFormField与控件ARIA承接服务端错误，使用当前可见控件顺序；直接body日期别名适配不改变嵌套字段语义，计算明细有只读代码上限。

RED证据：原缺少关闭保护、列表缺少说明入口、日期API别名提示缺失、错误开放计算明细导致额外必输，均已由对应隔离浏览器用例观测。途中还定位到整体form禁用未传递及ElFormItem服务端提示不稳定，已沿用档案的显式控件状态/PmsFormField模式；未改变共享控件全局实现。

最终真实浏览器全API模拟通过：干净/脏关闭、无效不提交、快速重复仅一次、保存期间输入和导航锁、错误定位等待期间锁、失败保留、固定/日期/动态嵌套字段顺序及ARIA、修正后重试。会话9项、元数据5项、字段策略/工作台/分页、说明7项与三项表单契约、三项必需规范及构建均exit0；列偏好与两页状态浏览器回归通过。独立审查日期Important和动态覆盖Minor均已解决，无剩余Critical/Important；既有大文件/AG Grid弃用提示未在本批扩展处理。

标准5174已仅刷新前端至PID16454，实际ael列表、说明入口及空新增窗口/取消只读核对通过；后端仍PID4640，未真实创建项目。正式仍v1.1.0，三批新前端修改留功能分支工作区，未提交/合并/推送/部署。证据位于outputs/progress-form-session-20261018。全局Axios短暂错误消息仍沿用原有格式，本批只保证表单字段投影，不声称抑制所有未知或迟到消息。
