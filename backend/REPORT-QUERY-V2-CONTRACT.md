# 报表统一查询后端交接

日期：2026-10-11。仅 backend 域实现；不包含前端验收、部署、提交、合并、真实数据库访问或结构升级。根目录 change.md 由主 agent 汇总本批记录，本 worker 不跨出 backend 编辑。

## 统一请求

- 顶部 `filters` 为 JSON 字符串数组，每项接受 `QueryCondition`：`field/operator/value/valueEnd/schemaVersion:2`，可带数字 `id`。不接受未知字段、操作、版本或属性。
- 保留不带版本的旧报表条件以及显式 `schemaVersion:1` 的旧方案条件。旧报表操作、大小写和空值含义不变；v2 文本去首尾空白、不区分大小写，负操作不匹配空白。
- 文本支持 contains/notContains/equals/notEquals/startsWith/endsWith/isEmpty/notEmpty；数字、日期支持全部比较与 between。日期按日历日比较，截止日期包括当天全部时间；0 为有效数字。
- 采购 document_status/close_status/progress 支持 equals/notEquals/in/notIn/reference 及显示名 contains/notContains/startsWith/endsWith。显示名字符查询不会对存储编码作模糊匹配。
- `column_filters` 为独立 JSON 字符串数组，每列至多一个元素。列间交集，同列 values 并集。每项只能是：

```json
[
  {"field":"requested","mode":"values","values":[0,1,null]},
  {"field":"bill_no","mode":"condition","condition":{"id":1,"field":"bill_no","operator":"contains","value":"001","valueEnd":null,"schemaVersion":2}}
]
```

- values 空数组明确返回无结果；null 匹配 NULL/文本空白，不能用空数组表示解除限制。解除限制应移除该列元素。
- 数字和日期的多值 membership 仅用于列 values，不开放给顶部业务条件或 condition 内的数字/date in。
- 每组最多20条件，每列最多1000选值；单次 SQL 绑定参数最多2000，超过明确拒绝，不截断。数字受现有报表 SQL Decimal 精度38/小数28限制。
- 列条件使用共享 `app/services/query_conditions.py` 的 `build_query_clause/scalar`；没有修改或复制共享模块。报表层只维护来源字段、枚举显示名/稳定身份映射与旧协议适配。

## 列候选

入口（均为 GET）：

- `/api/reports/purchase/column-options`
- `/api/reports/purchase/overview/column-options`
- `/api/reports/inventory/column-options`
- `/api/reports/stock-detail/column-options`

参数：`field`、`keyword`、`page`、`page_size`（1..200，默认50）、`parameters`（JSON字符串，内容为顶部已提交报表参数，包括已提交 keyword、filters、组织、物料、日期等）、可选 `column_filters`（JSON字符串）。单独传入的 column_filters 替代 parameters 内同名字段。候选 keyword/page 不覆盖 parameters 内顶部 keyword/结果分页。

服务端验证全部传入条件，排除当前列后再查询，保留其他列与顶部范围。采购/库存在完整服务端结果中 distinct 后分页；采购总表先聚合再取候选；物料收发先完整计算余额，再在服务端去重分页，不使用当前显示页。

返回：`{items:[{value:string|number|null,label:string}],total,page,page_size,has_more}`。精确 Decimal 返回字符串，列 values 可原样回传。日期返回 YYYY-MM-DD。不能以本页候选代表全量全选。

元数据新属性：`query_schema_version:2`、`query_fields`、`column_filter_fields`，采购另有 `overview_query_fields`（基础字段+总表字段）、`overview_column_filter_fields`。旧 `fields/filter_fields` 保留。采购明细和总表全部展示字段均有真实 v2/列查询能力，`unsupported_query_fields=[]`。

## 真实展示标签

