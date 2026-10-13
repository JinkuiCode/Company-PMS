# 列表进入规则、必输标记与紧凑操作列 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 按用户2026-10-13批准的同版方案在开发机统一单据自动查询、报表待查询、红星必输标记和内容适配操作列，交付验收，不部署。

**Architecture:** 查询方案加载仍由PmsQueryWorkspace独立负责，新增显式document/report进入模式，仅单据在个人默认方案恢复和依赖就绪后自动执行一次查询。PmsQueryConditionRow复用字段required及现有危险色，在字段框前显示星号。listUi提供64px单按钮、96px双按钮和多按钮宽度，迁移仅操作列状态，不改变业务列偏好。

**Tech Stack:** Vue3/TypeScript、Element Plus、AG Grid、Playwright；权限报错先只读定位，单独获批后才修复。

## Global Constraints

- 复用当前codex/pms-unified-query原目录，保留既有未提交文件，不合并、不推送、不部署正式环境、不升级数据库。
- 控件24px、字体12px、正文及行高沿用现有紧凑规范，不压缩业务编辑器。
- 红星只表示现有必输规则，不新增业务必输条件；移除物料（必填）、产品线（必选）标签文字。
- 单据加载按当前用户默认方案查询；必输默认值不足时保留待输入，不绕过校验。重选/保存方案不触发新的隐式查询。
- 报表页面初始化仅读取元数据；保留采购总表明细联动和用户明确查询路径。

## Task 1: 共享查询控件

- [x] 新增隔离真实Vue浏览器测试：document默认方案自动执行一次、report无自动业务查询、必输空值阻止查询、普通条件无星号、必输条件星号位于字段前；设置详情同样显示。
- [x] 在PmsQueryWorkspace新增entryMode，等待ready、loading结束以及方案初始化后仅执行一次；用户改变身份或listKey后重置初始化票据，旧异步不覆盖新状态。
- [x] PmsQueryConditionRow给字段选择容器增加required标记及可访问说明；label仍保持物料/产品线，使用表单同色星号且不增加行高。
- [x] 浏览器先RED再GREEN；query-workspace及条件竞态测试回归。

## Task 2: 页面接入与操作列

- [x] 项目档案/项目进度/任务列表/问题提报及系统列表显式document模式，三个报表显式report模式。
- [x] 档案自动查询经submitArchiveQuery应用个人条件、分页和列偏好；问题提报移除重复手写首查，仅保留统计读取。
- [x] listUi新增pmsActionColumn(count)及规范化状态函数，保留默认双按钮常量作为既有接口。
- [x] 单按钮档案/采购/提报/任务/参数/日志64，双按钮进度及管理96，多按钮枚举/字段按内容适配；无操作列库存报表不增加列。
- [x] 旧个人方案/列布局仅归一操作列width/flex/pinned/hide；业务列顺序、宽度和筛选保留。
- [x] 真页面隔离测试覆盖档案首次请求包含个人默认条件、单据重新进入刷新，报表进入不请求业务API，操作列64/96及旧偏好修正。

## Task 3: 权限报错（仅获单独批准后）

- [x] 根因：normalize_role_menu_ids只寻找同父B节点查看；feedback:view位于C节点，故feedback:add保存报错。
- [x] 获批后补后端回归：仅新增/补充补齐有效同模块父菜单查看；缺失、禁用或不同模块仍拒绝；不附加handle/retry。
- [x] 前端角色恢复保存保留菜单自身查看，兼容旧子按钮结构；不修改任何实际角色配置。
- [x] 运行RBAC、反馈升级及角色浏览器回归，保持权限变更接口和数据库结构不变。

## Task 4: 验证与交付

- [x] 执行style-contract、list-standard-contract、system-ui-consistency-contract、archive-filter-contract及npm run build；针对新增组件跑行为测试，不仅检查源码字符串。
- [x] 开发机真实Edge页面确认档案自动读取、收发必输红星、采购操作列，留存无凭据截图；不能把模拟API测试等同真实ERP数据验收。
- [x] 更新AGENTS.md、docs/PMS-UI-STANDARD.md及change.md，记录实际变化和证据，说明未部署服务器及权限修复批准状态。
