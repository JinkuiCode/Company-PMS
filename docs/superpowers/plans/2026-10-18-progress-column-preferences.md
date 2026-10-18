# 项目进度列偏好共享模块迁移

> **For agentic workers:** 使用 executing-plans 在当前对话执行，复用当前分支及已批准的旧页分批接入方案。

**Goal:** 项目进度列设置接入账号隔离、版本保护和安全存储，同时保留已有偏好。

**Architecture:** 为共享存储增加可选旧选择字段名适配，仅进度页使用 `selected_sheet_field_keys`；保留原账号键和旧程序可读字段。页面提供当前字段/列ID集合，业务查询、排序和权限不变。

**Tech Stack:** Vue3、TypeScript、现有纯行为测试及真实浏览器隔离测试。

## Global Constraints

- 沿用用户批准的治理共享模块迁移；仅Mac，不改后端接口、授权、数据库或正式环境，不提交/合并/推送。
- 默认共享存储行为及档案旧格式不变；只读不能迁移写回，未知版本/损坏/其他归属拒绝覆盖，存储拒绝不能阻断查询。
- 原键 `pms_project_progress_list_columns_v2:<owner>` 保持；新写入同时保留 `selected_column_keys` 和 `selected_sheet_field_keys`。

## Task 1：共享旧字段适配

**Files:** `frontend/src/list-system/columnPreferences.ts`、`frontend/tests/column-preferences.test.mjs`。

**Interfaces:** `createColumnPreferences`新增可选 `legacySelectionKey?:string`。读取仅在标准字段缺失时读取该别名；写入规范字段并镜像别名，身份/版本检查仍先执行。

- [x] 编写行为测试，旧字段读回有效列且原文不变，写入v1双字段兼容；标准字段优先，未来版本不覆盖，账号隔离及存储异常保持。
- [x] `cd frontend && node tests/column-preferences.test.mjs`，确认旧别名未恢复的RED。
- [x] read中传入 `selected_column_keys: value.selected_column_keys ?? (options.legacySelectionKey ? value[options.legacySelectionKey] : undefined)`；write中先规范化，并在版本/归属字段前构建别名，防止覆盖保护元数据。
- [x] 同一命令GREEN。

## Task 2：进度页适配与验收

**Files:** `frontend/src/views/project/ProjectList.vue`、`frontend/tests/progress-column-preferences-browser.mjs`、共享索引、change.md及本计划。

**Interfaces:** 页面 `readStoredColumnPreferences():ColumnPreferenceState|null` 作为旧业务形状适配；`persistColumnPreferences()` 调用共享write，保留既有就绪/恢复门禁。schema.allowed为可列表化动态字段原始key，fixed为当前基础列ID和全部有效动态sheet列ID。

- [x] 先写真实浏览器隔离用例：旧偏好恢复、无效字段清理、账号隔离、未来版本不覆写、拒绝存储仍可查询；所有API模拟、不写业务数据，观察RED。
- [x] 增加共享存储实例，`pageKey:'project-progress-list'`、`legacyPrefix:COLUMN_STORAGE_KEY`、`legacySelectionKey:'selected_sheet_field_keys'`；复用当前owner解析，不匿名读写。
- [x] 递归收集基础列ID并加入所有有效sheet列ID，不因当前取消勾选丢弃以后恢复所需布局。读取转换回旧形状；写入传入标准字段。保留操作列尺寸规范化。
- [x] 单元及浏览器GREEN，复用并运行工作台/分页契约和页面状态回归；三项强制规范契约、`npm run build`。
- [x] 独立审查、记录实际接入和边界；不将其余页面或其他三种共享行为报为完成。

## 实际结果

2026-10-18：共享别名单元RED→GREEN（7项）；真实进度页版本化写入RED→GREEN。独立审查发现当前未选有效列布局丢失，补充实际RED并仅在页面适配合并旧有效缺失状态，当前grid优先；增量复审确认Important解决，无剩余Critical/Important。浏览器覆盖旧选择/宽度、未选列冻结/排序、损坏/未来/异属缓存保护、账号隔离、读取和写入拒绝仍可查询。所有API模拟，无真实业务写入。

工作台/分页、三项强制规范及构建均exit0；状态两页浏览器回归exit0。构建保留既有大文件警告。证据outputs/progress-column-preferences-20261018；正式不变，不提交推送。Mac5174入口将在下一批最终刷新时一并核对，本批隔离5198页面不称为正式或5174现场验收。
