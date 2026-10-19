# v1.3.0 固定候选与隔离演练记录

## 已批准与已完成

用户批准call_bdd992678218418fbfffea0621cf5495：38项本地提交当前功能分支，固定v1.3.0，准备助手并对SQL230/PMS做COPY_ONLY校验备份、恢复另名库测试。不含正式部署、数据库结构升级、授权、主分支合并、推送或通知。

候选5c5baea86c6abbc3d0dddc9f3d7bfaea53f11997，分支codex/pms-unified-query，master保持542409037240428e34661173a07fd1ffda7d04a2，未推送。ZIP SHA256为faf0485c96232918209fece57b1e3074ad906654ae56e41042889966a6de9827，source.bundle SHA256为d6414c73fe3d69db61b59a9770e2377827f56ea8fad078d2e55ac77eceee9fe1。

从真实提交构建前端，并重跑适用必需检查和草稿/联动/页面说明契约。精确提交文件与摘要相符。配套程序安装/回退、受控ASGI生命周期、权限/文件/主机/流程守卫六组通过；审查3项问题已修正并复验。原失败测试记录保留，最终结果为outputs/archive-purchase-v130-20261019/helpers-final-results.json。

材料已传入10.10.1.228/C:/PMS/.runtime/archive-purchase-v130-20261019并按固定摘要校验。临时传输服务已关闭；只提供3个固定文件，未开放项目目录或配置。正式只读预检退出0：源码54240903，运行v1.2.1/f15d4f45，schema为2026-10-16-form-draft-02，PMS PID1044，SQL14.0.1000.169，四组后台队列均0；配置摘要和运行保持。没有替换正式源码/程序。

## 首次SQL演练结果

用户在维护窗口隐藏输入现有独立SQL身份（call_9dc99d9c933e421cb4d80462c7bacc05），凭据未进入文件、参数或日志。COPY_ONLY/CHECKSUM完整备份、VERIFYONLY、头信息及SHA校验通过，新随机库PMS_V130_REHEARSAL_20261019_52590b47恢复成功。备份位于SQL服务器，未下载。

候选探针通过当前schema、日常身份权限、组织/枚举映射及单位优先检查，随后在“历史有效草稿重号必须为0”条件失败，进程退出1。该条件前没有测试业务写入。正式健康仍ok，PID1044，未更改正式程序、数据、结构或授权；未发邮件、调用金蝶或通知。

只读定位：1份有效历史草稿，编码L_B-202608，与同号正式档案重复，无其他草稿重号。该草稿未删除、改号或用于业务联调。失败目录、备份与隔离库保留。

## 原因及修订准备

原确认的唯一性方案是保留历史重号草稿，下次保存时拦截，不自动清理。演练的“历史重号必须为0”门槛比方案严格，是演练判定的问题，不代表业务规则应改变或允许重号保存。

R1准备目录ops/releases/archive-purchase-v130-20261019-r1：仅将此门槛改为报告已有冲突，并继续按真实SQL比较验证这些编号会被新保存拒绝；不改应用5c5baea、业务规则或已有草稿。新增隔离SQLite回归验证原行保持，旧冲突只报告不清理；其余SQL测试不变。新私有目录及全新随机恢复将保留R0现场。

原批准方案约定“失败保留材料及隔离库，不自动重试或删除”，因此新的真实SQL恢复与复验尚未执行，须确认后再进行。正式维护窗口也尚未申请或批准；不能将本记录当作SQL验证全部通过或已正式发布的证据。

R1七组本地助手验证通过；最后路径及批准守卫变更后，重新运行7项守卫测试和1项历史冲突回归，均退出0。独立复审无遗留实质问题。具体结果见outputs/archive-purchase-v130-20261019/helpers-r1-results.json及helpers-r1-changed-final.json。修订准备包maintenance-preflight-v130-r1-pending.zip已生成，摘要afc67c7ff0bbde9132c6c8e90cacbdb14426374630b1e0b4843bfa9228cd94d8；未传入服务器，隔离执行批准未设置，正式执行入口仍拒绝。批准后需将准确的复验批准引用固定到最终助手，重新核对相关测试及摘要后才可执行。