- `product_line_name` 来源为当前 PMS `SysProductLine` 的 kingdee 配置名称，按请购组织内码映射，不用项目档案产品线替代。历史停用配置仍能显示；未配置时使用金蝶组织名称并加“（未配置产品线）”，仍可字符过滤/取候选。
- `project_name` 使用现有 scoped archive 查询及产品线关联，以 `(project_code, organization_id)` 对应有权读取的 PMS 档案名称。不存在、组织不一致或无权读取时为空，不回退 ERP 名称；查询、候选和返回展示使用相同身份。字符条件和列 values 不要求 reference；reference 仍必须传数字档案 ID 并重新校验。
- `supplier_name` v2 是主表展示值：单一供应商名称或“多家供应商”。旧 `supplier` 参数仍是关联单据供应商包含查询，二者不能在旧方案迁移中悄悄互换。
- `order_statuses/stock_statuses` 按已验证可展示的关联订单/入库单状态显示名去重、固定 Unicode 顺序合并，例如“审核中、已审核”。列 checkbox 选择整个单元格展示值，字符操作匹配展示字符串；空关联匹配 null 空白候选，不从当前页拼候选。
- 关联标签只消费与当前申请的组织、来源单据/行、物料及基本单位一致的公共单据。合并来源、错误来源、跨组织订单及未核验入库来源不参与候选，不扩展数据权限。
- 所有标签均在分页前投影，条件仍调用共享 query_conditions 编译器；映射/用户值使用绑定参数，不生成报表私有条件协议或新数据库表。当前 SQL 绑定预算仍为2000，超限明确提示缩小范围，绝不截断映射。

## 项目引用

- 项目编码/项目名称顶部 reference 都传 PMS 项目档案数字 ID 数组，不传名称、ERP 辅助资料 ID 或列表行号。
- 列表、候选、导出创建及导出执行都用当前 scoped archive 查询校验；解析为 `(project_code, organization_id)` 精确组合，不按编码匹配其他组织。同条件内并集、多条件交集。不明身份、权限失效、组织冲突或映射不唯一明确422。
- 旧 `project_code` 精确编码仍可用，新增 `project_codes` 字符串数组与单值互斥；它是旧编码查询扩展，不是稳定项目引用，不应替代 reference。
- 项目候选 `/api/reports/purchase/reference-options`：field=project_code/project_name、keyword、organization_ids、page/page_size、可选 ids 数字数组或 exact_values JSON字符串数组。普通搜索、ids 校验、批量精准搜索不能混用。
- ids 必须全部在当前可访问/选定组织中存在，否则422；候选返回数字 value/id、code、label、organization_id、product_line_name 和前端兼容 lineName。
- 精准查询按所选字段等值匹配，保留编码前导零，不自动勾选。返回 batch 的 input_count/duplicate_count/matched_records/unmatched_values/ambiguous_values，名称同名不自动选某条。

## 仓库引用

`/api/reports/stock-detail/options` 原调用不带 page/ids/batch_values 时保持旧接口；新增分页调用支持 page/page_size、ids、batch_field=code/name、batch_values 单列文本数组。仍按当前库存组织范围校验，允许历史停用档案。

仓库返回稳定数字内码，物料候选仍返回编码字符串。分页调用返回真实 total/has_more；恢复 ids 全部校验，不默默忽略失效/外部组织身份。普通、身份校验、批量三种模式互斥，批量返回相同 batch 汇总。不增加组织授权。

## 汇总及导出

- 采购明细：源字段先筛选，计算数量/进度后筛选派生字段，再计数/分页。仅源字段条件不额外触发全量会计工作集。
- 采购总表：顶部基础业务条件保持原行为，column_filters 以及顶部总表专属字段条件在项目+组织聚合后应用，不先删申请行改变完成率分母。总表专属字段是 organization_name、completion_rate、total_lines、not_ordered_lines、ordering_lines、receiving_lines、complete_lines、review_lines。候选、列表、导出复用 overview_selection。
- 库存：count、分页与后台导出复用同一 where_clause。
- 物料收发：先用完整流水计算逐行余额和完整范围汇总，再过滤展示流水、期初及汇总行。列筛选只决定是否显示，绝不删除计算输入或重算汇总金额；顶部旧附加条件仍不改变期初/汇总数值。total 仍只计展示流水，期初不参与分页。
- 导出仍 POST `/api/report-exports`，report 不变。采购明细 parameters 默认 view=detail；采购总表需显式 `parameters.view="overview"`，允许 columns 中使用总表字段。两者沿用采购 view/export 权限，不新增权限节点。
- 导出使用与列表相同的已提交 filters/column_filters/组织范围；项目引用在执行时重新解析。物料收发导出的期初也应用列条件。

