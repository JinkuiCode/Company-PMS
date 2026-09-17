# PMS Windows 运维模块

本目录用于正式服务器的开机启动、健康检查、日志轮转和部署前备份。脚本不包含业务密码或密钥，也不自动修改数据库。

## 首次配置

1. 复制 `pms-operations.example.json` 为 `pms-operations.json`。
2. 按服务器现场实际路径修改程序、Python、Nginx、受保护配置和数据目录。
3. 确认 `backend/.env.local` 已补齐生产配置，并设置 `PMS_ENV=production`、`DEBUG=false`。
4. 先运行 `backend/scripts/check_runtime_config.py`。输出只包含缺失字段名称，不显示配置值。

## 安装顺序

1. 运行 `Export-PmsOperationsBackup.ps1` 保存程序、Nginx 配置、受保护配置和计划任务。
2. 首次部署本版本或数据库版本变更时，先停止 PMS 服务，在已验证的数据库备份和授权维护窗口内，用独立升级身份执行 `backend/scripts/upgrade_database.py`。升级成功后再启动新版服务；日常开机任务不运行升级脚本。
3. 手工运行 `Start-Pms.ps1`，验证后端 `/api/health`、PMS 直连、OA SSO 和金蝶只读查询。
4. 以管理员身份运行 `Install-PmsTasks.ps1`，注册开机启动、每五分钟健康检查和每日日志轮转。
5. 在批准的维护窗口重启服务器，确认三个计划任务结果及所有业务验收项。

健康检查默认只记日志并返回失败，不自动重启。确认现场稳定后，才可在配置中启用 `autoRestart`。健康记录保存在 `C:\ProgramData\PMS\logs\health.log`。

## 服务器文件位置

- `C:\PMS` 是正式运行目录，不将发布临时包或历史副本混放在其正常源码和配置目录中。
- 一次性发布材料、旧代码副本和核对报告统一放在 `C:\PMS\.runtime` 的专用子目录；历史发布目录为 `release-history\日期`，期初数据核对材料为 `initial-import\日期`。`.runtime` 不入 Git，也不包含在常规程序备份中，清理前应另行核实是否需要独立备份。
- `C:\nginx` 是独立运行组件；`C:\backup` 和 `C:\ProgramData\PMS*` 现有备份及受保护运行资料按各自运维策略保留。本规则不授权移动这些目录，也不授权移动或删除运行中的 `C:\PMS` 文件。
- 2026-09-17 的根目录整理记录见 `C:\PMS\.runtime\release-history\20260917\move-manifest.csv`，8 项均已归档。`PMS - 副本` 含未纳入版本管理的内容，仅移至历史目录，未删除；确认独有资料无保留价值前不得删除。`Archive-PmsRootArtifacts.ps1` 可先不带参数预检，确认后再以 `-Apply` 续跑；不强制关闭占用进程。
- 金蝶期初异常中文清单在 `C:\PMS\.runtime\initial-import\20260917\kingdee-initial-anomalies-zh.csv`，同目录有中文说明及原始报告副本。含真实业务项目数据，仅留服务器本地，不纳入仓库或聊天附件。

## 数据库备份与恢复

程序脚本不会保存数据库口令。SQL Server 备份应继续使用服务器既有受控方式执行 `COPY_ONLY` 和 `CHECKSUM`，并运行 `RESTORE VERIFYONLY WITH CHECKSUM`。恢复演练只能恢复到独立测试数据库，不得覆盖正式 `PMS` 数据库；正式恢复必须另开维护窗口。

数据库升级身份由信息安全管理员临时授权，只在执行升级时使用；日常服务账号仅保留业务读写和连接权限。不要把管理员密码写入命令参数、脚本、环境模板或日志。升级命令失败时数据库版本保持未就绪，新版生产服务会拒绝启动；先定位故障并按备份方案恢复，不得手工伪造版本标记。发布前记录旧版本可用的数据库版本和回退兼容性，避免仅回退程序而继续使用不兼容的新库。

升级时可在服务器受保护目录创建仅管理员可读的临时配置副本，通过 `PMS_CONFIG_FILE` 指向它，并由管理员在远程会话中填写升级账号。升级完成立即撤去临时副本；日常 `.env.local` 始终保留运行账号。正式收回 `db_owner` 前先核对运行账号对业务表及 `pms_database_revision` 的读取和必要写入权限，并完成登录、项目读取与受控写入验收。不得在计划任务、命令行参数或聊天中输入数据库密码。

## 回退

停止计划任务后运行 `Stop-Pms.ps1`，恢复本次备份的程序、Nginx 配置、受保护配置和任务定义，再按原方式启动。程序回退不会撤销已经同步到金蝶的业务数据。
