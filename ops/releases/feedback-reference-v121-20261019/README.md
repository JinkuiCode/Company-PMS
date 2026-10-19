# v1.2.1 人员日志显示修复维护助手

2026-10-19用户批准执行待办1、2。复用v1.2.0经验证的程序备份、受控安装、实际浏览器验收与正常恢复。目标10.10.1.228/C:/PMS，SQL230/PMS只读核验，数据库结构和授权不变。

windows_update.py deploy --approved-window-reference conversation-20261019-items-1-2：先预检、校验候选、备份旧程序并验证，再只停启PMS。失败保留现场，不自动恢复或重启。resume.py仅在实际browser-acceptance.json完整且目标、摘要和进程匹配时恢复原业务后台；版本邮件后台保持关闭。

rollback只在另批且PMS已停止时恢复配套旧程序，不覆盖数据库。publish.py以ael隐藏输入验证真实发布身份，严格限定v1.2.1及当前启用用户，一次有界处理本批邮件，未知结果停止，不自动重试。
