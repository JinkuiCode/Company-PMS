# PMS治理实施前核对清单

核对日期：2026-10-15。代码基线：`codex/pms-unified-query`、`973c9af`。

本次仅静态读取本地代码，未运行业务、修改权限或访问生产。以下“已有”表示找到实际调用，不代表所有旧页面已迁移或已完成当前版本行为验收。设计依据为[统一开发与发布规范](2026-10-14-pms-development-governance-design.md)。

## 一、核对结论

- 19项已登记共享能力均存在，抽样真实页面调用成立；继续复用，无需重建整套前端框架。
- 首页统计没有复用产品线范围；后台金蝶同步没有在执行时重新构建操作者当前授权。这是明确代码缺口，不等于已确认发生生产越权事故。
- 全局日志只有管理员接口，不能直接接到普通用户单据页签。单据日志需要实体授权、主单关联、字段裁剪和安全输出。
- 档案审批已在当前代码落地；本批日志试点必须保留负责人、部门负责人、申请状态和版本冲突规则。
- 正式应用尚无统一用户版本中心；现有固定提交、构建及文件清单可作为其基础。样稿版本不能当作正式运行版本。

## 二、权限覆盖矩阵

状态采用“静态覆盖已见／明确缺口／待行为验证／不适用（有理由）”。本轮没有将任何资源标为最终验收通过。

| 资源或流程 | 静态证据 | 状态及后续验收 |
| --- | --- | --- |
| 首页统计 | `backend/main.py:161`使用dashboard:view；`backend/app/services/dashboard.py:17`自行查询项目。 | 明确缺口：遗漏产品线，部门范围缺部门时放宽，未统一全部业务数据授权。七类结果须一起修复。 |
| 项目进度、进度填报、任务 | `backend/app/api/projects.py:34`、`:114`、`:279`传范围；`backend/app/services/project.py:55`按产品线与负责人／部门过滤。 | 静态覆盖已见；待验证跨项目任务ID、自动保存、撤权和隐藏字段。 |
| 档案列表、引用、候选 | `backend/app/api/projects.py:142`、`:182`；`backend/app/services/project.py:86`；`backend/app/services/archive_column_query.py:64`复用档案范围。 | 静态覆盖已见；待验证列表、详情、候选、导出的一致投影。 |
| 档案写入、批量操作 | `backend/app/services/project.py:193`校验目标归属，`:1545`限制批量读取。 | 静态覆盖已见；待验证跨范围批量、目标产品线／负责人变化及并发。 |
| 档案变更审批 | `backend/app/services/archive_change.py:185`再查档案权限，`:78`校验负责人资格，`:248`列表限定申请人／审批人。 | 静态覆盖已见；业务资格独立于数据范围，日志模块不改其审批规则。 |
| 期初导入、分配产品线、来源 | `backend/app/api/offline_archives.py:24`分离导入与分配权限；`backend/app/services/offline_archive_import.py:22`要求全部业务数据授权。 | 登记受控期初整理例外；不把缺产品线当全量访问。来源输出及回退待专项验证。 |
| 业务直接导出 | `backend/app/services/business_export.py:224`同时要求查看和导出，`:121`复用资源查询；`backend/app/services/archive_change_export.py:15`复用变更范围。 | 静态覆盖已见；区分请求内导出与后台导出，明确长请求期间撤权检查点。 |
| 采购、库存、物料收发 | `backend/app/api/inventory_reports.py:18`、`purchase_reports.py:122`、`stock_detail_reports.py:63`按获授权产品线映射组织。 | 已确认组织级例外；待验证组织变更、未建档ERP数据、汇总、下钻和引用。采购档案引用另受档案范围约束。 |
| 后台报表导出、下载 | `backend/app/services/report_export_jobs.py:89`校验本人／当前权限／下载范围，`:113`在执行时重建授权。 | 静态覆盖较完整；待验证排队后、执行中和下载时撤权，以及组织映射变化。 |
| 同步管理、同步记录 | `backend/app/api/sync_tasks.py:15`校验档案；`backend/app/services/erp_queue.py:49`重试时复查；`backend/app/api/erp.py:60`同步记录先检查档案。 | 交互路径已有范围；执行路径见下一行，不能合并称为整体合格。 |
| 金蝶队列执行 | `backend/app/services/erp_queue.py:108`只带操作者ID执行，`:145`调用不传scope；`backend/app/services/kingdee.py:386`默认None；`backend/app/services/project.py:90`对None放宽。 | 明确缺口：排队后撤权／停用未形成当前授权复查。单独权限及ERP批次修复，不并入首页小批。 |
| 问题提报、统计、附件、导出 | `backend/app/services/feedback.py:39`本人或处理权限；`backend/app/services/feedback_attachments.py:95`下载回查提报。 | 静态覆盖已见；支持模块政策已于2026-10-15确认。业务链接须复查，不宣称自由文本附件自动受产品线过滤。 |
| 全局操作日志 | `backend/app/api/operation_logs.py:45`仅全局查看权限；`backend/app/schemas/operation_log.py:17`包含原始快照与技术信息。 | 管理员入口保留；普通单据授权读取尚无，禁止直接复用该输出。 |
| 系统管理和公共支持 | 各管理API使用独立动作权限；`backend/app/api/product_lines.py:29`业务候选过滤产品线；`backend/app/api/dicts.py:59`按编码候选允许已登录访问。 | 分资源登记规则；人员／部门候选的必要信息及可见范围仍需专项核对。 |

