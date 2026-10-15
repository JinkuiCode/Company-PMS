# PMS统一治理开发验证记录

日期：2026-10-15。范围：用户确认的治理定稿及交互样稿；另一对话暂停后实施。代码位于`codex/pms-unified-query`工作区，基线`973c9af`，未提交、合并、推送或部署。

## 开发候选已落实

- 权限：复用当前数据库授权、产品线及人员范围；首页七类结果统一范围；金蝶队列在领取和发送前复查原操作人的当前动作及数据范围。缺身份、旧任务缺来源、停用及撤权失败关闭，不发送金蝶请求，不按管理员角色名绕过。
- 档案临时维护：独立`project:archive:maintain`，仍须查看、编辑和数据范围；显式入口、必填原因、服务端中文差异确认、同事务日志。禁用、待审批、同步锁、版本冲突、字段和ERP身份保护继续有效。普通编辑及审批流程保留。
- 日志：统一服务保存中文差异和主单关联，凭据脱敏；档案、项目、任务、问题提报接入独立操作记录组件。业务用户只读当前获授权单据及可见字段；全局管理员审计独立、并排详情、技术信息按需展开。项目/任务删除、SSO开户/改名、后台导出实际结果和拒绝写入补齐留痕。
- 版本：部署清单绑定当前进程版本；关于PMS、历史更新、站内通知、邮件预览和页面说明共用发布内容。首版v1.0.0，发布必须匹配当前构建和实际验收凭据；逐启用用户建通知，显式已读。问题提报保存当时运行版本。
- 邮件：独立投递队列，复用既有安全SMTP传输；接受、失败、结果未知与已读分开。未知结果不自动重发，人工核查后受控重试；工作线程默认关闭。本次只模拟发送。
- 升级：新增日志3列、3张发布/通知表、提报版本字段和4项手动授权节点，版本提升为`2026-10-15-governance-01`；生产启动只检查，不隐式升级。重复升级不补回撤销或删除的授权节点。

## 权限与日志覆盖

下表是当前代码及隔离行为证据，不代表逐位正式用户、每个浏览器或MSSQL现场均已验收。完整接口登记见`backend/app/services/business_resources.py`；登记检查只检查准入，不能代替实际授权实现。

| 资源 | 范围与日志规则 | 本批证据 |
| --- | --- | --- |
| 首页 | 项目产品线与人员/部门共同过滤 | dashboard_scope 5项，含实际API/JWT与撤权 |
| 档案、引用、候选、编辑 | 统一档案范围、动作、目标归属与字段规则 | product_line_project_scope、archive_reference_authorization、生命周期及并发契约 |
| 档案维护、审批 | 维护3权限；审批另检查参与人；日志关联到档案 | archive_maintenance 14项、archive_change；维护及普通审批浏览器 |
| 项目、进度、任务 | 父项目范围；保存及删除沿用统一底账，子记录关联主单 | 项目范围契约、document_history；任务主从切换/删除浏览器 |
| 采购、库存、收发 | 产品线映射ERP组织；已确认不附加项目人员范围 | product_line_authorization、purchase_organization_scope及导出契约 |
| 直接/后台导出、下载 | 独立查看/导出权限、原操作人、当前业务范围；实际结果日志 | business_export、report_export及升级契约 |
| 金蝶队列/重试/记录 | 档案范围及当前原操作人动作；维护/新增/编辑/手动/重试分别记录来源 | erp_execution_authorization 14项、erp_queue 24项、product_line_sync |
| 期初档案 | 受控初始化及明确全业务数据授权，不以空产品线放开 | offline_archive 13项；性能36项及历史治理字段契约 |
| 提报、附件、通知 | 本人/获授权处理人员，附件回查父单；业务链接重新授权 | feedback API/服务/附件/邮件契约 |
| 单据记录 | 当前实体查看权限、范围、字段裁剪；删根单后仅全局审计可查 | document_history 14项；分页、迟到响应、失败/撤权清空浏览器 |
| 全局审计 | 独立全局查看权；技术明细折叠，无新增导出 | operation_log、security_audit 8项，审计浏览器 |
| 版本通知与管理 | 个人通知仅本人；发布/管理/重试各自授权，无角色旁路 | release_center 11项、release_mail 5项、runtime_release 4项 |
| 系统管理、认证、字段/枚举 | 当前有效RBAC及独立动作；配置写路径使用统一日志 | RBAC、user_security、字段目录、枚举、SSO事务回滚契约 |

已有19项共享能力的实际调用清单及新表单准入规则见[核对清单](../superpowers/specs/2026-10-15-pms-governance-readonly-review.md)和[定稿规格](../superpowers/specs/2026-10-14-pms-development-governance-design.md)。本批新增资源登记、队列授权、维护服务、日志安全投影、记录组件、运行版本及投递服务；未顺带重写全系统保存会话或列偏好模块。

## 验证命令与结果

后端使用已有运行时，不安装依赖：

```sh
cd backend
PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B tests/<契约名>.py
```

