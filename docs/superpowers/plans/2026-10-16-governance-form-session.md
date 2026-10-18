# 表单会话与保存控制实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans 按本计划内联实施并验证，不另建工作区。

**Goal:** 落实治理定稿规格第四节的表单会话标准，在档案新增抽屉试点，不改变既有布局和业务规则。

**Architecture:** 独立 `useFormSession` 接受页面草稿，管理原值、脏状态、验证/提交互斥、失败及冲突状态、关闭确认。页面继续负责字段规则、接口、错误定位和业务成功后的刷新。维护/审批的版本校验和两阶段提交保留既有实现，本批不替换。

**Tech Stack:** Vue3、TypeScript、Node test、Playwright Edge。

## Global Constraints

- 依据2026-10-14/15定稿规格和2026-10-16“先不用部署到正式环境，继续之前方案中计划的内容开发”的批准；仅本机开发。
- 复用当前 `codex/pms-unified-query` 和既有抽屉、字段、主题；无新视觉模块，不改权限、接口、数据库、真实业务数据或金蝶/邮件状态。
- 不合并、推送、打包正式候选、部署或发布通知。
- 原有数量修复及其他任务资料完整保留。共享模块按试点验收后再逐批迁移，不一次改全部表单。

## Task 1：共享控制器及行为测试

Files: 新增 `frontend/src/form-system/useFormSession.ts`、`frontend/tests/form-session.test.mjs`。
接口：`useFormSession({draft, clone?, equals?, isConflict?})` 返回 `original/dirty/phase/busy/error/capture/restore/submit/requestClose`；`submit({validate,save})` 返回 success/invalid/busy/failed，失败含原异常。`save` 只消费提交快照。

- [x] 先写行为测试：深层草稿与原值隔离；验证期间第二次提交拒绝；验证失败不写；失败/409保留草稿可重试；成功仅确认实际提交快照；保存期间不得重置或关闭；关闭确认只打开一次且取消不丢草稿。
- [x] 运行 `cd frontend && node --test tests/form-session.test.mjs`，确认缺少控制器导致断言失败。
- [x] 实现最小控制器；互斥在第一次await前生效，所有异常路径释放状态；关闭确认与提交互斥。
- [x] 重跑行为测试退出0。

## Task 2：档案新增试点与页面验证

Files: `ProjectArchive.vue`、`form-system/index.ts`；新建 `tests/archive-form-session-browser.mjs`；维护已有抽取测试绑定。

接入：`const archiveCreateSession = useFormSession({draft:form,isConflict: error => error?.response?.status === 409})`；`archiveCreateSaving = archiveCreateSession.busy`。打开时capture；关闭委托requestClose；保存委托submit，保留原字段错误定位和成功提示，payload使用save收到的快照。

- [x] 先写浏览器流程：验证期间快速双击仅一请求；失败留值、继续编辑重试；必填/数量拒绝不请求；取消关闭保留草稿、确认放弃关闭；成功关闭且刷新。所有API完全模拟，拒绝外部网络。
- [x] 运行浏览器，确认旧页面快速双调用验证可复现重复写入；若已有控件节流遮蔽，用组件真实提交入口验证控制器接入，不弱化覆盖。
- [x] 替换新增页面本地布尔量及JSON原值管理，保留详情保存流程和原字段错误适配。
- [x] 运行新行为/浏览器测试及既有档案数量、字段扩展、字段治理/抽屉测试；项目必需style/list/system规范和build。
- [x] 本机实际页面只读确认既有抽屉与登录可用；不创建真实档案。

## Task 3：记录与交付

- [x] 更新共享模块使用说明、治理跨批跟踪及 `change.md`，区分本批完成与下一批页面状态/列偏好/字段适配待开发。
- [x] 保存完整命令、退出码、源文件摘要及页面证据于 `outputs/governance-form-session-20261016/`；独立审查并解决本批问题。
- [x] 仅本地工作区交付；正式环境保持本批开始时的版本，不通知用户升级。

完成补充：onError纳入同次提交的互斥生命周期；异步字段提示完成才解锁，提示自身失败以presentationError返回，页面明确提醒。实际Mac只读列表与既有详情正常；真实新增被既有金蝶目录依赖阻止，未创建档案，完整写流程只在全模拟API验收。详见同日共享模块记录。
