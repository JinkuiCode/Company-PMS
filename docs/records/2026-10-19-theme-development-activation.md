# 三主题开发机实际系统接入

2026-10-19，用户批准：“将这批调整更新到开发机，我在实际系统中验收一下，暂不部署正式环境。”本记录仅为本机接入，不是正式发布。

## 已执行

- 主目录及主题工作区基线均为`564653da4f1461eb985515517ece697a1c378793`。77份已验收源码摘要匹配，所有受控后端文件一致，认证store/生产路由/请求层/数据库结构无改动。
- 原`/Users/jin/Code/PMS/.runtime/active-source`、state、PID及版本记录、既有两个开发launchd配置已备份到主题工作区`.runtime/theme-development-activation-20261019/backup/`。
- active-source指向`/Users/jin/.codex/worktrees/pms-theme-ui/PMS`，不将源码复制进master，不覆盖主目录其他聊天资料。主题工作区后端复用主目录已有Python依赖。
- 沿用现有用户级launchd服务名称和参数，仅换WorkingDirectory及源码标记。保持`K3_READ_ONLY=true`、`ERP_SYNC_WORKER_ENABLED=false`。复制配置位于本批私有目录，原配置保留。实际本机后端8000/PID38760、前端5174/PID38774运行主题工作区；PID属于记录当时状态，不作为未来固定值。
- 继续使用`/Users/jin/Code/PMS/.runtime/data/pms-dev.db`；数据库文件身份、版本`2026-10-16-form-draft-02`、用户/档案/项目/任务数量及两份保护配置摘要前后相同。未执行迁移、数据导入、权限修改、邮件或金蝶业务动作。
- 5184独立预览保留。正式环境完全未操作；没有提交、合并、推送或新增发布通知。

## 验证

全部命令在主题工作区执行，退出0：

1. `python3 .runtime/theme-development-activation-20261019/verify_runtime.py before`：候选摘要、基线、后端字节、SQLite只读quick_check、版本及配置权限通过。
2. `python3 .runtime/theme-development-activation-20261019/activate_launchd.py`：仅更新8000/5174的已核对监听身份，原用户级后台服务重建；两端health/API代理成功。
3. `python3 .runtime/theme-development-activation-20261019/verify_runtime.py after`：实际监听cwd正确，仍为同一数据库且数量、版本与配置保持。
4. 在主目录运行`env PMS_STATUS_ONLY=1 ./start-pms.command`：原启动器识别两端为managed and current，目标是主题工作区。
5. `node .runtime/theme-development-activation-20261019/browser_actual.mjs`：实际5174，无API模拟；受保护档案路径回到登录页，办公蓝主题已加载；公开采购说明含新进度颜色及原行数解释；三报表和身份接口未登录返回403；无页面异常或业务写请求。

前一批72项聚焦测试、5项分页、四项规定契约、实际/隔离类型及构建、五份浏览器套件证据仅在摘要匹配后复用，没有因接入重复无关测试。详见`frontend/prototypes/theme-controls/ALL-PAGES-VERIFICATION.md`与`outputs/theme-application/verification-manifest.json`。

本次实际入口及说明已在内置浏览器打开。当前可用浏览器没有实际系统登录会话，因此不声称本轮已核对登录后的真实档案和报表数据，也未提取或绕过登录。用户可在原开发机浏览器刷新或打开<http://127.0.0.1:5174/project/archive>自行验收；这不再设为另一个AI待执行的登录等待。

## 保留与回退

当前主题工作区是实际开发服务的活动源码，在另行切换来源前不要归档。原只读启动入口仍可使用，日常数据库和保护配置仍位于主目录。若需回退，恢复备份中的active-source为主目录，并恢复备份的两个用户级启动配置；仅重建开发服务，并让原启动器登记新的监听身份，不把历史PID写回当前状态。不恢复或升级数据库。不据本机接入推断已获主分支合并、GitHub推送或正式部署许可。

详细机器证据、配置摘要和实际截图仅留本批忽略目录：`before.json`、`activation.json`、`after.json`、`browser-actual.json`、`actual-login.png`、`actual-guide.png`；不包含认证凭据。