## 物料收发排序

`StockDetailQuery` 新增 `sort/direction`，默认 `bill_date/asc`，direction 只允许 asc/desc。metadata 提供 `sort_fields`、`default_sort` 和 `sort_semantics`。

sort 白名单为全部15展示字段：material_code、material_name、bill_date、bill_name、bill_no、bill_seq、stock_name、stock_status_name、owner_type_name、owner_name、unit_name、opening_qty、income_qty、issue_qty、balance_qty。

先按原日期/来源/创建时间/单号/行号/row_id 顺序完整计算余额，然后过滤并在整个展示流水中排序，再分页。NULL/文本空白始终排末尾，相等值保持原流水顺序。期初固定前置、不参与流水分页；完整汇总不受排序影响。导出消费相同 sort/direction，不按倒序输入重新计算余额。列候选参数可携带排序，不改变候选集合。

## 前端核对

已只读核对 `frontend/src/query-system/report-adapter.ts`、四个报表页面及 api 文件：四个列候选路径、parameters/column_filters 和项目 reference-options 的 field/exact_values 映射一致；显式 schemaVersion1 和 ids 恢复校验已补兼容。

已向 Boole（报表前端独立线程）发送并确认接口协调要点：总表导出 view=overview；新 supplier_name v2 进 filters，旧 supplier 迁移保留旧语义；总表使用 overview_query_fields；收发排序只发送 metadata.sort_fields 中的字段，并按已提交快照导出。已只读核对前端新增字段和映射，但未修改前端文件、未声称浏览器联调验收。

下钻契约：明细模型继续拒绝总表专属过滤。整表 tab 继承已提交基础查询与全部原组织/引用数组，不用当前页项目截断范围。单行下钻替换已满足的项目正向 reference 为当前行 project_code+organization_ids=[row.organization_id]，空项目用 project_code_is_empty=true；保留日期/物料/供应商/状态和项目字符条件，清除 overview 列条件。原 reference 数组若含跨组织 IDs，再缩到单组织仍会明确422，不能绕过后端身份校验。

## 验证边界

- 本次点名的产品线/项目名称字符过滤、供应商和关联状态列漏斗、全部展示字段候选、总表聚合过滤与导出、收发显示排序均已实现，不再以“不支持该字段”占位。稳定身份 reference 只对已声明 reference 的字段开放，不把供应商名称或多状态展示字符串伪装成主数据身份。
- 未对真实 MSSQL/金蝶进行性能或联调验收，未执行新的 DDL/业务写入；既有采购 session-tempdb 会计工作集实现未改为业务库写入。
- 本环境没有可调用的 reviewer subagent 工具，未执行独立代码审查；主 agent 可对本 backend 范围做最终审查。

## 本批变更与验证

变更原因：统一查询协议及列漏斗不能丢弃限制、跨页计数偏差或改变采购完成率；前端恢复旧方案和引用身份校验须完整匹配接口。

涉及文件：

- app/api/purchase_reports.py
- app/api/inventory_reports.py
- app/api/stock_detail_reports.py
- app/services/report_filters.py
- app/services/report_column_candidates.py（新增）
- app/services/purchase_reader.py
- app/services/purchase_query_labels.py（新增，只读名称映射及已验证来源标签投影）
- app/services/inventory_reader.py
- app/services/stock_detail_reader.py
- app/services/stock_detail_engine.py
- app/services/stock_detail_order.py（新增，完整余额后的共享展示排序）
- app/services/report_export_data.py
- app/services/report_export_jobs.py
- tests/report_query_v2_contract.py（新增）
- REPORT-QUERY-V2-CONTRACT.md（本交接）

