# PMS Windows 运维模块

本目录用于正式服务器的开机启动、健康检查、日志轮转和部署前备份。脚本不包含业务密码或密钥，也不自动修改数据库。

## 首次配置

1. 复制 `pms-operations.example.json` 为 `pms-operations.json`。
2. 按服务器现场实际路径修改程序、Python、Nginx、受保护配置和数据目录。
3. 确认 `backend/.env.local` 已补齐生产配置，并设置 `PMS_ENV=production`、`DEBUG=false`。
4. 先运行 `backend/scripts/check_runtime_config.py`。输出只包含缺失字段名称，不显示配置值。

## 安装顺序

1. 运行 `Export-PmsOperationsBackup.ps1` 保存程序、Nginx 配置、受保护配置和计划任务。
2. 手工运行 `Start-Pms.ps1`，验证后端 `/api/health`、PMS 直连、OA SSO 和金蝶只读查询。
3. 以管理员身份运行 `Install-PmsTasks.ps1`，注册开机启动、每五分钟健康检查和每日日志轮转。
4. 在批准的维护窗口重启服务器，确认三个计划任务结果及所有业务验收项。

健康检查默认只记日志并返回失败，不自动重启。确认现场稳定后，才可在配置中启用 `autoRestart`。健康记录保存在 `C:\ProgramData\PMS\logs\health.log`。

## 数据库备份与恢复

程序脚本不会保存数据库口令。SQL Server 备份应继续使用服务器既有受控方式执行 `COPY_ONLY` 和 `CHECKSUM`，并运行 `RESTORE VERIFYONLY WITH CHECKSUM`。恢复演练只能恢复到独立测试数据库，不得覆盖正式 `PMS` 数据库；正式恢复必须另开维护窗口。

## 回退

停止计划任务后运行 `Stop-Pms.ps1`，恢复本次备份的程序、Nginx 配置、受保护配置和任务定义，再按原方式启动。程序回退不会撤销已经同步到金蝶的业务数据。