用户随后批准重新隔离验证（call_03442e2ba30c4da9b769aef151075b2d）。最终R1助手固定该引用并重跑7项守卫测试，退出0；最终包maintenance-preflight-v130-r1.zip摘要5d0da955c90851580d44f897d1fa224f1dcfa7b662d7fd05b1657248df31091d。三个固定文件已传入新的受限私有目录并校验，临时传输服务已关闭。R1只读预检退出0，正式版本v1.2.1、源码54240903、PID1044、schema及保护配置保持，四组队列均0。已启动获批R1演练；后续结果另记，不能据此宣称SQL全部通过。

## R1结果及R2修订准备

用户在新维护进程隐藏输入SQL身份（call_a82d2a89bbaa48a2aa646481c7dd87aa）。R1再次完成COPY_ONLY/CHECKSUM备份、VERIFYONLY和单备份集核验，新隔离库PMS_V130_REHEARSAL_20261019_984c186f恢复成功。随后探针以HTTPException停止，退出1，现场保留。正式后端未停止，健康检查仍ok。

只读诊断退出0：草稿权限及清理字段校验通过；合成样本已保存至版本3且仍为active。正式字段校验仅报告customer缺失，422/FIELD_POLICY_VALIDATION_FAILED；正式环境已有客户必输规则，测试样本没有填写客户。这是测试样本遗漏，不应通过关闭必输或改应用规则解决。详见outputs/archive-purchase-v130-20261019/r1-result-observed.json及服务器私有readonly-r1-diagnosis.json。实际SQL的转换重放、排序规则和并发部分尚未全部通过。

R2仅补充合成样本customer，应用5c5baea及固定包摘要不变。新增test_conversion_fixture.py直接读取探针中的同一份转换样本，通过真实草稿服务及临时SQLite验证客户必输场景：原样本RED复现相同422；补客户后转换及重放通过；移除客户仍拒绝且保留草稿、没有正式档案或队列副作用。8组助手测试均退出0（helpers-r2-results.json），独立复审无遗留实质问题。R2路径独立，执行批准未设置，正式维护批准仍为空。

R2准备包maintenance-preflight-v130-r2-pending.zip，摘要cb7eceaf7e59be8b0d95de3a837b155ab5c9105f65b0ef27c098e1a9f83061a0；未上传、未执行新的备份恢复或业务写入。按原失败边界，实际R2复验仍须批准。R0/R1材料、备份和隔离库继续保留。

## R2实际复验通过

用户批准call_6d4a1965dc384eaeb0adae85e90ccdbe后，固定准确批准引用并重跑7项守卫检查退出0。最终maintenance-preflight-v130-r2.zip摘要2054a6412b9a1d3b265fd053dd4979fe0897e84192bd6bb5b1dacaa1097aa1ad；摘要校验的引导及三项固定材料传入R2受限私有目录，传输服务随后关闭。R2只读预检退出0，正式基线保持。

用户本地隐藏输入身份（call_7e91ffe1993d41309ea1cb74336cab9c），完成新的COPY_ONLY/CHECKSUM备份、VERIFYONLY及新库PMS_V130_REHEARSAL_20261019_cdf82c77恢复。全套探针与后置正式状态核验通过，V130_R2_REHEARSAL_EXIT=0，phase=complete。

回执确认：日常身份权限、三组组织/枚举映射、类别必输及联动、单位优先、历史重号保留且拦截、草稿/正式全局编码、失败事务回滚、转正式及重复提交重放、SQL事务锁超时/释放、两路并发仅一份成功，全部通过。SQL排序规则Chinese_PRC_CI_AS下，重音字符不等价、全角字母等价，两类行为均验证。schema与授权保持；production_written=false、database_structure_changed=false、erp_calls=0、mail_calls=0；正式服务及保护配置摘要保持。见outputs/archive-purchase-v130-20261019/r2-result-observed.json。前两次失败证据未覆盖，全部备份及隔离库保留。

固定候选及隔离验证阶段至此完成。后续正式窗口方案独立见2026-10-19-archive-purchase-v130-production-plan.md；本次SQL通过不等于正式环境已更新，正式部署、通知、合并推送仍按各自边界确认。
