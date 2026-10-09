# 采购总进度实施计划

基线：已确认的 purchase-overview 方案 A，及“总进度 / 明细进度”、产品线 / 项目编码 / 项目名称列顺序修订。
范围：开发机，同目录 codex/pms-purchase-overview；不部署、不合并、不推送、不修改数据库结构或 ERP 数据。

## 任务
- [x] 先补行为测试：按项目编码及请购组织分组、五种状态计数、分页、筛选、空权限、空项目下钻。
- [x] 新增只读汇总接口，沿用 report:purchase:view 与现有组织数据范围；复用现有数量/来源校验，不另写采购进度口径。
- [x] 实现方案 A：默认总进度、项目状态快捷筛选、行/状态数下钻、全范围明细与返回位置。
- [x] 两表统一首列及标签；一次性迁移旧明细默认列，随后尊重用户保存的列偏好。
- [x] 总表与明细独立保留列设置、查询方案及分页；下钻携带上次成功查询条件，不使用未提交草稿。总表保留缓存及滚动位置，返回不重查。明细保留三 sheet 导出；总表不将项目计数冒充申请行导出。
- [x] 补充字段取值说明、change.md，完成后端契约、前端标准检查、构建及桌面/窄屏浏览器验证。

## 口径与边界
一行是项目编码 + 请购组织组合；同编码跨组织不合并。完成率 = 已完成申请行 / 当前公共条件下全部申请行，待核对计分母、不计分子。状态快捷筛选过滤项目，不重算项目分母。名称取有权访问的 PMS 档案，不用金蝶名称补空。无项目编码单独分组，下钻只查询无项目的对应组织。权限取当前数据库授权，汇总、明细、导出不新增角色旁路。失败保留上次成功结果，旧请求不得覆盖新选择。

## 验证
后端：purchase_overview_contract、purchase_reader_contract、purchase_typed_progress_contract、purchase_api_contract、purchase_product_line_contract、purchase_organization_scope_contract、field_catalog_contract、enum_management_contract。
前端：purchase-overview-browser、purchase-report-browser、purchase-page-contract、purchase-quick-filter、purchase-detail-state；style-contract、list-standard-contract、system-ui-consistency-contract、data-dictionary-contract、enum-management-contract；npm run build；git diff --check。

## 2026-10-09 执行结果

以上检查全部通过。额外回归 report_export_contract 10项、report_typed_filters_contract 8项、compact-workspace-browser；采购后端契约共72项通过。浏览器覆盖了返回原滚动位置，以及方案未查询时翻页不采用草稿排序。独立复核发现的方案范围、失败范围提示和初始排序恢复问题均已修复并补回归。

现有真实只读连接抽查 A-202638 两组织的总数和完成数与原明细一致。无条件汇总当前约16.9万申请行耗时15.1秒，单项目约1.7秒；全量性能仍需用户体验验收，不作为生产SLA。仅开发机交付，未提交、部署、合并或推送。

## 后续批准：联动修复与服务器部署

用户批准本地验证后直接部署；不包含主分支合并或GitHub推送。

- [x] 查明本地产品线配置为空，不导入或伪造服务器配置。
- [x] 候选接口接收产品线多选；两个视图共用联动、清空、方案精确核验及过期响应保护。
- [x] 隔离测试覆盖同项目跨组织、空授权、停用配置、方案恢复、并发和无自动业务查询；74项后端契约及前端回归/构建通过。
- [x] 固定发布版本，备份应用文件，部署前后端；不改数据库、权限、ERP写接口，不重启SQL/OA/服务器。
- [x] 核对服务器文件、健康状态、已配置选项及真实只读样本，记录发布结果；人工业务验收由用户完成。

2026-10-09服务器已发布运行版本`27ed70f`，旧前端备份在`C:\PMS\.runtime\release-history\purchase-overview-20261009-121208`。仅PMS后端PID从5288变为6500；数据库版本仍为2026-09-23-02，6个受保护文件未变。7项产品线配置及组织项目候选读取成功，A-202638在8吋Bench下汇总与明细均1472行；178个前端文件本机与外部HTTP散列一致，健康检查通过。详见本批发布记录。未合并master、未推送GitHub，人工验收待用户执行。
