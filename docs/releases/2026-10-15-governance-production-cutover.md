# PMS治理候选正式切换记录

2026-10-15，用户独立批准正式维护窗口：10.10.1.228停启PMS、SQL230/PMS库限定升级至governance-01、部署98ac38c7及受控页面验收。验收期间ERP/导出/邮件后台暂停，不自动授权、不真实通知、不合并推送；失败保留现场，数据库恢复切换另行确认。

## 准备

- 复用当前工作区和既有候选；Git HEAD ae23468仅文档记录，业务候选仍98ac38c77f4b0bf40764f38257084b7fde5b4c81，固定ZIP SHA256 09b906b83c392c41788d5c55f6f452197a43549c7d4e74cf7b596c84c9aa14f4。
- 从干净固定候选副本制作增量Git bundle（216419字节），只带973c9af1到98ac38c7的既有历史，供服务器本地部署，不推送、不修改master。
- 现场只读运行身份HAS_PERMS_BY_NAME在既有演练库3新表的SELECT/INSERT/UPDATE/DELETE均1；autoRestart=false，8000/80，运维数据目录C:\ProgramData\PMS。早期只读命令引号语法错误已纠正，未做设置或数据修改。
- 新助手位于.runtime/governance-production-cutover-20261015；复用此前已审查、固定SHA的备份/另名恢复和数据摘要函数。新增停写后备份顺序、恢复副本逐项核对、正式DB_NAME双门禁、stdin凭据、源码/配置/上传备份、固定Git候选部署和进程内受控验收封锁。
- TDD初始RED9，补SSO可写GET/限定传输RED2、严格换行门禁RED1，最终GREEN13。独立审查指出的SSO可写GET和Windows源码换行问题已补：验收期间拦全部SSO入口，普通本地登录/退出保留；停服前全新源码副本LF检出与ZIP对照，实际安装仅规范化精确CRLF等价差异，不接受业务内容变化。
- 4类worker在受控进程内暂停，业务写请求返回维护提示503；不修改受保护配置或候选业务源码。此时尚未正式停服、升级或替换程序，不能把准备检查称为部署成功。

执行证据后续追加；脚本/回执位于本项目私有.runtime及outputs目录，不加入安装包或Git。

## 执行前补充验证

独立审查进一步指出旧版Settings没有PMS_RELEASE_MANIFEST属性，以及新生成根release.json未被Git忽略；助手已增加旧Settings安全读取、环境路径门禁，部署后的工作区只允许精确的`?? release.json`，且该文件必须与固定包逐字节相同。未修改.gitignore或候选业务代码。RED2后GREEN15。

一次性全新Git副本实际运行Cutover.install：973c9af1→固定bundle→98ac38c7 detached，backend/ops/frontend dist及根release.json全部字节与ZIP一致，旧dist保留，最终仅根运行清单为预期未跟踪文件。实际安装检查退出0，原项目程序与数据库未参与。证据为outputs/governance-production-cutover-20261015/{tests-green.log,local-install-check.log,helper-source-sha256.json}。

执行前最终补充：已新增8000监听PID、实际启动PID、受控回执PID、可执行文件、启动路径、写入封锁标志及运行者SID绑定门禁，RED1→GREEN16。现场GetOwnerSid核对原PMS进程与当前执行者SID一致，保持原运行身份。固定助手SHA256 c917cf6197b36a21cd88c8fcc2c784e1d2444b67f2415b4c925a275b8eae00e2；临时传输18961仅开放4个命名工件给228，非228来源实际404。传输进程PID30748，任务会话18978，阶段结束需关闭；仍未停正式PMS。

## 服务器准备通过，等待本地SQL身份

最终独立审查无剩余执行阻断；16项测试退出0，bootstrap与固定哈希一致。远程运行新私有目录引导后，服务器回执依次preflight-verified、program-backup-verified、awaiting-local-sql-identity。正式库PMS仍archive-governance-02、源码973c9af1、backend_stopped=false、受保护配置保持。

旧源码归档/Git历史备份、前端及受保护配置备份、全新候选源码副本字节核对通过；目录C:\PMS\.runtime\governance-production-cutover-20261015\previous-program。用户已被请求在维护窗口本地隐藏输入SQL管理用户名及密码。当前尚未停PMS、制作切换时点数据库备份、正式升级或替换程序；后续以实际安全回执追加，不重复启动助手。

## 正式切换实际完成，待页面验收

用户本地输入身份后，助手依次完成pms-stopped、backup-verified、isolated-restored、final-backup-restore-verified、formal-upgrade-verified、candidate-installed、controlled-pms-started、deployed-awaiting-browser-acceptance，返回PMS_GOVERNANCE_DEPLOYED_CONTROLLED；无需再次运行助手或升级脚本。