共享基础：`backend/app/services/authorization.py:73`运行时读取有效用户、角色、菜单和产品线；`business_data_scope.py:6`只检查明确授权。项目／档案内部旧函数对None保留全量语义，不能只改一个默认值而不盘点所有调用者；对外公共适配器须默认拒绝，系统任务须显式执行身份。

主路由登记至少覆盖17项：问题提报、仪表盘、用户、角色、参数、库存、物料收发、采购、同步、字段目录、枚举、全局日志、产品线、字段规则、项目进度、档案、进度填报。证据为`frontend/src/router/index.ts:55`。登录／SSO／改密、SSO链接生成器、说明、403单列公共流程；任务、审批、导入、附件、通知重试和后台导出虽无独立路由，仍须登记资源。

## 三、19项共享模块调用采样

| 能力 | 实际接入采样 | 后续原则 |
| --- | --- | --- |
| 应用壳、导航 | `frontend/src/router/index.ts:52` | 继续统一菜单和路由权限。 |
| 主题、密度 | `frontend/src/main.ts:5` | PMS字体、颜色、尺寸沿用现状。 |
| 标准列表 | `frontend/src/views/project/ProjectArchive.vue:6` | 页面只维护业务列及动作。 |
| 查询方案 | `frontend/src/views/project/ProjectArchive.vue:45` | 单字段、document/report模式沿用。 |
| 本页列过滤 | `frontend/src/views/project/ProjectArchive.vue:162` | 仅当前页，不改变后台导出。 |
| 查询引用 | `frontend/src/query-system/PmsQueryConditionRow.vue:8` | 领域数据使用权限适配。 |
| 列设置 | `frontend/src/components/PmsListColumnPicker.vue:6` | 控件已有；偏好持久化继续收敛。 |
| 基础字段 | `frontend/src/form-system/components/PmsNumberControl.vue:3` | 复用共享外壳与状态。 |
| 编辑容器 | `frontend/src/views/project/ProjectArchive.vue:103`、`ProjectList.vue:240` | 抽屉、行内、表格分别适配。 |
| 主从切换 | `frontend/src/views/project/ProjectArchive.vue:1288` | 草稿保护和晚响应保护沿用。 |
| 权限基础 | `frontend/src/router/index.ts:196`、`backend/app/api/archive_changes.py:21` | 后端最终授权，补覆盖而非重建。 |
| 字段治理 | `backend/app/api/field_catalog.py:5`、`backend/app/services/project.py:38` | 新字段同步注册，适配显示与错误。 |
| 枚举、候选 | `frontend/src/views/project/ArchiveChangeList.vue:20` | 稳定存储值、历史显示沿用。 |
| 导出、长任务 | `frontend/src/views/reports/InventoryList.vue:204` | 资源范围和独立导出权限一致。 |
| 操作日志 | `backend/app/services/archive_change.py:176` | 保留底账，增加单据读取模块。 |
| 请求、错误 | `frontend/src/utils/request.ts:44` | 共享错误处理；页面状态另模块化。 |
| 页面说明 | `frontend/src/views/project/ArchiveChangeList.vue:66` | 同版变更同步更新说明。 |
| 提报、邮件 | `backend/main.py:48`、`:93` | SMTP配置可复用；版本通知独立队列。 |
| 发布、回退 | `build-server-release.command:62`、`backend/app/services/database_revision.py:14` | 固定提交与清单绑定用户版本。 |

