# v1.2.0 程序部署、受控验收与回退助手

本目录为已批准的本机准备材料，尚未提交Git、上传或执行正式变更。程序候选为3c01fe05/R3；目标固定10.10.1.228，SQL230/PMS保持form-draft-02。只有新的具体正式维护批准才可执行。不得运行旧v1.1.0结构升级助手。

## 已固定的身份

- 程序源码旧HEAD为d81ba3b，旧实际运行清单为d71971d/v1.1.0；两者分别校验。
- 新包、bundle、完整提交、build_id与schema固定在pins.json；windows_update.load_pins同时固定其摘要。
- 原进程绑定此前已验收的normal-process.json摘要、PID/created/SID/完整参数、原resume_runtime.py摘要、Start-Pms.ps1与运行清单摘要。当前只读观测进程6760仍符合。不能只凭PID文件或某个参数子串停机。
- 完整命令拒绝额外app-dir/reload/factory等覆盖；解释器固定为现场实际Python313路径，不能猜测为venv路径。
- 任一前提漂移须停止受影响动作并重新核对，不自行更换基线。

## 新私有目录

另批窗口内先在目录外运行Initialize-PrivateWorkspace.ps1，带明确批准引用。仅创建全新C:\PMS\.runtime\shared-governance-v120-20261018；若已存在即拒绝。该新目录只允许当前维护SID、SYSTEM及Administrators，子文件继承；不改原配置/目录ACL。材料传入后校验全部摘要。

所有读取维护状态/配置和复制保护配置前，逐对象检查根目录及全部子文件的ACL、owner和reparse；任何NULL/空DACL、其他主体或链接拒绝。目录名private不是权限证明。实际Set-Acl尚未执行；本机门禁反例及正式Windows的内存规则构造已验证，不冒充实际目录ACL验收。

维护目录中放本目录程序、pins.json、candidate.zip和source.bundle。新候选zip更名为candidate.zip不改变其字节；候选原文件及历史包保留。不得传入密码/SQL升级身份或使用公开传输目录保存备份。

## 正式动作顺序（均未执行）

1. `windows_update.py preflight`：只读重验固定来源、正常进程、保护摘要、schema、队列、自动重启、空间和包。需先有安全目录；不创建备份、不停机。
2. 另批后`windows_update.py deploy --approved-window-reference <真实批准引用>`：预检、stage、备份旧源码/完整历史/前端/运行清单/私有配置，校验后再次预检；仅停PMS、再次核schema/队列，安装固定源码和前端并受控启动。业务写入、OA、外部查询和四类worker暂停。流程无数据库备份/升级/恢复、角色授权、通知发布或邮件发送。
3. 浏览器以现有账号实际验收版本/说明、档案和进度读取、系统列表、提报关闭一次确认；不提交业务数据。实际完成后才由操作人员记录browser-acceptance.json，含commit、archive_sha256、controlled_pid、accepted=true、verified_at、verified_by和四项checks：version_and_guide、archive_and_progress_read、system_lists_read、feedback_close_once。禁止用模板或本机测试填正式通过。
4. 只有维护批准包含“验收通过后恢复常规运行”时，运行`resume.py --approved-window-reference <真实批准引用>`：验证实际验收回执、当前进程、包和队列后，仅停受控PMS，使用原Start-Pms.ps1恢复；ERP/导出/问题邮件按原配置运行，版本邮件进程变量继续false，不改保护配置。失败保留现场，不自动重复启动。
5. 失败回退必须另有针对当前现场的具体批准，PMS先保持停止，再`windows_update.py rollback --approved-window-reference <真实回退批准引用>`。验证备份、schema与保护配置，恢复旧程序/前端/运行清单，保留被替换文件，保持PMS停止。不执行数据库恢复或恢复配置。需要恢复常规运行时另按现场方案执行。

重复deploy或已有状态拒绝；每一步保留私有阶段记录。失败不自动回退、不重试、不启动旧程序。readonly预检使用现有运行身份只做SELECT，不索取SQL升级管理员。

## 隔离验证

- test_program_update.py：目标、批准、来源、停止状态、队列等门禁；维护HTTP白名单。
- test_files.py：真实R3包/bundle在一次性Git副本安装和回退；丢失前端、复制中断、篡改、保护配置及数据库标记保持，恶意ZIP拒绝。
- test_windows_update.py：错误机器/目录、逐对象ACL及NULL DACL、完整进程参数、可信启动回执、失败停止和损坏运行清单下的停机回退上下文。
- test_resume.py：真实验收目标/完整性及正常恢复环境。
- test_controlled.py：固定候选真实ASGI生产只检查分支、实际schema检查、四类worker全部暂停、8条路径封锁；仅SQLite副本且仅替换MSSQL配置校验，网络连接拒绝、不开监听、副本字节不变。

以上不能代替Windows实际部署、SQL2017现场及本人/OA/真实金蝶验收。具体结果和命令见outputs/shared-governance-revision-20261018。
