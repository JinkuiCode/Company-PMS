# 治理候选正式服务器与隔离MSSQL演练记录

2026-10-15，用户明确批准“批准，现在执行”：受控助手、正式服务器只读预检、COPY_ONLY/CHECKSUM完整备份和VERIFYONLY、全新另名库恢复及治理升级演练。正式库不升级、不停服务、不替换程序、不改授权、不发真实通知、不合并或推送。

## 已完成准备

- 固定候选98ac38c77f4b0bf40764f38257084b7fde5b4c81，ZIP SHA256 09b906b83c392c41788d5c55f6f452197a43549c7d4e74cf7b596c84c9aa14f4；当前工作分支codex/pms-unified-query，HEAD ae23468仅记录提交。
- 新助手在.runtime/governance-mssql-rehearsal-20261015，包含server_rehearsal.py、test_server_rehearsal.py、transfer.py、bootstrap.ps1；均为本次受控运维材料，不进入安装包或Git。
- TDD初始缺失助手正例RED、连接timeout及运行指纹RED、传输白名单RED后GREEN；13项标准库测试全部通过。覆盖固定包、篡改拒绝、解压目录不复用、主机/实际库名、恢复新库/文件、完整文件列表、旧结构/数据/授权保护、版本/新增表限制、备份门禁、敏感回执过滤、真实pyodbc Cursor接口限制及进程/前端/清单指纹。
- 独立审查核心助手无剩余执行阻断，指出并已修复pyodbc Cursor不支持timeout的问题；改为Connection.timeout，加入回归。最终transfer/bootstrap还在执行前复核。
- 实际Windows App终端已只读确认IPv4 10.10.1.228、正式HEAD973c9af、git status无改动、127.0.0.1:8000/api/health返回ok。原生远程键盘丢特殊符号，改编码命令后读取成功；早期命令语法错误仅影响只读预检，没有进行设置或数据变更。

## 执行保护

正式只读连接与管理恢复连接分开；现有受保护配置仅加载/取摘要，不回传凭据。备份/恢复身份由用户在维护控制台隐藏输入，助手不记录；必须现有SQL管理员身份，权限不足不授权或提权。恢复库名使用PMS_GOV_REHEARSAL_20261015及随机8位后缀；无WITH REPLACE，库名和所有物理文件必须不存在。备份原文件留SQL服务器，HASHBYTES只返回SHA256。

隔离子进程仅通过stdin接收本次连接信息，清空外联配置环境、无真实配置文件、显式新库连接，先SELECT DB_NAME()再调用限定迁移及启动结构检查；只导入模型登记，不调用init_db/main，不启动worker。完整比对旧列、索引、外键、检查约束、历史行摘要及权限表；仅白名单新增结构/4个未授予节点/版本变化，历史新增日志字段必须为空，版本通知表无记录。

## 初始状态（历史检查点）

截至本段仅本机助手与只读远程预检完成；脚本/候选包尚未传输，尚未输入SQL管理身份，尚未备份、恢复、新建隔离库或执行真实MSSQL升级。后续实际回执追加在本记录，不将准备工作报告为演练成功。

本机证据：outputs/governance-mssql-server-rehearsal-20261015/{helper-source-sha256.json,helper-tests.json,helper-tests.log}；现场私有回执位于服务器本次专用目录。

## 执行检查点：等待Mac解锁

- 最终13项测试退出0；核心助手及新增transfer/bootstrap独立复核均通过，指纹与执行材料一致。其他来源访问临时端点实测HTTP404，仅允许正式228取固定两文件。
- Mac临时传输端已在10.10.91.223:18960启动。远程提交编码引导时桌面控制被Mac锁屏/物理输入保护阻止，已请用户手动解锁。当前没有server-receipt.json；不据此推断命令绝对未执行，恢复后先检查远程维护目录、控制台和回执，再决定后续。
- 应用源码、固定候选及发布清单无未提交改动，未合并、推送、修改正式程序或授权。没有收到备份/恢复/隔离升级完成证据，不能称演练成功。
- 临时传输只保留到本次执行完成或明确中止；结束时必须关闭。辅助材料及快照保留，失败不自动恢复正式库。

## 解锁后现场预检通过

解锁后先只读检查本次目录不存在（REHEARSAL_DIR_EXISTS=False），确认先前引导未执行。随后在原PMS维护控制台运行固定编码引导：新私有目录创建、候选与助手下载及SHA校验通过，实际维护进程返回preflight-verified和awaiting-local-sql-identity。期间其他PDM任务窗口仅最小化，未终止或操作其业务。

