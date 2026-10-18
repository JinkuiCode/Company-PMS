# 草稿02：SQL2017隔离演练记录

2026-10-18。首次隔离升级因驱动约束反射未实现而停止并回滚；用户另批兼容修复和全新库复验后，第二次完整备份/校验、恢复、升级及重复执行验证均通过。原备份、失败库及旧候选保留。本文是隔离演练通过记录，不是正式上线或完整应用/API验收记录。

## 固定材料

私有目录`.runtime/archive-draft-mssql-rehearsal-20261018`包含server_rehearsal.py、test_server_rehearsal.py、package_snapshot.py、candidate.zip、transfer.py、bootstrap.ps1及package.json。后端包338个程序/脚本/测试文件与已通过Mac真实验收的candidate-r2逐字节一致，加上snapshot.json与SHA256SUMS共340项。快照明确标记未提交、commit为空；不伪造release.json或Git身份，不以此发布v1.1.0。

14项安全测试通过，独立只读审查无剩余重要问题。下载引导独立固定helper与ZIP的SHA256，两项校验通过后才执行。传输仅绑定当前只读核对的Mac公司接口10.10.91.223:18960，仅向来源228提供两个文件；没有回执上传入口。正式机私有目录创建后限制SYSTEM/Administrators权限，已有目录不覆盖复用。

证据：[助手准备收据](../../outputs/archive-draft-management-mac-20261018/server-rehearsal-preparation.json)。本机安全测试不能替代真实SQL2017演练。

## 待批准执行范围

1. 在10.10.1.228只读预检当前程序、保护配置、PID/前端/版本清单摘要、健康及SQL230/PMS版本。历史基线为6ebc2d2e/v1.0.2/governance-01，实际不符即停止，不擅自重新定基线。
2. 下载仅供演练的后端快照和助手到新建私有目录，不替换C:/PMS正式程序。使用现有独立SQL备份恢复管理员，用户名/密码均由用户在维护窗口隐藏输入，不写代码、参数或日志。
3. 对PMS在线COPY_ONLY/CHECKSUM完整备份并VERIFYONLY，核对备份单集及SHA256、磁盘余量和所有数据/日志文件列表。备份恢复会增加服务器负载。
4. 恢复至随机新库PMS_DRAFT_REHEARSAL_20261018_加8位随机后缀，库及物理文件必须不存在，无WITH REPLACE。失败保留证据，不自动覆盖、重试、恢复正式库或删除隔离库。
5. 候选子进程仅连接隔离库，先检查实际库名；不读正式配置、不导入main、不调用init_db、不启动worker。串行执行governance-01→form-draft-01→02限定迁移和结构检查，重复执行不改变结果。仅允许新增空草稿表、一个未授权管理节点和版本变化，全部既有结构/数据/授权保持。
6. 以现有日常运行身份连接隔离库，只读查询草稿表SELECT/INSERT/UPDATE/DELETE四项有效权限；不足则停止，不授予。执行后再次核对正式程序、PID、配置、清单及前端摘要和健康保持。

正式PMS不停服，不升级正式库，不替换正式程序，不修改授权，不发邮件/通知，不操作金蝶，不Git提交/合并/推送。此次演练不等于完整应用启动/API或正式切换验收，后续正式维护窗口另批。

## 已批准并开始执行（等待SQL身份）

用户随后明确批准“现在执行隔离演练”。Windows App只读现场核对：IPv4为10.10.1.228，正式HEAD仍6ebc2d2e，v1.0.2/governance-01，工作区仅已知未跟踪release.json，health为ok、后端PID5656未变，本轮目录原不存在。

按固定引导创建私有演练目录并下载两份文件，helper/ZIP独立摘要校验后启动；控制台依次显示preflight-verified和awaiting-local-sql-identity，现停在用户名隐藏输入提示。助手预检包括正式PID/前端/配置/清单摘要、实际SQL库和版本及依赖版本检查；本机临时传输服务已核对归属后停止。没有停止PMS或替换正式程序，尚未开始备份、恢复或隔离升级。

需要用户在维护窗口自行输入现有独立SQL管理员用户名、密码；不在聊天发送，也不保留上次维护密码。证据：[现场观察记录](../../outputs/archive-draft-mssql-server-20261018/preflight-observed.json)。当前等待身份输入不是演练成功，后续实际结果另行追加。

## 实际备份恢复通过，隔离升级停止

用户在隐藏窗口输入身份后，控制台完成backup-verified及isolated-restored；COPY_ONLY/CHECKSUM/VERIFYONLY、单备份集及SHA256均已验证。完整备份留在SQL服务器Backup目录，路径、SHA256、时间与LSN保留在服务器rehearsal-state.json中，不覆盖旧备份。

新库为PMS_DRAFT_REHEARSAL_20261018_f66bb9ee。隔离子进程在升级阶段抛NotImplementedError，助手停止且不自动重试。只读检查确认失败库仍governance-01、无pms_form_draft表，说明本次事务已回滚；原失败库保留。正式库实际版本仍governance-01，正式程序仍v1.0.2/6ebc2d2e，health为ok、PID5656，运行进程/前端/版本清单指纹与演练前完全相同；没有替换正式程序或升级正式库。

根因：SQLAlchemy2.0.37的MSSQL get_check_constraints没有实现，草稿结构验证直接调用该方法。服务器只读驱动探针确认同样抛NotImplementedError；SQL实际构建号14.0.1000.169已现场核对。详见[失败诊断](../../outputs/archive-draft-mssql-server-20261018/failure-diagnosis.json)。

