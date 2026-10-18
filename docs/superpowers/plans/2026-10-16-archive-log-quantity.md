# Archive log and positive quantity implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 按已确认新增页面顺序显示日志、精简名称并严格限制新输入数量，同时纠正授权的单条正式数据。

**Architecture:** 后端共享日志解析负责排序与名称来源；数量统一校验放在独立服务，被字段写规则及导入复用，响应Schema不收紧历史值。前端复用PmsNumberControl及现有折叠信息。

**Tech Stack:** FastAPI/SQLAlchemy/Pydantic、Vue3/Element Plus。

## Global Constraints

- 沿用2026-10-16已确认规格；不部署/迁移/合并/推送/发信/扩大权限。
- 不改旧日志和其他历史数量，不静默取整；数量保留DECIMAL(20,8)存储结构。
- 新增表单布局不改变，排序契约核对实际基础和分组顺序。

### Task 1: 共享日志呈现

- [x] 在backend/tests/archive_log_quantity_contract.py补失败用例：乱序旧日志按表单排、snapshot不改、current字段不拼后缀但来源元数据在、单据与审计同序且隐藏字段不泄露。
- [x] 新建backend/app/services/archive_log_presentation.py顺序定义和排序入口；operation_log_metadata.py在共享解析末尾调用；operation_log_references.py返回名称来源标记，document_history.py保留安全来源元数据。
- [x] PmsDocumentHistory.vue增加按需名称说明；OperationLogList.vue在现有技术信息解释来源；page-guide/registry.ts同步两处说明。
- [x] 测试历史原值未修改，更新原有引用契约的显示期望与来源断言。

### Task 2: 数量校验

- [x] 先通过真实隔离API/服务检验0、负数、小数、非有限数拒绝；1/整数Decimal通过；超存储上限拒绝；历史-1原样回传/未提交仍可改其他字段，修改为1记录日志且无ERP队列。
- [x] backend/app/services/archive_quantity.py提供validate_archive_quantity，field_policy.py统一写规则在数量变化时调用；offline_archive_import.py复用有值校验并保留行号错误。
- [x] 前端offlineArchiveFields.ts提供共用数量校验，ProjectArchive.vue仅校验实际变化值；ArchiveRecordForm.vue使用step=1及正整数校验，保留未改变历史值；不使用会把-1自动钳制为1或小数取整的min/precision组合。
- [x] 前端行为测试覆盖负/零/小数及历史未变情况，字段目录契约保持兼容。

### Task 3: 验收与正式单条修正

- [x] 跑相关后端契约（引用、日志、档案变更/维护、导入、字段目录/枚举）；前端style/list/system、字典/枚举、archive-filter、page-guide及build。
- [x] 本机5174实际页面验收（ERP/邮件保持现有受控边界）；需要时隔离模拟API覆盖错误与旧值。
- [x] 正式数量由用户自行纠正，代理仅实页只读确认A-202666当前数量1；未写业务日志或推断ERP处理。原代理纠正步骤不再执行。
- [x] 独立审查，处理范围内问题，更新change.md和实际验收记录，明确正式部署仍待单独确认。

完成记录：docs/releases/2026-10-16-archive-log-quantity-local.md。真实新增保存未执行；其现有产品线依赖未就绪，新增交互以隔离浏览器及后端API验证，不扩展权限或ERP配置。