服务器回执确认：代码973c9af1、源库2026-10-14-archive-governance-02、SQL主机10.10.1.230、库PMS、SQL版本14.0.1000.169（2017）、SQLAlchemy2.0.37/pyodbc5.2.0匹配；健康及受保护配置核对通过，backend_stopped=false。新助手与候选只位于C:\PMS\.runtime\governance-mssql-rehearsal-20261015，没有替换正式程序。

当前SQL管理用户名和密码均使用getpass隐藏输入；已请用户在窗口本地输入，聊天中不收集。收到输入后才会开始备份/恢复与隔离升级；目前未收到这些步骤的完成回执。原始安全回执在本机outputs/governance-mssql-server-rehearsal-20261015/server-receipts.jsonl和server-receipt.json。


## 最终结果：真实MSSQL演练完成

用户在维护窗口隐藏输入现有SQL管理身份后，助手依次返回backup-verified、isolated-restored、complete；最终新进程只读复核返回PMS_INDEPENDENT_READONLY_VERIFIED，退出0。未保存或回传凭据。

- 正式运行主机10.10.1.228；实际SQL主机10.10.1.230、库PMS。正式源码973c9af1ea2efee52ecbb5c44b46122d5aaeac26、数据库2026-10-14-archive-governance-02均保持。
- COPY_ONLY/CHECKSUM完整备份：`D:\Program Files\Microsoft SQL Server\MSSQL14.MSSQLSERVER\MSSQL\Backup\PMS_GOV_REHEARSAL_20261015_2d7e991f.bak`。SQL记录完成时间2026-10-15 16:00:39；1个完整备份集，VERIFYONLY WITH CHECKSUM通过。SHA256 `a432bef60ea64747ccb30d7817396681e7f20906e603832f3344fcc5f5e66e01`；FirstLSN 82000000200300274，LastLSN 82000000211800001。
- 新库`PMS_GOV_REHEARSAL_20261015_2d7e991f`，使用全部新物理文件，无WITH REPLACE。固定候选98ac38c7限定升级至governance-01及check_database_ready通过；再次执行不改变结果。真实SQL2017/SQLAlchemy2.0.37/pyodbc5.2.0的兼容性得到现场验证。
- 升级前后29张既有业务/授权表原列逐行摘要一致，原菜单和既有结构投影一致；3652条档案、13776条日志保留。新增日志/提报字段无历史回填；新增权限节点4个且零角色授权；版本、站内通知、版本邮件3张新表均0行。
- 独立新连接重新采集隔离库，与升级后保存快照一致并重新运行validate_upgrade。正式库版本、干净工作区、原后端PID、全部前端资源及原运行清单指纹核对通过；助手最终健康和受保护配置保持检查通过。
- 正式PMS未停止/重启，正式库未升级，程序/配置/角色未替换或修改；助手未启动业务主应用或worker、未发金蝶/SMTP请求、未发布真实通知。无Git提交、合并或推送。此结论指本次助手操作，不推断其他既有业务进程没有正常活动。

安全元数据：本机`outputs/governance-mssql-server-rehearsal-20261015/server-receipt.json`最终phase为independent-readonly-verified，阶段流水为server-receipts.jsonl；仅含计数、摘要与运维元数据，无业务明细/凭据。服务器私有目录另存isolated-before.json、isolated-after.json、isolated-verification.json及independent-verification.json。

本机临时传输18960已关闭：受控进程Ctrl-C退出130，随后端口无监听/连接拒绝；该退出是正常清理，不是升级失败。备份、新隔离库和现场材料保留供审阅，不自动删除。当前获批范围完成，正式升级/部署及实际授权、通知另行批准。

## 独立审查与证据限制

最终只读审查未发现本轮演练阻断。启动结构核验仅指check_database_ready，不等于候选主应用完整启动、登录或真实API验收。既有应用RBAC/人员/范围数据保持及零新增授权，不等于已测试日常运行身份对新表的INSERT/UPDATE/DELETE；下一阶段须先检查有效权限，不擅自授予SQL权限。29张表为capture.tables中既有业务/授权表的行摘要计数，菜单单独逐行比对、版本单独核验；恢复副本数据比较不能扩展为正式库在线全表前后逐行不变。