## 待批准兼容修正

实际源码与固定候选目前保持原样。本机私有原型仅将MSSQL检查约束读取改为参数化sys.check_constraints/sys.tables/sys.schemas目录SELECT，按schema和表名定位；禁用或不受信任的约束不被接受，原约束名称、version正值及status集合检验继续执行。SQLite使用原反射路径，DDL、目标版本、事务、版本锁、菜单和授权逻辑不变。

8项隔离替身测试原码RED、原型GREEN，覆盖有效/缺失/禁用/不受信任/放宽表达式/额外状态/SQLite及原索引门禁。独立只读代码审查无重要问题，不把原型测试当真实SQL2017演练通过。原型未连接数据库，尚未应用到backend或候选；[可审阅差异](../../outputs/archive-draft-mssql-server-20261018/proposed-check-reflection.diff)。

下一步需批准将兼容修复纳入源码、补充契约并生成新固定包，随后在全新另名库中按原范围重做演练，保留旧包/备份/失败库，不覆盖重用。正式库与程序继续保持。旧SQL维护进程已结束且不保留凭据，复验时需要重新隐藏输入身份。


## 已批准兼容修复及新候选（r3）

用户明确批准“修复并重新隔离演练”。实际迁移源码已采用上述参数化目录查询，SQLite路径、完整约束检验、历史DDL、目标form-draft-02、事务和授权规则不变。新增可移植契约测试先在原源码RED，再修复GREEN；拒绝场景要求明确的检查约束错误，避免把未实现异常误当拒绝成功。

本轮8项MSSQL专项、01升级8项、02升级7项、本人草稿14项、管理8项、治理升级16项均退出0；新助手14项安全检查退出0。独立最终审查再次验证专项8项与助手14项，无Critical/Important问题。前端未变，复用r2验收证据；本轮未重启Mac或再次升级实际Mac库。

保留旧候选，固定`.runtime/archive-draft-management-local-20261018/candidate-r3`及690项摘要。相对r2仅迁移源码和新增契约测试两文件不同。新的后端演练包339个backend文件，加快照与摘要共341项；不是Git发布身份。

新演练目录：`.runtime/archive-draft-mssql-rehearsal-20261018-r2`。快照e12d0e5d56ef2897ba4cdf7b0997c3b076d83e3eed7d34e81e0061f4317a65b6；ZIP 30c248dad3c45746d326a819b5b1efaee6a0a776bd43ad3107aa40c737dd81cb；助手b8cbdb2e1a70cc7039f94195d4385781ac37a92a47bd18aeaa3ed8fd786072b6。引导独立固定两份摘要，助手相对原版仅修改这些固定摘要及新独立目录。随机库仍要求不存在，不覆盖旧失败库。

证据位于outputs/archive-draft-mssql-server-20261018：source-check-reflection-red/green.txt、compat-各契约.txt、retry-helper-safety-green.txt和candidate-r3-delta.json。实际服务器复验结果随后追加，不将本机通过视为SQL2017演练成功。


## 新候选已通过服务器预检，等待重新输入身份

新目录下载的两份文件独立SHA256校验通过，助手依次显示preflight-verified、awaiting-local-sql-identity，窗口现停在SQL备份/恢复管理员用户名隐藏输入。预检重新验证正式版本、实际库修订、源码、健康、运行指纹及保护配置；未进入备份恢复或新库升级。临时传输进程已停止。需要用户在维护窗口重新输入现有身份，密码不保留、不在聊天发送。

证据：[新预检记录](../../outputs/archive-draft-mssql-server-20261018/retry-preflight-observed.json)及retry-awaiting-sql-identity.png。等待身份不等于新演练完成；原备份和失败库继续保留。


## 新隔离库实际演练通过

用户重新隐藏输入身份后，控制台显示backup-verified、isolated-restored、complete及PMS_DRAFT_ISOLATED_REHEARSAL_COMPLETE。只读复核新库PMS_DRAFT_REHEARSAL_20261018_37eea38c已达2026-10-16-form-draft-02，草稿表0行。后缀ASCII为51/55/101/101/97/51/56/99，避免截图抄录误差。

实际SQL2017升级及启动前结构检查通过；重复升级/检查后快照完全相同。32张既有表、3653条原档案及原授权保持，只新增空草稿表、未授权管理节点及版本修订。现有日常运行身份对隔离草稿表的SELECT/INSERT/UPDATE/DELETE有效权限均满足，无需或实际追加授权。完整备份COPY_ONLY/CHECKSUM/VERIFYONLY、单备份集及SHA256核验通过；准确路径、摘要、LSN、时间以服务器新目录rehearsal-state.json为准，备份文件未离开SQL服务器。

最终正式版本仍v1.0.2/governance-01，健康通过；助手回执service_unchanged及protected_configs_unchanged均true，backend_stopped为false。旧包、旧失败回执及失败库继续保留，没有清理。SQL身份随维护进程结束释放，不在聊天或文件留存。

证据：[实际完成观察记录](../../outputs/archive-draft-mssql-server-20261018/retry-complete-observed.json)、retry-complete-summary.png及retry-revision-summary.png。启动前结构检查不等同于完整应用启动或业务API真实验收；正式切换尚未执行，发布身份/候选、维护窗口、实际业务验收及通知仍按独立批准边界推进。
