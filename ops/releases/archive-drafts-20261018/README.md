# 草稿 v1.1.0 切换助手

仅供已单独批准的10.10.1.228维护窗口。本次仅完成本地准备和隔离验证，禁止据此直接执行正式切换。

- 正式基线：6ebc2d2e / v1.0.2 / governance-01，SQL230/PMS。
- 应用候选：d71971d9250f74ff560b3f4bfa68a4f95edf3c58 / v1.1.0 / form-draft-02。
- `rehearsal_base.py`为已验证的备份/新库恢复/快照对照机制，原文件完整保留并在cutover.py中固定摘要；切换覆盖固定包读取器及随机隔离库前缀，不使用原main入口。
- `cutover.py`需`--approved-cutover`，检查目标/包/运行进程/配置/版本/SQL日常权限，备份旧程序，隐藏读取SQL身份，二次预检后仅停PMS；停写后重新备份、另名恢复并比较快照，通过后才正式限定升级、安装及受控启动。
- `controlled.py`只验收读页面：登录退出可用，业务修改、OA入口、报表和外部组织/人员查询封锁，四类worker暂停。读页面的原RBAC和数据范围继续生效；不自动授予草稿管理或发布权限。
- `rollback.py`需另一项`--approved-program-rollback`批准，先核对正式库已按另批方案恢复到旧版本及切换前完整快照，且PMS停机、配置/程序备份有效。只恢复旧源码/前端/发布清单，保留当前文件，保持PMS停机。它不执行数据库还原、清理隔离库、启动旧程序或恢复worker。
- 任一步失败停止，保留现场，不覆盖原备份、不自动重试、恢复数据库或发布通知。SQL凭据仅隐藏输入及子进程stdin传递，不入参数、代码或日志。无回执上传。

本地验证（Python3.12）：

```text
python3 -B ops/releases/archive-drafts-20261018/test_cutover.py
python3 -B ops/releases/archive-drafts-20261018/test_rollback.py
python3 -B ops/releases/archive-drafts-20261018/test_install_rollback.py
python3 -B ops/releases/archive-drafts-20261018/test_install_rollback.py --missing-live-dist
PYTHONPATH=backend:backend/.venv-deps312 python3 -B ops/releases/archive-drafts-20261018/test_controlled_startup.py
```

前三类仅用标准库、私有固定包和一次性Git副本，无SQL/服务操作。受控启动检查复制本机SQLite库，实际执行ASGI生命周期/版本/结构/中间件；为允许SQLite替身，单独替换正式MSSQL配置校验，不替代真实SQL2017部署验收。不开监听、不外联，副本字节保持。

包、bundle、固定引导及运行清单位于被Git忽略的`.runtime/archive-draft-release-20261018`；该目录不进Git，不含凭据。引导的所有摘要在执行前再次验证；当前没有监听或传输服务。正式操作顺序和批准边界见本轮正式切换方案。
