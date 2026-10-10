# 项目档案默认查询与排序实施计划

> For agentic workers: Use superpowers:executing-plans in this approved ongoing session.

**Goal:** 固定档案类别多选默认主机，清空全部，项目编码默认倒序。
**Architecture:** 保留既有Vue查询栏、列偏好与分页；多选编码作为archive_category的in条件交给SQLAlchemy分页前过滤。默认排序同时体现于表头和后台，权限依赖与数据库结构不变。
**Tech Stack:** Vue3/TypeScript/ElementPlus/AGGrid/FastAPI/SQLAlchemy。

## Global Constraints
- 继续codex/pms-offline-archive，基线b3660bec，不触碰报表工作区。
- 默认主机、多选OR、其他条件AND、清空全部、编码desc。
- 统一compact控件，Noto Sans SC和现有主题，不增加局部CSS覆盖。
- 无结构迁移，无ERP写入，无权限修改；不推送/合并master。

### Task 1: 查询行为和默认排序
Files: frontend/src/views/project/ProjectArchive.vue；backend/app/services/list_query.py。
Tests: backend/tests/archive_default_query_contract.py；frontend/tests/archive-default-query-browser.mjs。
- [x] RED：后台反序ID数据默认按project_code倒序，多类别in在分页前过滤，非法数组422；浏览器默认主机控件、多选和清空、旧排序偏好及跨页顺序。
- [x] 实施：固定PmsSelectControl multiple，archiveQuery.categories初始化枚举主机值；请求追加 {field:'archive_category',operator:'in',value:categories}，空/不可见省略。backend仅archive_category允许in，校验1至100个正整数；默认order_by(project_code.desc(),id.desc())。
- [x] 排序：保留列偏好布局，但初次初始化applyColumnState({state:[{colId:'project_code',sort:'desc',sortIndex:0}],defaultState:{sort:null,sortIndex:null}})；空排序请求后台回编码desc。
- [x] GREEN：后台契约和隔离浏览器真实组件行为通过；保留现有档案分页契约。
- [x] 必需检查：node tests/{style-contract,list-standard-contract,system-ui-consistency-contract,archive-filter-contract}.test.mjs；npm run build；后台archive_pagination及新契约。复核相关列偏好与查询交互。
- [x] 记录change.md、计划和验收证据，核对差异并提交到既有功能分支。

### Task 2: 代码发布与现场验收
- [ ] 固定包/提交、验证Git历史、所有构建文件及逐文件哈希；服务器当前b3660bec/数据库archive-02/保护配置/健康/无待处理任务核对。
- [ ] 保存当前程序、Git历史、前端和业务哈希。仅停启PMS，快进功能分支，前端入口最后替换，不升级数据库。
- [ ] 现场页面默认主机、多选、清空、编码desc及翻页；业务/ERP哈希不变。记录版本、备份、测试、GitHub未推送/master未合并。代码回退可保持现有数据库。

现场SQL Server 169兼容修复：显式编码排序不再重复追加相同列默认排序，保留ID稳定排序。新增MSSQL编译契约RED/GREEN通过；修正版继续同批准范围发布。
