# 采购进度查询实施计划

> **For agentic workers:** Use executing-plans to implement this plan task-by-task. Preserve separate database deployment approvals. This plan is approved for local implementation; GitHub merge is not approved.

**Goal:** 按已确认 V2 样稿交付金蝶采购申请明细粒度的采购进度查询，以及逐字段报表说明。

**Architecture:** 金蝶独立只读连接负责固定、参数化查询；后端统一权限及来源校验后分别汇总订单、入库与退料。PMS 标准列表负责分页、筛选和个人偏好，右侧明细随主表选中行变化。

**Tech Stack:** Vue 3、TypeScript、Element Plus、FastAPI、SQLAlchemy、SQL Server。

## 全局边界

- 2026-09-21 追加确认：统一按申请日期 >= 2026-01-01 限制报表查询，包含当天；所有读取及导出入口同范围，不截断符合条件申请的下游单据链。
- 用户已确认复用 `/Users/jin/Code/PMS`、`codex/pms-db-permission-split`；保留既有未提交改动及样稿，不建立额外分支、不合并 master。
- 复用 V2 平铺订单/入库抽屉，不重新设计；使用项目字体、颜色、表单和标准列表组件。
- 新报表只读金蝶；不修改 OA/ERP 登录和同步流程，不重启 SQL Server、OA 或服务器。
- 正式连接不能使用此次探查输入的管理员凭据；独立账号和新增数据库权限需单独确认。没有可用数据源时显示明确错误，不用模拟记录冒充实时数据。
- 新菜单、权限初始化必须配套数据库版本及独立升级测试；不在生产启动时自动升级。不把前端发布与数据库升级混在一起。
- 完成口径、限制及证据见 `docs/采购进度查询报表说明.md`；说明目前是草稿，交付前须与实现核对。

## 任务 1：数量计算内核

文件：`backend/app/services/purchase_progress.py`；测试：`backend/tests/purchase_progress_contract.py`。

接口：`summarize_requisition(request, orders, links, receipts, returns=(), *, complete=False)`。输入由后续数据库适配层规范化，返回 Decimal 或不可证明时的 None，以及异常代码。只有完整关联集能标记 `complete=True`。

- [x] 先建立失败测试，再实现当前关联数量汇总，不使用 old 数量。
- [x] 覆盖分批下单/多次入库、入库前后退料区别、单位换算、来源错误、合并申请歧义、未知状态、超量、重复和部分结果。
- [x] 运行 `backend/.venv-security312/bin/python backend/tests/purchase_progress_contract.py`，16 项通过。
- [x] 数据库适配层加入后对真实拆单、三次入库及退料返回值再次验证；换算与异常仍保留构造测试和人工验收边界。

## 任务 2：明细异步联动控制

文件：`frontend/src/views/reports/purchaseDetailState.ts`；测试：`frontend/tests/purchase-detail-state.test.mjs`。

接口：`createPurchaseDetailState<T>(load, changed)`，页面通过回调更新响应式状态；打开、选行、订单筛选、重试、关闭、列表换页分别调用对应方法。

- [x] 先编写失败测试，后实现选行清空订单筛选和过期响应抑制。
- [x] 关闭取消请求，旧请求失败不能替换新行，异常提示不泄露原始服务错误。
- [x] 运行 `node --test tests/purchase-detail-state.test.mjs`，6 项通过。
- [x] 正式页面接入控制器；Edge 隔离接口验证鼠标/键盘切换、慢网乱序、关闭、失败与重试。

## 任务 3：只读数据接入与服务接口

实际新增：`backend/app/services/purchase_reader.py`（含查询 Schema）、`backend/app/services/purchase_connection.py`（独立配置）、`backend/app/api/purchase_reports.py`；后端入口注册。

- [x] 先用录制结构及脱敏构造数据测试读取器，再实现固定 SQL 和绑定参数，禁止前端提交 SQL。
- [x] 独立连接配置隐藏凭据，设定连接/语句超时；账号无写权限另行实测，不把连接 read_only 意图当权限保证。2026-09-21 账号创建与独立登录验证成功；连接模块实查成功，5 项测试通过。服务器配置尚未安装。
- [ ] 补查真实分批入库、退料、换算与状态定义。对无法归属的合并来源返回异常，不按比例猜分。
- [x] 服务接口覆盖元数据、服务器分页列表、单条申请明细和导出；过滤先于排序及分页，候选选项同样遵守权限。
- [x] 申请/订单/入库分别聚合，使用真实唯一键；不靠物料编码连接，不用重复连接后的行直接求和。
- [x] 1005 行关系数据测试总数、50 条分页、尾页、日期边界和文本过滤；查询方案恢复及服务失败由 API/浏览器测试覆盖。

## 任务 4：权限、字段目录及导出

预计修改：`backend/app/services/field_catalog.py`、`backend/app/models/init_db.py`、`backend/app/services/database_revision.py`；新增报表权限初始化及契约测试。

- [x] 查看 `report:purchase:view`、导出 `report:purchase:export` 分离。首建仅授权系统管理员，不设置 admin 运行时旁路，撤权后不得启动补回。
- [x] 受限账号通过 PMS 档案项目编号映射现有档案数据范围与产品类别；未映射资料不向受限账号展示。
- [x] 列表、数量、详情、候选、导出测试权限拒绝及范围隔离，详情在读取子单据前拒绝越界请求。
- [x] 只读字段注册表同时驱动元数据及字段目录；金蝶协议状态为系统固定，不建立可自由修改的业务枚举。
- [x] 导出使用同一数据范围及筛选，最多 500 行、防公式注入并记统一操作日志。
- [x] 初始化变更提升数据库版本，验证一次性授权及撤权保留；菜单使用自动编号，不占用既有菜单。部署升级仍需备份与独立流程。

## 任务 5：正式页面及联动验收

预计新增：`frontend/src/views/reports/PurchaseProgressList.vue`、报表 API 类型；修改 `frontend/src/router/index.ts` 和 `frontend/src/layout/AppLayout.vue` 图标注册。

- [x] 使用 PmsDataList、PmsListFilters、统一控件；表头沿用金蝶名称，汇总字段明确加“累计”。
- [x] 按批准样稿提供筛选、进度、50 条分页、列设置、个人查询方案；明细订单与入库表平铺，不使用嵌套卡片。
- [x] 绑定任务 2 的控制器；切换申请清空旧内容与订单筛选，翻页/筛选移除当前行时关闭抽屉。
- [x] 对快速切换、旧请求失败、无订单、无入库、导出权限、接口失败和重试做 Edge 隔离接口测试。
- [x] 运行样式、标准列表、系统 UI 一致性契约及 `npm run build`，比对 1366/1600 桌面和窄窗口样稿。

本项进展：必需契约及构建通过；1366/1600 桌面已检查，390px 抽屉可用，主列表窄屏以横向滚动保持 700px 表格宽度，页面允许纵向滚动避免分页截断；未改变系统导航。

## 任务 6：发布与逐字段说明交付

- [x] 对照当前响应字段核对报表说明中的来源、连接、单位、审批/作废规则、公式、空值和异常；明确本地验证而非正式上线。
- [x] 报表数据与权限契约通过，以只读身份复核真实拆单、三次入库、退料和进度过滤，记录样本与响应时间；未覆盖业务样本保留待验收清单。
- [ ] 用户确认所需数据库升级与权限动作后部署 PMS；不动共享数据库服务和 OA。
- [ ] 在正式页面验证菜单、筛选、分页、主表/明细联动、导出和数量，交付最终说明。
- [x] 记录实际完成调整到 `change.md`；保留未验收项，不将局部测试通过当全任务完成。