- 停写后备份文件：`D:\Program Files\Microsoft SQL Server\MSSQL14.MSSQLSERVER\MSSQL\Backup\PMS_GOV_CUTOVER_20261015_fc5f4117.bak`，COPY_ONLY/CHECKSUM，VERIFYONLY通过、1个完整备份集。SHA256 `6d5d46a8e77b6ac1ad683e18a31f9aaea0008808502299453b1013edf1adf2da`；SQL记录完成时间2026-10-15 16:46:30，FirstLSN 82000000221700130，LastLSN 82000000227300001。
- 新恢复副本`PMS_GOV_CUTOVER_20261015_fc5f4117`使用全部新文件，无WITH REPLACE；恢复内容与停写正式快照精确一致。本次切换没有使用先前在线演练备份替代最终备份。
- 正式SQL230/PMS实际升级至`2026-10-15-governance-01`，固定候选`98ac38c77f4b0bf40764f38257084b7fde5b4c81`部署，程序用户版本v1.0.0；服务器本地Git为该候选detached状态，原分支未合并、未推送GitHub。
- 启动前升级保持核验通过：29张既有业务/授权表摘要、原菜单和原列结构保持；档案3652条；4新权限节点零授权，3版本通知新表零记录。正式升级通过候选upgrade_database.py的governance_only限定入口，不调用通用初始化。
- 后端、运维源文件、前端dist及根release.json全部与固定ZIP一致，HTTP实际前端入口字节一致；受保护配置保持。新PID与8000监听者、受控ready证明、程序路径、原SID绑定检查通过。ERP/导出/问题邮件/版本邮件worker继续暂停；业务写请求及SSO入口维护封锁保留。源码无变更，只有固定包生成的根release.json为预期未跟踪文件，不改.gitignore。

随后新进程独立只读复核返回PMS_INDEPENDENT_LIVE_VERIFIED：数据库版本/结构、菜单、业务表（认证活动表另核）、配置、所有部署文件、源码HEAD、受控PID及封锁标志均通过。13787条切换时历史日志从本次恢复副本逐ID摘要与正式旧列逐项比对保持，现场日志13788条，允许正常认证/审计追加；sys_login_failure、sys_operation_log、sys_remember_token没有被误判为必须全表静止，其他表仍精确核验。3张新表持续为空。

独立核验私有服务器文件`independent-live-verification.json`，本机安全回执phase为independent-live-verified；验证源码在outputs同名目录。正式IAB页面已打开到http://10.10.1.228/login，请用户现有ael登录后继续页面验收。尚未恢复后台/业务写入、授予权限或发布实际通知，不能称全部正式闭环完成。

## 实页验收、名称修正和最终收尾

用户ael已登录并实页确认：项目档案默认启用/主机条件显示311条、编码倒序；A-202666详情显示8吋Bench名称并保持只读，单据有2条日志，展开可见同步状态和最后同步时间等中文字段差异；共享说明包含临时维护授权/原因/撤权及同步规则；关于PMS显示v1.0.0/正式环境，升级通知空状态符合零发布；管理员操作审计及登录详情可正常查看，时间16:51:23等与MSSQL原口径一致。本批没有提交正式业务样本写入或真实HTTP授权变更请求。

发现旧受保护配置APP_NAME原值为乱码：诊断确认配置原值即乱码、环境未覆盖、代码默认值正确，原配置与切换前哈希一致。用户独立批准仅修正该字段。name_fix.py字节函数RED2→GREEN2、回执原state保留RED1→GREEN3，独立窄复核通过；新命名脚本经固定SHA下载执行，先备份且验证只有APP_NAME变化，再按相同SID仅重启受控PMS。后台和业务/SSO封锁保持、数据库及固定源程序不动。期间Windows更新窗口自行居前，首次命令未进入维护控制台；只最小化窗口，先确认脚本/结果均不存在才继续，未操作系统更新设置或重复执行修正。

配置备份服务器`application-name-before.env`；修正前SHA256 `98a7f6a01311218596631dcd02fd2f3ae1d47745371264217834d0a8aa6c97ad`，修正后`833ffbbe21ca598495a59912e741a1b0239f29cb1f132cd761acb73f393b207a`。修正记录`name-fix-verification.json`，当前受控PID3000；旧ready证明与原cutover-state/原配置哈希保留，不伪造“配置全部未变”。页面刷新后会话保持，关于页实际显示“PMS 项目管理系统 / v1.0.0 / 正式环境”，乱码修复成立。

最终新连接只读复核`final-readonly-verification.json`返回PMS_FINAL_READONLY_VERIFIED：APP_NAME以已验证备份的精确单字段替换核对，其余受保护配置保持；数据库版本/结构、固定源文件/静态资源、当前受控PID与SID及维护封锁均通过。3652档案保持；13787旧日志原列逐ID摘要保留，当前13789条，认证活动表单独处理。ael当前有效上下文对project:archive:maintain、system:release:publish/manage/retry均拒绝，未新增授权；此为真实库有效权限计算，未声称受控503代替实际HTTP403撤权验收。3张版本通知表持续为空。

常规恢复只读预检：ERP6条success；导出3 expired/1 failed，无活动排队；问题邮件2 sent，无待发；版本邮件空。原配置ERP worker与问题邮件开启，版本邮件关闭；本轮仍保持4类worker暂停、业务写及SSO维护封锁，恢复须另行批准。恢复方案见`../superpowers/plans/2026-10-15-governance-resume-normal-runtime.md`。

临时传输18961已正常Ctrl-C结束并检查连接拒绝；更换过的旧传输进程也已终止。安全回执、浏览器验收摘要、测试及当前检查点在outputs/governance-production-cutover-20261015；服务器备份/恢复副本/配置材料保留。当前已批准的受控切换范围完成，未恢复常规业务、未授权或通知、未Git合并推送；A2b3整体正式发布闭环仍待后续批准。

## 常规运行已恢复

用户另行批准后，既有Start-Pms.ps1恢复正常main:app，新PID7160，业务写入与SSO临时封锁解除，原ERP/导出/问题邮件后台恢复，版本邮件关闭。恢复前无待执行旧任务，实际健康/固定文件/配置/版本及正式登录页面复验通过；18962临时传输已关闭。完整范围、证据和OA会话验证限制见[恢复记录](2026-10-15-governance-normal-runtime.md)。原备份保留，新权限和真实升级通知/Git整合仍未执行。
