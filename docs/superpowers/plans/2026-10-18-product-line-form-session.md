# 产品线表单保存会话接入计划

> **For agentic workers:** 使用executing-plans在当前codex/pms-unified-query工作区实施，保留混合工作区资料，不创建分支或工作树。

**Goal:** 既有产品线抽屉复用已批准的useFormSession，统一关闭确认互斥、保存快照、失败保留与重试。

**Architecture:** 保留PmsFormDrawer布局、字段及组织绑定不可改规则；业务校验和原POST/PUT、版本参数由本页适配。删除操作保持独立busy，读取沿用上一批usePageLoad。仅复用共享控制器，不创建新通用组件或改变后端授权。

**Tech Stack:** Vue3、现有统一表单控件、useFormSession、全API模拟的本机Edge。

## Global Constraints

- 延续已批准系统页适用保存会话分批接入及“继续”指示；仅Mac代码和隔离验证，无真实产品线/角色/组织/配置/数据写入，不动金蝶、正式环境、数据库或Git。
- 沿用现有抽屉、组织绑定、必输项、409提示和接口，不新增/扩大权限。POST仍只含organization_id/display_name/sort；PUT仍只含display_name/sort/is_enabled/expected_updated_at，编辑不发送organization_id。
- 保存成功后才关闭；失败保留输入。关闭确认未结束时不接受第二个确认或保存；保存期间禁止关闭/路由切换和输入，取消确认保留草稿。
- 复用已确认字体/语义色和控件；保存青绿、取消琥珀。不存在需要重新选择布局的设计差异。
- 不自行提交/合并/推送；样本、输出和私有文件不加入Git。

## Task 1：浏览器行为回归

**Files:** frontend/tests/product-line-form-session-browser.mjs。

- [x] 模拟全部API及身份，非本机网络拒绝，仅允许指定fixture写路径；编辑fixture绑定组织，不读取真实凭据。
- [x] 同时调用两次close，实际只出现一次未保存确认；确认期间save不得发送写请求。旧代码应产生两个确认或允许保存，观察RED。
- [x] 校验必输、取消/放弃关闭、保存互斥、busy字段/路由锁、409/失败保留输入、成功重试；断言PUT不包含组织字段，新增POST保持接口体，权限不足不写。

## Task 2：页面适配

**Files:** frontend/src/views/system/ProductLineList.vue。

**Interfaces:** useFormSession({draft:form,isConflict})；capture/restore/requestClose/submit；deleting独立ref，saving为deleting或session.busy。

- [x] form建立会话；每次open赋值后capture，close只在requestClose许可后关闭并废弃组织候选请求；确认取消不改form。
- [x] save在原权限/删除busy检查后通过submit调用原业务validate和基于独立snapshot的原POST/PUT，onError保留原错误文案；success才关闭并刷新，不重复执行业务请求。
- [x] 保留组织候选序号、删除路径和全部权限码；输入/辅助查找及按钮使用统一busy，保存/取消沿用语义色，不加新控件。

```ts
const lineFormSession = useFormSession({ draft: form, isConflict: (e: any) => e?.response?.status === 409 })
const saving = computed(() => deleting.value || lineFormSession.busy.value)
// save()消费submit的snapshot；close()先requestClose，再restore并关闭。
```

## Task 3：验收与记录

- [x] `node tests/product-line-form-session-browser.mjs` GREEN（本机5198，全API模拟），重跑系统设置列表浏览器回归。
- [x] `node --test tests/form-session.test.mjs tests/product-line-contract.test.mjs tests/page-load.test.mjs`，三项必需规范契约及`npm run build`均退出0；当前相同后端未改，可复用产品线API契约证据。
- [x] 独立只读审查，关闭Critical/Important；记录当前文件摘要、change.md、共享索引/待办。只报告本批产品线表单，不宣称用户/角色/部门/枚举已迁移。

## 实际结果

观察到两次close出现两个确认的RED，接入后浏览器GREEN；确认期间不写、关闭取消/放弃、必输校验、保存互斥、busy输入/路由锁、409保留输入及重试、不可变组织绑定、原POST/PUT体及权限不足拒绝全部通过。所有测试API模拟，未真实写产品线或访问金蝶。读取状态两页回归、18项相关契约及构建exit0；独立审查无Critical/Important/Minor。5174实际源模块已含本批控制器，使用现有登录打开一条既有绑定产品线后未修改即取消，组织字段只读且返回7行列表；没有启动组织查询或保存。完整证据在outputs/product-line-form-session-20261018。本批未改库/授权/配置，未重启后端或部署/提交/Git操作。
