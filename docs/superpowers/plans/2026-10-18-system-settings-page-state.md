# 产品线与字段规则读取状态迁移

> **For agentic workers:** 使用executing-plans沿用当前工作区逐项实施。

**Goal:** 产品线列表、字段规则列表使用共享状态，加载失败清理旧数据，模块切换及离页不应用旧响应。

**Architecture:** 只替换主列表请求生命周期与就绪判断，沿用已有查询、完整分页和错误/重试样式。产品线组织候选独立保持原请求代次，字段规则保存/恢复默认保持原API及授权。

**Tech Stack:** Vue3、usePageLoad、现有完整读取及全API模拟测试。

## Global Constraints

- 本批属于已批准的系统旧页共享模块迁移，仅Mac，不改变角色授权、产品线范围、金蝶组织绑定或字段规则业务逻辑。
- 接口仍为GET `/product-lines`、GET `/field-policies?module=...`；保存、删除、恢复默认等接口及其条件不变，不执行任何真实写入或金蝶访问。
- 不部署、通知、修改数据库或配置，不提交合并推送；字段目录/枚举结构未变。
- 已有布局和控件保持，字段规则失败仅增加标准错误/重试反馈；不是抽屉或字段编辑重设计。

## Task 1：隔离行为测试

**Files:** `frontend/tests/system-settings-page-state-browser.mjs`。

- [x] 全API模拟两页，拒绝非GET；产品线失败应清除旧行，字段规则快速切换模块后旧响应不能回写，失败可重试、空结果及卸载安全。
- [x] `node tests/system-settings-page-state-browser.mjs`以及单独policy模式执行，分别观察旧行保留、跨模块旧响应的实际RED。

## Task 2：页面适配

**Files:** `frontend/src/views/system/ProductLineList.vue`、`FieldPolicyList.vue`。

**Interfaces:** usePageLoad.begin/isCurrent/succeed/fail/invalidate；ready只在本次ready/empty，loading/failed派生，不保存业务行。

- [x] 产品线保留loadCompleteDataset及身份去重，用ticket检查取消/应用；失败清items并fail；卸载invalidate主列表并使原组织读取代次失效。
- [x] 字段规则每次fetch取ticket，业务行/分组应用前检查；失败清行/分组并fail，保留dirtyKeys原清理时机；卸载invalidate。不修改PUT/重置及元数据权限计算。
- [x] 字段规则增加既有pms-list-load-error模式的role=alert/重试按钮；两页不新增授权或默认权限。
- [x] 浏览器GREEN，页面状态/分页/产品线/字段规则相关契约；三项必需规范及构建。
- [x] 独立审查、change.md/共享索引/本计划记录，仅标记读取状态，不把保存会话等其他系统适配报为完成。

## 实际结果

产品线失败旧行残留、字段规则跨模块旧响应覆盖两项实际RED，适配后两页GREEN；失败/重试、空结果、卸载不回写通过。共享状态及相关前端契约13项、字段目录/枚举后端契约、必需规范和构建均退出0。独立审查无Critical/Important/Minor；仅Mac、全API模拟且拒绝非GET，未执行真实写入或部署。完整摘要及日志在outputs/system-settings-page-state-20261018。
