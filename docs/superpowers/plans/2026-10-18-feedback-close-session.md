# 提报表单关闭互斥（仅Mac）

> **For agentic workers:** 复用已选executing-plans，在当前分支内完成，不新建工作树或委派实现。

**Goal:** 将已复现的两次并发关闭只保留一次确认，保留已确认的保存/放弃/取消及正文/附件领域流程。

**Architecture:** FeedbackForm.vue只将关闭草稿判断接入现有useFormSession.requestClose；使用明确的正文/附件快照适配，附件File保留身份、不转JSON或上传。正文提交、submission_id、saved中间结果、附件循环和版本冲突仍由原控制器负责，不把分步操作改为单次通用submit。

**Tech Stack:** Vue3/TypeScript、现有统一表单；实际Vue refs/watch及真实控制器代码的隔离测试，模拟API；真实浏览器全API隔离复验。

## 批准与边界

用户已批准call_e4f447331a1c45afbde5ce81fe0c8b02，仅Mac修复及验收；不改接口、权限、数据库、正式或Git，不提交真实提报、上传真实附件或发邮件，已固定a3候选不改。布局、按钮、文案与现有统一控件保持，使用ui-craft已有项目基线；无新的视觉设计事项。

## 实施与验证

Files：frontend/src/views/feedback/FeedbackForm.vue、frontend/tests/feedback-close-session.test.mjs、page-guide/registry.ts配套说明；隔离浏览器测试；本计划、change.md。

- [x] 将源码guard双调用复现提升为先失败的行为契约：一次确认、取消保留、放弃允许关闭、保存只提交一次；保存失败拒绝关闭。
- [x] 接入共享requestClose；初始化与保存成功更新基线，文件身份及顺序参与脏判断，失败/附件未完保留原状态。
- [x] 验证正文已存/附件失败后重试不再创建正文，附件版本续传；409保留和原API payload不变，验证期间不触发真实网络。
- [x] 六类共享会话回归/提报契约；style-contract、list-standard-contract、system-ui-consistency-contract和npm run build。
- [x] 本地模拟浏览器验收，独立审查，更新change.md和总台账；不能阶段完成后忽略其他已批准工作。


实际结果：原并发关闭2项RED→最终6项GREEN。独立Minor（确认回调持锁时capture无效）补保存成功后dirty=false/再次guard不确认的RED→GREEN并关闭；共享会话及提报契约、三项规范和最终构建通过。最终浏览器全API模拟通过；5198桥接写文件后缓存旧模块已明确并只重启该临时服务后复验。5174空新增/取消零提交；刷新前端后最终模块已验证，后台PID4640保持，无真实邮件/ERP/库/授权/Git。证据见outputs/governance-finish-20261018。
