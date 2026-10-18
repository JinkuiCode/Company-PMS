# 全局表单合规遗留收尾方案（已批准并完成）

> **For agentic workers:** 使用superpowers:executing-plans内联实施。用户2026-10-16明确批准“同意，仅本机修复这两项”；实施及验证已完成。

**Goal:** 处理本次扩展检查明确发现的两项既有问题，不扩大到其他页面批量迁移。

**Architecture:** 继续使用现有表单框架；只替换版本通知邮件重试确认中的一个勾选控件，既有消息、状态、权限和邮件接口保持；更新契约对既定查询作用域的检查口径。

**Tech Stack:** Vue3、现有PmsCheckboxControl、Node、全模拟API的Edge。

## Global Constraints

- 仅Mac当前工作区。无正式部署、数据库升级、账号授权、真实发信或邮件重试，不合并/推送。
- 原始失败证据：outputs/governance-form-session-20261016/frontend-09.log和frontend-10.log；相关两个源文件与本批开始HEAD一致。
- 旧页控件按批准批次迁移；本批已获得针对版本通知页单控件的独立确认，不扩大为其他页面迁移授权。

## Task 1：查询密度契约

Files: frontend/tests/form-system-contract.test.mjs。

- [x] 保留原表单命名空间要求，额外接受已落地的`.pms-query-density .pms-form-control`前缀；拒绝业务页面前缀、伪同名及逗号混入。
- [x] 添加允许/拒绝选择器用例，先RED，更新检查后GREEN；不改form-tokens.css。

## Task 2：版本通知单控件迁移

Files: frontend/src/release-center/ReleaseCenter.vue、frontend/tests/release-center-browser.mjs或新独立重试确认浏览器。

- [x] 先增加浏览器断言：unknown时原因非空且人工核查勾选后才可确认；waiting/failed保持原条件；忙碌时不可修改；失败保留原因/勾选；无权限用户不显示重试。
- [x] 导入现有PmsCheckboxControl，替换唯一原始el-checkbox，保留v-model、unknown条件、disabled和原文字，补aria-label。不给普通用户增加管理员控件，不改变接口或后端授权。
- [x] 使用全模拟API及已确认控件基线核对显示/键盘勾选/禁用/失败，执行全局adoption、form-system、必需三项规范及build；不接触真实投递。
- [x] 更新模块清单/验收记录与change.md；现有业务说明及人工核查规则保持，不添加纯技术说明。只本地交付，不发布新版本通知。

证据与范围见 [本机收尾记录](../../releases/2026-10-16-form-compliance-local.md)，完整输出为outputs/form-compliance-20261016/。
