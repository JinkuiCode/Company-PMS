# Mac产品线名称显示修复验收

2026-10-15。用户明确批准仅Mac修复：只读名称接口、独立名称加载、当前不可选值禁用显示、错误重试、保持原新增/变更校验及授权。已实施并完成实际5174页面核验。

## 原因与调整

原`/api/product-lines/options`在返回本地名称前校验金蝶组织；Mac受控验收后端未启用采购只读连接配置，目录不可用返回503，连同本可读的名称一起丢失，详情下拉因无选项显示内部ID“3”。没有修改产品线、档案或用户数据来规避问题。

新增`GET /api/product-lines/labels`仅从PMS读取名称，与原options共用同一业务按钮权限及产品线范围函数；空授权返回空，显式business:data:all只扩展数据范围，不代替业务按钮权限。保留禁用历史名称但不作为可选项，不连接金蝶。原options组织校验、422不可选及503语义保留。

前端共享`useProductLineOptions`独立读取名称与可选项，各自请求票据及失败状态；名称重试不请求金蝶候选，重新读取先清除旧标签，迟到响应不能覆盖新范围。详情仅为当前不可选值补一个disabled展示项，不将其他历史名称变成选择项。候选失败/加载中禁止修改产品线，其他获准编辑字段不受影响；新增仍只使用校验过的options。名称失败明确提示和重试，编辑模式的候选不可用也有简洁提示。使用现有表单/按钮/语义样式，未修改共享选择控件或布局。说明入口同步更新产品线规则。

## 验证

- 新后端4项先RED（缺少端点）后GREEN：外部不可用仍读授权名称、禁用历史、空授权/显式全部范围、同令牌撤销范围及按钮立即生效。原options外部503仍拒绝。
- 新前端5项先RED（名称为“3”等）后GREEN：名称/候选独立、仅当前禁用项、不改变新增候选、清理失败旧标签、仅名称重试、迟到响应、名称不等待外部候选。
- 后端6组退出0：product_line_labels、product_line_api、product_line_authorization、product_line_project_scope、product_line_source、product_line_sync。原身份安全代码有已有utcnow弃用警告，未扩大修改。
- 前端style-contract、list-standard-contract、system-ui-consistency-contract、archive-filter-contract、product-line-contract、archive-edit-drawer-contract、product-line-display、page-guide、page-guide-tab全部退出0；`npm run build`退出0，仅既有大包警告。
- 完全mock浏览器仅访问临时本机5198，全部API为夹具、外部请求拒绝；先在旧版看到“产品线3”失败，修复后验证显示12吋Bench、候选503时仅产品线禁用/备注仍可编辑、新增被拒绝、当前历史值disabled且其他历史名称不混入候选、名称失败提示和重试、仅名称重试零候选请求、518px窄窗，零写入。
- 独立只读复核实跑后端4项、前端5项及mock浏览器；额外启用产品线列表列，验证名称重试后列表和详情同步恢复。静态表格刷新疑点经双方实际复现排除，没有增加无必要watch/刷新。无重要缺陷。

完整日志与源文件SHA256在`outputs/product-line-display-20261015/`，`backend-results.json`、`frontend-results.json`、`browser-green.log`、`browser-grid-green.log`为当前证据。

## 实际Mac结果与保护

- 用户原IAB会话、`http://127.0.0.1:5174/project/archive`，未取密码/令牌。样本LOCAL-GOV-20261015-001详情显示“12吋Bench”，既有只读提示及无维护入口保持；点击新增提示金蝶目录/产品线读取失败，新增表单未打开，未保存或同步。
- 实际截图`outputs/product-line-display-20261015/actual-product-line-name.jpg`；隔离截图为isolated-name-offline.jpg及isolated-name-narrow.jpg。
- `final-verification.json`：SQLite完整性ok、全部35张表（含sqlite_sequence）及结构逐项完全一致，103条档案/197条日志/原授权等未改，受保护配置字节一致，ERP任务0、发布/邮件记录0。本批没有实际写入。
- 只刷新Mac受控后端（PID19768、8000）和缓存旧模块的标准前端（PID19782、5174）；临时5198已停止。受控启动器仍只检查数据库，ERP、后台导出、反馈邮件和版本邮件worker继续暂停。未启用金蝶或采购只读连接配置。

## 备份与边界

本批前5个源码文件、数据库before.db、受保护配置存私有`.runtime/product-line-display-20261015-135558/`。数据库备份SHA256为ba784790d3a566e5494f02c665dfae6626b0d1ae7678c34a156df971683f2567，回退仅恢复本批配套源码并重新受控启动；无需升级或覆盖真实库，原库本批未写。

当前分支codex/pms-unified-query，HEAD973c9af。本批未提交、合并master、推送或创建PR，没有连接或部署服务器/正式环境。金蝶目录不可用仍会阻止新增或变更产品线，这是原校验边界；本批只恢复查看名称，并未恢复对接连接。
