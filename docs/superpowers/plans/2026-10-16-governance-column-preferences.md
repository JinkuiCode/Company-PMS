# 列偏好共享模块实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans 内联执行。

**Goal:** 落实治理规格第四节的账号/页面隔离、失效字段清理和格式升级，先接项目档案。

**Architecture:** 独立存储适配接受页面键、当前账号和有效列集合；保留既有档案账号缓存键，将无版本数据按v0读取并在下一次用户调整列时保存v1元信息。布局内容保持现有格式以兼容程序回退。固定列位置/宽度仍由原页面适配处理。

**Tech Stack:** TypeScript、Node test、Vue现有列设置。

## Global Constraints

仅当前批准工作区开发，不动真实偏好、账号授权、API、数据库或正式环境；不合并/推送。旧版未带账号的布局兼容仍按原页面流程，不能覆盖新版或其他账号数据。无新增布局或控件。

## Task 1：控制器及行为测试

新增 `frontend/src/list-system/columnPreferences.ts`、`frontend/tests/column-preferences.test.mjs`。
接口 `createColumnPreferences({pageKey,ownerId,storage,legacyPrefix?})` 返回 `key/read/write/clear`；read/write接收 `allowed/defaults/fixed`；read状态ready/empty/anonymous/invalid/unsupported/unavailable。

- [x] RED：账号和页面隔离、空授权不存、v0迁移保留顺序/宽度/冻结/隐藏、失效列和重复列清理、显式空选择保留、未来版本/错误归属拒绝覆盖、存储异常转可处理状态。
- [x] GREEN：实现受控读写；只在明确写入时改变缓存，读不迁移或删除源值；v1包含page_key/owner_id/schema_version及原布局数据。

## Task 2：档案接入与回归

修改 `ProjectArchive.vue`，保留当前固定列调整和布局恢复时机。读取/写入失败用现有消息反馈一次；不让缓存异常导致整个页面不可用。旧未带账号布局只在当前账号缓存为空时读取，显式恢复默认才能删除当前缓存。

- [x] 运行新增行为测试、现有档案默认查询/产品线展示浏览器、页面状态和表单浏览器、三项规范及build。
- [x] 更新标准和接入清单、change.md，保留未迁移页面的状态。

验收说明：旧default-query浏览器脚本仍依赖已取消的页面定位。本批以archive-page-load-browser的当前真实Vue入口验证原账号列宽245、默认主机与编码倒序，产品线旧浏览器回归退出0；不执行无效旧定位或改业务代码迁就它。
