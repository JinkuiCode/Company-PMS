# PMS 共享模块接入索引

本索引按当前代码实际入口整理。模块存在、首个页面接入与全系统迁移是三个不同状态；旧页面仍按批准批次接入。完整产品规则见治理定稿规格及 PMS-UI-STANDARD.md。

## 现有模块与入口

| 能力 | 标准入口 | 使用说明／实际接入例 |
| --- | --- | --- |
| 应用框架与菜单 | frontend/src/layout/AppLayout.vue | 登录后统一侧栏、页面标题、用户菜单和版本入口。 |
| 字体、颜色与密度 | frontend/src/styles/pms-theme.css、form-system/form-tokens.css | 业务控件与查询密度各有适用范围，页面不另建主题。 |
| 列表容器、分页 | components/PmsDataList.vue、CustomPagination.vue、config/listUi.ts | 档案等列表复用布局及分页选项、操作列规则。 |
| 查询工作区 | query-system/PmsQueryWorkspace.vue、core.ts、system-adapter.ts | document/report进入模式、方案、条件校验与数据适配。 |
| 本页列筛选 | query-system/page-column-filter.ts、column-filters.ts | 仅当前页快照，翻页／重查清除，不能影响总数／后台导出。 |
| 业务引用 | query-system/PmsQueryReference.vue、reference.ts | 共享引用候选、分页、多选及已选摘要。 |
| 列设置 | components/PmsListColumnPicker.vue | 显示、顺序、冻结、列宽的统一交互。 |
| 列偏好存储 | list-system/columnPreferences.ts（本批新增） | 档案试点，其他页面尚未迁移。账号＋页面键、有效列清理、格式兼容、安全失败。 |
| 统一字段控件 | form-system/index.ts、components/Pms*Control.vue | 文本、长文本、数字、日期、选择、树、开关、勾选等统一状态。 |
| 表单／行内／表格容器 | PmsFormDrawer.vue、PmsFormField.vue、PmsInlineField.vue、form-system/ag-grid.ts | 三类交互共用令牌，保留各自容器。 |
| 表单会话 | form-system/useFormSession.ts（本批新增） | 档案新增试点；原值、草稿、验证／保存互斥、关闭确认、失败投影及重试。详情审批保留专用流程。 |
| 页面数据状态 | composables/usePageLoad.ts（本批新增） | 档案列表试点；待查询、加载、空结果、失败、重试及请求代次，不持有业务行。 |
| 字段元数据／错误适配 | form-system/fieldMetadata.ts（本批新增） | 档案试点；配置与代码上限取交集，结构化错误按当前可见字段和页面顺序展示。 |
| 主从切换 | utils/detailSwitch.ts、composables/confirmDetailSwitch.ts | 最新选择生效、草稿保存／放弃／取消；不由本批会话模块取代。 |
| 授权与资源登记 | backend/app/services/rbac.py、business_resources.py及各业务范围服务 | 运行时权限和数据范围在后端检查，前端隐藏不能代替授权。 |
| 字段目录与规则 | backend/app/services/field_catalog.py、field_policy.py | 同一生效元数据驱动可见／可编辑／必输；代码决定配置上限，保留存量必填兼容。 |
| 枚举与产品线候选 | enum_registry.py、composables/useEnumOptions.ts、useProductLineOptions.ts | 稳定存储值、历史显示名与有效候选分开，不在页面重复写选项。 |
| 业务导出与后台导出 | business-export/BusinessExportControl.vue、components/ReportExportControl.vue及后端导出服务 | 查看、导出权限及范围分别校验；报表长任务由队列管理。 |
| 操作日志与单据记录 | backend/app/services/operation_log.py、document_history.py、document-history/PmsDocumentHistory.vue | 同一底账，管理员与单据业务投影分开，后端提供中文差异。 |
| 请求反馈 | frontend/src/utils/request.ts | 统一认证／拒权／错误反馈；具体字段错误由表单适配处理，不重复建消息系统。 |
| 页面说明 | page-guide/PmsPageGuide.vue、registry.ts | 同版维护操作、字段及权限说明，共享搜索和独立页签。 |
| 问题提报与邮件 | 后端feedback.py／feedback_mail.py及对应页面 | 支持模块按本人／处理权限，关联业务单据另核数据范围。 |
| 版本与通知 | release-center/、后端runtime_release.py／releases.py／release_mail.py | 关于页、运行版本、个人通知和独立投递；代码开发不自动发布通知。 |
| 发布／升级／回退 | build-server-release.command、ops/windows、backend/scripts/upgrade_database.py | 固定版本和校验材料；数据库升级、授权、正式部署按独立边界。 |

