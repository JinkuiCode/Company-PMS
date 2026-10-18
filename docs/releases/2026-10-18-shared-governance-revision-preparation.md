# v1.2.0 修订候选及正式维护准备

2026-10-18。用户批准call_ff1976010a024484ad0cffc8e30482bd：当前功能分支提交明确14项、修订固定候选、准备及隔离验证部署/回退助手；不包括正式变更、额外Git提交、合并推送或真实通知。已复用原方案，当前本机准备完成不等于正式发布。

## 本地提交与固定包

- 分支codex/pms-unified-query；新应用提交3c01fe057ae8b49009d5059f9d75b478deac84e7，真实直接父e06174e98546cb70970d642012c6a3dcab3bda98。14项与批准摘要精确相同，索引空；相对master d81ba3b累计70个路径。没有合并或推送。
- 最终候选：release/shared-governance-v1.2.0-r3-20261018/pms-v1.2.0-3c01fe05-20261018-r3.zip，SHA-256 **cf1113f3f1a5e182d1caed7847ca79a2a568a1affcdddca86d3ca15ed4691aa8**。
- 包内真实parent为e061，base_commit另记d81；此前R2把两者混淆，独立审查发现后修正并重建。R2原包保留为superseded，不能部署；原a3候选及v1.1.0材料也保留。版本仍为尚未发布的v1.2.0，无虚构新正式版。
- 固定Git快照的三项必需前端规范及构建退出0；425项ZIP、424项校验摘要、421项来源字节比对、实际运行清单解析、另库源码恢复和14项摘要通过。直接父与bundle基线分别对照真实Git验证，746项范围外文件保持。升级说明追加提报关闭保护及说明链接，历史根release-notes.json未使用。

## 助手与证据

ops/releases/shared-governance-v120-20261018为本批新准备、尚未提交的维护材料，不混入上述已固定14项及候选源码。固定ZIP/bundle/pins，准备新私有目录ACL、只读预检、程序备份、仅PMS切换、受控验收、验收通过后恢复原运行，以及失败时另批程序回退。详细范围/步骤见其README。

隔离结果：2项程序门禁、6项真实R3文件/Git安装回退、7项Windows门禁和2项恢复门禁全部退出0；另1次固定候选真实ASGI生命周期通过，四类worker暂停、8条路径503、网络拒绝且SQLite副本不变。Windows目标/完整argv、ACL/子文件NULL DACL均有RED→GREEN证据。没有将这些替代真实Windows启停/SQL2017/普通用户现场。

独立审查发现的parent、私有备份ACL、进程额外参数及子文件NULL DACL问题已逐项修正并复验。保留全部失败证据，不自动重试正式动作。

## 正式只读观察

用户于本轮打开PMS正式维护窗口后，15:43—15:51（UTC+8）只读确认：10.10.1.228/C:\PMS/master仍为d81；运行v1.1.0/d719，PID6760的created、SID、exe和完整command与此前正常启动回执完全一致，PID文件一致；运行回执/启动助手/原Start-Pms脚本及运行清单摘要均核对。实际解释器为既有Python313路径，助手据此固定，未猜测venv。health正常，autoRestart=false。

SQL使用现有运行身份仅SELECT确认10.10.1.230/PMS/form-draft-02，ERP、导出、问题邮件、版本邮件的待执行数均0。PowerShell5.1在内存构造新目录ACL得到protected=true、3规则、no_acl_applied=true；没有Set-Acl、传文件、建正式目录、复制秘密、备份正式程序、启停PMS或任何数据库写入。首次读UTF8清单被PowerShell默认编码误解，改用Encoding UTF8读取后通过，文件原值未改。

15:59追加只读核对：C盘可用20.15GB，无自动重启覆盖任务，新维护目录尚不存在，旧程序备份清单存在。

观测只代表当时状态；正式窗口内仍须重验空间、自动重启、队列、来源及所有摘要。固定的启动回执变化会阻断停机，不能凭相同PID认定同一程序。

## 下一具体批准范围

待用户单独批准后才能进入正式窗口：上传固定材料；新建受限私有维护目录（仅该目录ACL，不改PMS用户角色或原保护文件权限）；重新预检及备份旧程序并验摘要，仅停启PMS，部署3c01fe05/R3并受控只读验收；验收真实通过并记录回执后，按同一批准包含的条件恢复原常规运行，版本邮件仍关闭。数据库结构/数据/授权保持，不索取SQL升级账号、不执行SQL服务重启或数据库恢复。

若失败保留现场，不自动回退/重复启动；使用已验证程序回退材料的实际恢复另列当时具体批准。主分支合并、GitHub推送、版本站内/邮件通知、普通用户本人/OA及真实项目金蝶联调仍未完成，不能因本文件存在标为已交付。

证据：outputs/shared-governance-revision-20261018中的commit-verification、artifacts、package-verification、production-readonly-observation、helpers-*.log及最终材料摘要。新增运维源码/本记录与本批change.md追加保持未提交，不伪称包含在3c01fe05中。
