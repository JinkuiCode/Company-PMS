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
| 列偏好存储 | list-system/columnPreferences.ts | 档案已正式、进度工作台Mac已接入。账号＋页面键、有效列清理、格式兼容、安全失败。 |
| 统一字段控件 | form-system/index.ts、components/Pms*Control.vue | 文本、长文本、数字、日期、选择、树、开关、勾选等统一状态。 |
| 表单／行内／表格容器 | PmsFormDrawer.vue、PmsFormField.vue、PmsInlineField.vue、form-system/ag-grid.ts | 三类交互共用令牌，保留各自容器。 |
| 表单会话 | form-system/useFormSession.ts | 档案新增已正式；进度新增、产品线表单Mac已接入。原值、草稿、验证／保存互斥、关闭确认、失败投影及重试。详情审批保留专用流程。 |
| 页面数据状态 | composables/usePageLoad.ts | 档案已正式；进度/任务及九个系统列表Mac已接入。待查询、加载、空结果、失败、重试及请求代次，不持有业务行。 |
| 字段元数据／错误适配 | form-system/fieldMetadata.ts | 档案已正式、进度新增Mac已接入；配置与代码上限取交集，结构化错误按当前可见字段和页面顺序展示。 |
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

2026-10-18后续Mac批次：ProjectList.vue与ProjectProgress.vue已接入usePageLoad及内联重试，隔离真实浏览器两页和必需前端检查通过。任务异步历史切换另有交错测试；仅页面状态完成，列偏好/表单会话/字段适配在进度页仍待迁移，正式仍为v1.1.0。详见[批次计划及结果](superpowers/plans/2026-10-18-progress-page-load.md)。

2026-10-18后续Mac列偏好批次：ProjectList.vue接入共享存储，保留原账号键及selected_sheet_field_keys别名；当前未选有效列旧布局仍保存，失效列清理。未来/损坏/异属缓存保护与存储异常不阻断查询已隔离实页验证，默认档案行为保持。仅Mac，见[计划及结果](superpowers/plans/2026-10-18-progress-column-preferences.md)。

2026-10-18后续Mac表单批次：进度新增窗口接入useFormSession及共享字段元数据/错误投影，关闭保护、互斥、快照、可见控件顺序/日期别名/动态嵌套/ARIA均已隔离实页验证；列表说明入口及5174只读现场通过，表格/详情保持原写路径。至此进度工作台适用的四项共享行为已接入，任务页仅接入页面状态；系统页面仍按下一批继续。正式仍v1.1.0，见[本批结果](superpowers/plans/2026-10-18-progress-form-session.md)。

2026-10-18系统只读批次：DataDictionaryList.vue及OperationLogList.vue接入usePageLoad，完整读取/分页、离页及详情异步总数保护已隔离真实浏览器验证。保留字段目录只读和审计当前布局/授权，无真实写入或正式部署，详见[本批结果](superpowers/plans/2026-10-18-system-readonly-page-state.md)。

2026-10-18系统设置读取批次：ProductLineList.vue及FieldPolicyList.vue接入共享页面状态，失败清旧行、重试和离页保护通过；字段规则模块快速切换的旧响应不再覆盖当前模块。组织绑定、保存/删除/恢复默认和授权均保持原路径，本批只覆盖读取。见[计划及结果](superpowers/plans/2026-10-18-system-settings-page-state.md)。

2026-10-18用户/角色读取批次：UserList.vue、RoleList.vue主列表接入共享状态，用户完整分页及部门参数保持，失败清行/重试、旧响应及卸载已隔离验证。部门管理、用户表单及角色权限树保持专用流程，不把读取迁移报告为表单会话全迁移。见[结果](superpowers/plans/2026-10-18-system-identity-page-state.md)。

2026-10-18专用管理读取批次：枚举定义/值、参数、同步任务接入共享状态，同时保留枚举身份、参数securityEpoch/撤权清内存、同步服务端查询/防抖/轮询。三页隔离行为和原参数安全/枚举身份测试通过；写入会话继续使用原专用流程，尚未统一迁移。正式仍v1.1.0，本机前端已刷新，见[本批结果](superpowers/plans/2026-10-18-system-specialized-page-state.md)。

2026-10-18产品线保存会话批次：既有产品线抽屉接入useFormSession，连续关闭只一次确认，确认/保存互斥、提交快照、409保留输入及重试通过；组织不可改、POST/PUT字段及权限保持。全API模拟验收与5174实际只读打开/取消通过，未真实写入或部署，见[计划及结果](superpowers/plans/2026-10-18-product-line-form-session.md)。用户/角色/部门/枚举等保存适配继续分批推进。

2026-10-18部门保存会话批次：UserList内既有部门抽屉接入useFormSession，未保存关闭/离页/改开目标的一次确认、校验和保存互斥、独立快照及失败保留通过。部门负责人跨部门候选、原权限/接口、删除和拖拽保持。模拟回归及5174只读打开取消通过，仅Mac未真实写入或部署，见[计划及结果](superpowers/plans/2026-10-18-department-form-session.md)。

2026-10-18用户/角色/枚举保存会话批次：三处普通维护抽屉接入共享会话，独立重置、角色树/首页、系统存储值及缓存保留领域适配。角色/枚举说明和升级目录同步登记。至此本批五处普通管理表单（产品线、部门、用户、角色、枚举）完成Mac会话迁移；敏感参数、字段策略批量表、附件幂等和邮件核查保留专用控制器，不强行替换。37项契约、专项隔离、构建及审查通过，尚未提交或部署，见[计划及结果](superpowers/plans/2026-10-18-system-save-sessions.md)。


2026-10-18最新本机适用性收尾：原60项治理变更已固定a3/v1.2.0候选但未部署；提报表单另经批准只将关闭保护接入useFormSession.requestClose，保留正文/附件分步保存、幂等与重试控制器。取消/放弃/保存及保存后干净基线、附件续传和版本冲突经隔离及模拟浏览器通过，新修复尚未纳入原包。任务编辑保留表格自动保存，报表复用report-adapter/createReportRequest，版本邮件和参数保留专用保护；未引用相同composable不直接认定缺陷。旧MenuList/FieldList当前无router/导入入口，不擅自重启旧模块。详情及剩余真实验收见[本批收尾](releases/2026-10-18-governance-completion-preparation.md)。