优先补齐模块仍为六项：资源权限登记与适配、保存会话、页面数据状态、列偏好持久化、字段元数据及错误适配、单据记录与版本通知。实施按独立模块、试点页面、分批迁移，不为日志试点顺带替换全部保存逻辑。

## 四、日志与版本接入注意事项

1. 审批事件实体为`pms_archive_change`，档案修改另以`pms_project_archive`记账（`backend/app/services/archive_change.py:176`、`:227`、`:242`）。只按档案ID过滤原日志会漏审批，需主单／申请／任务／批次关联和去重展示。
2. 当前操作日志表只有实体类型、实体ID，没有统一主单关联列（`backend/app/models/operation_log.py:18`）。是否增加关联表／索引在具体实施计划里确定；涉及结构时走独立升级。
3. 快照递归脱敏已有；摘要和异常直接保存（`backend/app/services/operation_log.py:385`）。新公共模块必须覆盖文本脱敏及普通用户安全摘要，不把原始技术异常搬到单据。
4. 中文引用名在读取时查询当前名称（`backend/app/services/operation_log.py:329`），新增事件需保存必要名称快照。旧事件只显示可证明信息；新增审批动作还需统一中文映射。
5. 发布包已有固定提交、日期和SHA256清单；前端`0.0.0`、FastAPI`0.1.0`、数据库结构号各有用途。新增用户发布记录作为统一入口，不把包默认值和数据库号混用。
6. `backend/app/models/feedback.py:61`通知表绑定提报，`backend/app/services/feedback_mail.py:39`受众是提报人／处理人员。版本通知复用SMTP传输，单独记录发布、用户通知、已读、邮件状态与幂等键。

## 五、实施顺序及并行边界

| 批次 | 产出及验收 | 交叉控制 |
| --- | --- | --- |
| P1 首页权限 | 已有独立计划；七类结果同范围，缺部门／无产品线／撤权行为验证。 | 仅两个服务文件及测试，实施前核对project.py所有权。 |
| P1补充 档案临时维护 | 已确认独立可撤销权限、原因必填、核对差异后直接生效、完整留痕；保留范围、字段及状态保护。 | 单列具体实施计划；共享档案服务及页面协调归属，不随首页批次夹带实施或自动授权。 |
| P2 权限覆盖与后台同步 | 逐资源补缺；原操作者当前授权复查，系统身份显式登记，排队撤权在外部写入前拒绝。 | ERP接口、任务状态与重试语义独立列方案；首轮隔离测试不写金蝶。 |
| L1 单据日志试点 | 公共安全日志读取、档案／审批关联、已批准详情页签；实体和字段范围测试。 | 保留现有档案审批及表单，集成文件集中由一批修改。 |
| L2 审计及日志扩展 | 标准审计列表接入；逐项补写路径、失败审计、历史快照，再接其他单据。 | 不一次替换全系统，新增结构单独升级。 |
| V1 版本与通知 | 单一运行版本源、发布记录、关于页、站内已读及独立邮件队列、说明关联。 | 应用壳、模型及发布脚本统一集成；发布验证后才触发通知。 |

潜在交叉文件：`backend/app/services/project.py`、`archive_change.py`、`operation_log.py`、`field_catalog.py`、`enum_registry.py`、`database_revision.py`、`backend/main.py`及升级脚本；`frontend/src/views/project/ProjectArchive.vue`、`ArchiveChangeList.vue`、`frontend/src/page-guide/registry.ts`、`frontend/src/layout/AppLayout.vue`、`frontend/src/router/index.ts`；根目录`change.md`。

本对话目前仅核查及文档整理。两段对话共用目录，正式并行编码须先分文件归属或建立获准的隔离工作区；数据库、启动和发布由单一批次顺序执行。本文不批准任何业务代码、真实权限、数据库或发布变更，也不写入实施变更日志。