测试均使用离线内存 SQLite/mock，不使用真实 DB/凭据；有明确 RED 后 GREEN。最终命令及结果由本 worker 回报，主 agent 汇入项目 change.md；不记录其他 worker 的档案改动。

最终验证证据（以下全部退出0）：

工作目录 `/Users/jin/Code/PMS`，命令共同前缀为 `DATABASE_URL=sqlite:// PYTHONPATH=backend/.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`。

| 命令后缀 | 结果 |
| --- | --- |
| `backend/tests/report_query_v2_contract.py` | 38 tests OK |
| `-m unittest discover -s backend/tests -p '*report*contract.py'` | 79 tests OK（包括上述38及4项审查回归，不重复累加） |
| `-m unittest discover -s backend/tests -p '*purchase*contract.py'` | 74 tests OK |
| `-m unittest discover -s backend/tests -p '*stock_detail*contract.py'` | 88 tests OK |

工作目录 `/Users/jin/Code/PMS/backend`，命令共同前缀为 `DATABASE_URL=sqlite:// PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`。

- `tests/field_catalog_contract.py`：field catalog contract passed，退出0。
- `tests/enum_management_contract.py`：enum management contract passed，退出0；既有迁移提示仅涉及测试内存历史分类 custom_history，未访问真实数据库。
- `git diff --check -- backend/app/api/purchase_reports.py backend/app/api/inventory_reports.py backend/app/api/stock_detail_reports.py backend/app/services/report_filters.py backend/app/services/purchase_reader.py backend/app/services/inventory_reader.py backend/app/services/stock_detail_reader.py backend/app/services/stock_detail_engine.py backend/app/services/report_export_data.py backend/app/services/report_export_jobs.py`：无输出，退出0。

可直接复跑的完整测试命令（项目根目录）：

```bash
DATABASE_URL=sqlite:// PYTHONPATH=backend/.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 backend/tests/report_query_v2_contract.py
DATABASE_URL=sqlite:// PYTHONPATH=backend/.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s backend/tests -p '*report*contract.py'
DATABASE_URL=sqlite:// PYTHONPATH=backend/.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s backend/tests -p '*purchase*contract.py'
DATABASE_URL=sqlite:// PYTHONPATH=backend/.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s backend/tests -p '*stock_detail*contract.py'
```

新增未跟踪文件另以 `git diff --no-index --check /dev/null <path>` 检查：purchase_query_labels.py、stock_detail_order.py、report_query_v2_contract.py、本交接文件均无空白错误输出；该 no-index 命令因新增文件与 /dev/null 不同返回1，不是测试失败，未把它记成退出0。

运行时交接：本 worker 已停止 runtime 编辑。主线程复跑报告79、采购74、收发88均退出0，与当前代码一致。开发PMS已加载既有受保护只读配置，金蝶写入禁用、后台同步关闭。独立审查发现并修复空值OR权限括号、计算列候选工作集、全NULL CASE类型三项问题，定向复核4 tests退出0。

主线程真实开发浏览器只读联调：库存指定物料2条按仓库过滤为1条；A-202638汇总2组织1804申请行，申请行数候选332/1472，筛选1472后只保留对应组织，下钻1472条明细并按已完成过滤113条；物料180102020045、双组织、2026-09-01至09-23收发29条，直接调拨筛6条，原结存未重算、数量两位小数、零空白。缺少组织时查询按钮禁用，仓库条件仅引用。以上是真实只读ERP查询，不等同于正式PMS/Windows/OA页面验收；无新增授权、业务写入或数据库结构修改。

Git 当前分支 `codex/pms-unified-query`；未创建分支、提交、推送、PR或合并。前端/档案 worker 的文件未编辑。
