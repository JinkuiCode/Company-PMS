# 项目档案产品线首列：本地候选

日期2026-10-21；原人类批准 `call_0d38cb25f7e84b269a6ded5ce7b702bd`已直接核对。基线A0 `0fe7fd038cfec570f3ec5b4e03d9088f8134e617`，工作区archive-enum-options/PMS、分支codex/archive-enum-options。没有部署、合并、推送、后端/数据库、ERP、权限或字段业务规则变化。

## 结果与兼容

- 默认列：勾选工具列（有权限时）→产品线→项目编号→原其他列。两业务列仅initialPinned左冻结，配合maintainColumnOrder；不永久锁定产品线。名称及元数据仍取原授权接口，不展示ID，不因列布局扩权。
- 旧个人偏好及命名方案做一次补显/位置/必要冻结兼容，其他列宽、隐藏、相对顺序、排序、条件及条数保留。旧编号/名称的隐藏状态与选列元数据对齐，避免迟到的列更新覆盖旧隐藏；没有已存布局时保留原默认编号倒序。
- 受控可选layout_version仅在schema.layoutVersion显式启用时透传；未来/非法版本拒绝覆盖，未知字段不透传，owner/page/schema_version保持。个人兼容成功后有界保存；命名方案读取只做投影，仍由原显式保存动作写回快照。
- 新版本中用户主动隐藏/移动/取消冻结可保持，恢复默认重新采用新布局。初始化只读一份快照并共用于选列、状态、排序，防止短暂读取失败把默认布局写成迁移结果。失败提示不冒充已保存，损坏/未来原串不删除。

## 验证与证据

`.runtime/p28-product-line/evidence/final-checks.json`记录完整命令与退出码：本批17项适用检查通过，包括项目规定的前端三项全局契约、档案筛选、数据字典/枚举、构建，以及列偏好/本页布局/短暂读取恢复、档案旧方案/共享方案协议、A0加载与确认回归。没有改共享query workspace/C1源文件，不能据此声称已组合C1实现。

实际Vue＋AG Grid合成验收15组通过：默认首列与冻结/滚动、有无勾选、旧个人偏好与其他冻结/隐藏/排序、列设置移动/取消冻结/隐藏后刷新、恢复默认、短暂读失败、当前版偏好、旧命名方案与明确保存、元数据拒绝、坏/未来存储、写失败、名称失败及既有重试、未知历史产品线、办公蓝/青绿/石墨三主题。截图人工核对，0页面异常、0业务写入、0外部请求。浏览器报告 `.runtime/p28-product-line/evidence/browser/verification.json`，A0另6组页面回归输出 `a0-browser-regression.log`。临时Vite仅127.0.0.1:5191，无后端，未访问已有库。

额外执行的 `project-list-column-preferences-contract.test.mjs` 有1项旧源码断言失败，要求ProjectList保留已不存在的私有columnPreferenceStorageKey。该测试及所读ProjectList/PmsListColumnPicker三文件与基线字节完全相同，私有基线副本同样exit1（见`preexisting-contract/evidence.json`、baseline.log）。这是暂停中的项目进度旧测试，不是本批行为回归；未改源文件或放松断言。不能将所有额外测试统称全绿。本批实际共享列行为与账号/页面隔离由column-preferences测试通过证明。

独立复审发现的短暂读取覆盖问题先RED复现，再单快照修复GREEN；非空customer查询条件亦验证到合成请求且原方案存储不因读取改写。最终无遗留Critical/Important/Minor；git diff --check通过。构建体积和AG Grid弃用提示为既有警告。

## 公共说明精确组合条目

后续由单一集成人在archive页面说明增加（本批不修改公共registry.ts）：

> 产品线列：默认位于勾选列之后、项目编号之前，产品线和编号初始左冻结。旧个人布局和查询方案首次兼容，保留其他设置；之后可在列设置中移动、隐藏或取消冻结，保存后按个人选择显示。恢复默认会恢复产品线首列。字段不可见时仍遵守当前授权；名称无法读取时显示“名称暂不可用”，不显示内码。

## 固定与下一步

`.runtime/p28-product-line/candidate/manifest.json`绑定实际独立提交、源码增量、补丁、200份前端构建和摘要。原A0包保留。此完整dist含A0/P28，**未组合E1/C1/C2**，不得直接覆盖正式或另一线成果。后续A1/A2已各自获得本地范围批准，但只在本批交付后顺序接续；真实库升级、正式窗口及合并推送仍无授权。