表中前端路径未写根目录时均位于 `frontend/src/`；后端服务前缀为 `backend/app/services/`。

## 本批新增模块的接入契约

- `useFormSession({draft, clone?, equals?, isConflict?})`：draft为可结构化克隆的业务表单对象，默认JSON语义比较，可由页面提供归一化比较。`capture/restore`在保存或关闭确认期间拒绝；`submit({validate,save,onError?})`在验证前锁定，save消费独立快照，onError异步定位完成后才解锁，定位自身失败通过presentationError返回。服务端版本和幂等仍由业务接口负责，不把网络失败当成功。
- `usePageLoad()`：在请求前begin，赋行和总数前isCurrent，结果用succeed/fail。排序防抖立即invalidate(true)，离页invalidate()；错误后重试重新begin。它不自动发请求、不改变默认查询、不替页面决定清除或保留旧行。
- `createColumnPreferences({pageKey,ownerId,storage,legacyPrefix?})`：read只读；v0可兼容到v1内存对象，write保留旧布局字段并附版本／归属。allowed是当前可选列，fixed还应包含不能在列选择中取消的业务列。未知版本、归属不符、损坏缓存拒绝覆盖；恢复默认是显式clear。缓存失败不阻断本次查询方案在内存中使用。
- `resolveFieldMetadata`：显示、编辑、必输及列表状态共用解析器；字段来源、业务锁和权限等更严限制继续由页面／服务传入。`mapFormFieldErrors`只接已登记的当前可见字段，按页面顺序返回错误和首字段，不维护重复翻译表。

## 迁移边界及遗留项

2026-10-16新增服务器草稿代码模块：后端`form_drafts.py`及`PmsFormDraft`独立存储生命周期，前端`form-system/usePersistentDraft.ts`负责身份/版本/冲突/未知结果核对，`ArchiveDraftList.vue`负责本人列表。仅登记`archive-create`，复用现有表单会话和统一字段；其他表单接入仍须批准。`create_archive(..., commit=False)`支持同事务转档，普通创建默认行为兼容。真实Mac/生产尚未升级，不能把代码完成视为已启用；详见[本地记录](releases/2026-10-16-archive-drafts-local.md)。

2026-10-16仅档案试点接入上述四项；项目进度、用户、角色、部门、枚举及通知页面保持原流程，后续逐批验收。项目进度必须保留表格自动保存，不能直接套新增抽屉会话。

档案试点的扩展检查曾发现两项既有基线问题：查询密度作用域检查滞后、ReleaseCenter重试确认仍用原始勾选框。用户独立批准后，2026-10-16已仅在本机修正检查并将该单控件接入PmsCheckboxControl；未知结果先人工核查、原因必输及权限规则保持。全局表单契约和控件接入检查现已通过，见 [收尾记录](releases/2026-10-16-form-compliance-local.md)。这不代表上述四项共享行为模块已迁移全系统，也不代表正式环境已更新。


2026-10-18最新落地状态：上述草稿及四项档案试点共享能力已随d71971d/v1.1.0正式部署，数据库form-draft-02及真实本人草稿保存/恢复/修改/删除、只读记录/说明验收通过；草稿管理保持独立权限。升级通知已发布18条，邮件17accepted/1缺邮箱failed。前述“尚未正式更新/未升级”是2026-10-16阶段状态，不作为当前状态；项目进度及其他管理页的四项行为迁移仍未完成。
