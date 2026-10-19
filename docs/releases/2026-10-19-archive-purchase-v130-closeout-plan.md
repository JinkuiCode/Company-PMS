# v1.3.0正式发布收尾待批准范围

正式应用5c5baea/v1.3.0已部署并恢复常规运行，schema及授权保持。此文是待批准的后续收尾范围，不是执行许可。

1. 本地先准备并隔离验证本次通知和源码对齐助手，沿用现有发布认证、RBAC、运行包/验收回执、受众/队列检查和一次有界投递；不修改产品业务逻辑。助手放在最终production-r1目录，预计新增publish.py、test_publish.py、align_source.py、test_evidence.py四项，并纳入最终审核清单。
2. 仅提交下列34项当前维护源码、相关测试及发布记录，以及随后通过隔离验证的上述四项助手。排除原始Excel、输出截图、私有目录、旧样稿、R0/R1失败助手和其他聊天的AGENTS.md、团队索引/开发总清单。失败现场及旧源码仍在原位置保留，不进行删除。两个助手目录README是当时准备快照，当前最终状态以本次发布记录及真实回执为准。
3. 当前分支仅比master多应用提交5c5baea；将批准的收尾提交快进合并master并推送GitHub。只读远端核对master仍542409037240428e34661173a07fd1ffda7d04a2。若提交/分支/远端发生漂移，先核对而不强推或丢弃其他工作。
4. 服务器源码追齐同一收尾提交并核对工作区；应用后端、已构建前端、运行release.json与保护配置字节保持，不重启，不改数据库或权限。运行应用标识仍真实构建5c5baea；源码记录提交可在其后，须分别记录，不伪造构建身份。
5. 使用ael现有版本发布权限，正式发布《项目档案录入与采购统计优化》四项更新站内通知，并向当前启用用户已有邮箱做一次有界投递。发布前重查运行证据、已发布版本、启用用户、通知/邮件队列；身份仅在维护窗口隐藏输入。无邮箱者保留明确投递结果；未知投递结果停止，不自动重试。站内通知覆盖启用用户并保留未读跟踪，关联archive、purchase页面说明；不发送无关邮件，不改邮件配置。
6. 核对通知、邮件投递结果和三端源码/实际运行证据，更新本批记录及change.md；没有新增授权、业务写入或ERP操作。

四项通知内容沿用outputs/archive-field-linkage-20261019/release-notes.draft.json：采购已审核且终止正常；草稿/正式全局编号唯一；档案必输及默认值；产品线关联机型与系列。发布版本v1.3.0，链接到已更新的页面说明。

## 当前34项归档清单

- `ops/releases/archive-purchase-v130-20261019-production-r1/Initialize-PrivateWorkspace.ps1`
- `ops/releases/archive-purchase-v130-20261019-production-r1/README.md`
- `ops/releases/archive-purchase-v130-20261019-production-r1/controlled.py`
- `ops/releases/archive-purchase-v130-20261019-production-r1/pins.json`
- `ops/releases/archive-purchase-v130-20261019-production-r1/program_update.py`
- `ops/releases/archive-purchase-v130-20261019-production-r1/resume.py`
- `ops/releases/archive-purchase-v130-20261019-production-r1/test_controlled.py`
- `ops/releases/archive-purchase-v130-20261019-production-r1/test_files.py`
- `ops/releases/archive-purchase-v130-20261019-production-r1/test_program_update.py`
- `ops/releases/archive-purchase-v130-20261019-production-r1/test_resume.py`
- `ops/releases/archive-purchase-v130-20261019-production-r1/test_windows_locale.py`
- `ops/releases/archive-purchase-v130-20261019-production-r1/test_windows_update.py`
- `ops/releases/archive-purchase-v130-20261019-production-r1/windows_update.py`
- `ops/releases/archive-purchase-v130-20261019-r2/Initialize-PrivateWorkspace.ps1`
- `ops/releases/archive-purchase-v130-20261019-r2/README.md`
- `ops/releases/archive-purchase-v130-20261019-r2/controlled.py`
- `ops/releases/archive-purchase-v130-20261019-r2/isolated_probe.py`
- `ops/releases/archive-purchase-v130-20261019-r2/pins.json`
- `ops/releases/archive-purchase-v130-20261019-r2/program_update.py`
- `ops/releases/archive-purchase-v130-20261019-r2/resume.py`
- `ops/releases/archive-purchase-v130-20261019-r2/server_rehearsal.py`
- `ops/releases/archive-purchase-v130-20261019-r2/test_controlled.py`
- `ops/releases/archive-purchase-v130-20261019-r2/test_conversion_fixture.py`
- `ops/releases/archive-purchase-v130-20261019-r2/test_files.py`
- `ops/releases/archive-purchase-v130-20261019-r2/test_historical_conflicts.py`
- `ops/releases/archive-purchase-v130-20261019-r2/test_program_update.py`
- `ops/releases/archive-purchase-v130-20261019-r2/test_rehearsal.py`
- `ops/releases/archive-purchase-v130-20261019-r2/test_resume.py`
- `ops/releases/archive-purchase-v130-20261019-r2/test_windows_update.py`
- `ops/releases/archive-purchase-v130-20261019-r2/windows_update.py`
- `docs/releases/2026-10-19-archive-purchase-v130-isolation.md`
- `docs/releases/2026-10-19-archive-purchase-v130-production-plan.md`
- `docs/releases/2026-10-19-archive-purchase-v130-closeout-plan.md`
- `change.md`


## 整批批准与助手验证

用户批准call_2953949e83114a4e99aafadee3a060d4，覆盖本文件整批收尾。通知及源码对齐四文件先写测试，当前助手缺失RED复现后实施；7项发布/一次投递/无邮箱/未知及SMTP暂拒停止测试、3项验收证据/实际临时Git快进与运行文件保留测试均通过。SMTP为模拟，不连接正式数据库。两次独立只读审查无遗留实质问题。

为了把实际通知与邮件结果一并写入最终收尾提交，执行顺序为：先完成通知/一次投递，记录真实结果，再一次提交本批文件、快进master并推送，最后服务器源码对齐。已向用户说明，动作对象和批准范围不变，应用不重启。publish要求正式源码仍为固定BUILD；align_source要求本版本publication-and-mail-complete才允许更新源码。不得将安装版本5c5baea伪造为随后文档/助手提交构建。


## 已执行的通知结果

正式通知预检及身份验证通过，发布版本v1.3.0/release_id5。18位启用用户均有站内记录，18封邮件一次投递均被SMTP接受，无失败或未知；本人实页通知仍未读，查看说明链接正常，档案页“最近更新v1.3.0”已更新。发布未重启或改权限/配置。记录见production-plan及outputs/archive-purchase-v130-20261019/publication-observed.json。后续Git/服务器最终核对结果单独存储于final-alignment.json，不循环改写本记录的自身提交身份。