- 38组批量契约全部退出0，391项unittest及资源登记准入检查通过；完整列表和每项输出见`outputs/governance-validation-20261015/backend-results.json`及同目录日志。批量后补充“原用户删除”测试，队列授权从13项增为14项，受影响契约重跑退出0。
- 另跑`offline_archive_contract.py`，13项退出0。历史并发夹具明确存量标记及合同日期，不改变实际业务校验；历史升级测试仅隔离后续版本结构检查，不放宽当前生产检查。
- MSSQL建表DDL编译检查通过；未连接实际MSSQL，因此不能据此宣称MSSQL事务、锁或恢复已现场验证。

前端命令（`cd frontend`）：

```sh
node tests/style-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
node tests/archive-filter-contract.test.mjs
node tests/data-dictionary-contract.test.mjs
node tests/enum-management-contract.test.mjs
node tests/page-guide.test.mjs
node tests/page-guide-tab.test.mjs
node tests/detail-switch.test.mjs
node tests/feedback-contract.test.mjs
node tests/archive-governance.test.mjs
node tests/project-progress-workbench-contract.test.mjs
npm run build -- --outDir /private/tmp/pms-governance-development-build --emptyOutDir
```

以上退出0；构建保留既有大于500kB的分包警告，无构建错误。

Edge浏览器使用本机`http://127.0.0.1:5198`，6个脚本所有`/api/`均模拟、外域请求阻断：`archive-maintenance-browser.mjs`、`archive-governance-browser.mjs`、`governance-audit-browser.mjs`、`document-history-browser.mjs`、`task-document-history-browser.mjs`、`release-center-browser.mjs`均退出0。普通审批脚本需设置`PMS_GOVERNANCE_URL=http://127.0.0.1:5198`，默认5174没有服务的首次失败不作为验收结果。

截图：`outputs/development-governance-20261015-{maintenance,audit,about,notices,history-denied,task-history}.png`。核对了精简版本头、普通用户不见技术信息、审计并排详情、任务日志不遮挡操作列；截图中的用户、版本及记录是隔离样本，不是正式发布证据。

独立代码复核已完成：队列授权失败消息/新旧任务状态保护、维护保存迟到响应、分页页容量、任务主从及删除关闭、初始化不补权、SSO日志失败回滚、未知路由审计脱敏与用户删除FK保护等审查问题均已修复并运行相应验证。

## 真实Mac库只读副本演练

- 标准启动源：`.runtime/active-source`为`/Users/jin/Code/PMS`；`start-pms.command`默认使用`.runtime/data/pms-dev.db`，不能把`backend/data/pms-dev.db`当成标准入口。
- 实际源库标记`2026-10-14-archive-governance-02`。演练工具只读源库，备份、升级及恢复各用独立副本：`/private/tmp/pms-governance-live-copy-20261015`。目录0700、数据库0600，含业务数据，不上传Git。
- 备份SHA256：`aa1d34a3c95ad17f649754aff3b0621c9ef34bcb2a5c22cb2bff3c43ff092af5`。`evidence.json`确认`source_unchanged`、`upgrade_copy_verified`、`restore_copy_verified`均true。原档案102条、项目1条、任务6条、日志185条，源与恢复副本逐表逻辑哈希相等。
- 未修改实际源库、人员、角色、邮箱或ERP；未启动实际后台工作线程。
- 原问题提报SMTP启用，6条旧通知状态均为sent；实际验收启动需隔离旧邮件及其他后台线程，不能仅依赖新增版本邮件默认关闭。原SMTP配置保持不动，启动隔离尚未执行。

## 尚待执行与批准

1. **Mac真实开发库及现场闭环**：拟使用上述源库；执行前再做新的完整备份并校验，限定从archive-governance-02升级至governance-01，仅重启PMS自身，保持真实邮件/ERP后台关闭。4项新增权限只建节点、不自动授予角色。该实际升级需按项目数据库规则独立确认。
2. **明确测试身份**：维护、发布、投递管理需指定账号及最小范围授权；本批未改真实角色。不能用角色名或伪造用户内码代替授权验收。
3. **正式环境**：重新只读核对运行目录/提交/数据库版本；MSSQL验证备份并恢复到隔离另名库；独立批准后部署固定提交，现场验证后才发布通知。详见[升级与回退材料](2026-10-15-governance-upgrade-runbook.md)。
4. **真实邮件、Git整合**：邮件启用、合并master和推送均未执行。保留工作区及其他任务资料；不删除分支、不自动提交所有改动。

开发候选通过适用的隔离验证，尚不能宣称正式升级或真实用户端到端验收完成。

## 2026-10-15追加执行状态

上述开发交付之后，用户已独立批准Mac库限定升级；已完成升级、现有授权下的实际只读核验及两处现场显示修复，见[Mac实际升级记录](2026-10-15-governance-local-upgrade.md)。原文“实际源库未升级/待批准”描述的是开发候选交付时点，当前以追加记录为准。后台隔离、0项新增授权、0次版本发布/发信保持；正式环境不动。跨库日志时间口径、真实维护写入和正式发布完整闭环仍未验收。

2026-10-15后续验证：实际Mac库升级、维护保存/恢复、日志时间和产品线名称修复已在独立批准批次完成。新增合成库真实Vue/API及本机TLS SMTP闭环也已通过，见[版本通知隔离联调](2026-10-15-release-e2e.md)。此前“真实维护未验收/跨库时间待处理”等描述为当时状态；正式MSSQL/企业邮箱/真实受众发布和Git整合仍未执行。
