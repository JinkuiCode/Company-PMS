# 治理候选MSSQL结构核验兼容修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 消除正式MSSQL2017在升级核验和启动检查时的NotImplementedError，保留原唯一约束核验强度，并重新固定本地候选。

**Architecture:** 当前依赖SQLAlchemy2.0.37的MSSQL dialect未实现get_unique_constraints，治理校验却无条件调用。仅将MSSQL唯一键元数据读取改为参数化sys目录查询，SQLite保留原读取方式；不改变DDL、历史数据、权限分配或启动门禁。

**Tech Stack:** Python、SQLAlchemy2.0.37、MSSQL2017系统目录、unittest；现有固定包构建脚本。

## Global Constraints

- 状态：用户已批准本地修复、验证、本地提交和重新打包；不包含正式环境动作。
- 原候选c2d1ce299bccdd6a4d3caa7fed885b8b0b653a20及ZIP保留；原包尚未通过真实MSSQL验收，不得用于正式部署。
- 修复仅影响结构元数据读取；不捕获异常后跳过校验，不用SQLite测试替代真实MSSQL验收。
- 不增删字段/索引/业务数据，不提升数据库版本或改版本标记；数据库目标仍2026-10-15-governance-01。
- 继续使用codex/pms-unified-query，不合并master、不推送、不连接正式服务器、不部署、不升级实际数据库、不授权或发送邮件。
- 所有构建使用PYTHONDONTWRITEBYTECODE=1；不覆盖旧候选包，重新绑定修复提交。

## 根因证据

- backend/requirements.txt固定sqlalchemy==2.0.37。
- 本机已安装MSSQL dialect的方法来自Dialect.get_unique_constraints，方法体直接raise NotImplementedError。
- 使用模型元数据模拟Inspector、调用真实MSSQL dialect的方法，稳定复现backend/app/services/governance_migration.py:64异常。没有连接任何数据库或读取业务记录。
- 该校验同时用于upgrade_governance和check_database_ready，可能使升级事务失败、使已升级MSSQL启动失败。现有MSSQL测试仅编译DDL，未覆盖这一反射路径。
- 证据：outputs/governance-mssql-preflight-20261015/reproduction.json、reproduction-trace.txt。

### Task 1：先补失败契约

**Files:** 修改backend/tests/governance_upgrade_contract.py。

- [x] 用模型元数据生成列结构，用实际MSDialect.get_unique_constraints触发未实现行为，先验证现有verify_governance_structure失败。
- [x] 同一测试中的MSSQL连接只接受SELECT sys元数据，禁止DDL/DML；不能把真实方法mock为成功。
- [x] 加入同索引多列按key_ordinal排列、不同索引列不能拼成一个约束、包含列不计入唯一键、缺失唯一键拒绝、目录查询失败拒绝的案例。
- [x] 保留SQLite升级/回退、重复执行不回补权限、失败事务回滚及假版本拒绝的现有测试。

运行：

```bash
cd backend
PYTHONPATH=.:.venv-deps312 PYTHONDONTWRITEBYTECODE=1 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B tests/governance_upgrade_contract.py
```

预期先RED定位到当前反射异常，修复后所有案例GREEN。

### Task 2：最小兼容修复

**Files:** 修改backend/app/services/governance_migration.py。

- [x] 添加独立只读唯一键读取函数，按dialect分支；SQLite沿用原get_unique_constraints/get_indexes。MSSQL使用SQLAlchemy text绑定schema_name/table_name，读取sys.tables、sys.schemas、sys.indexes、sys.index_columns、sys.columns。
- [x] MSSQL仅接受is_unique=1、is_disabled=0、is_hypothetical=0、has_filter=0且非主键的完整有效唯一索引；只取key_ordinal>0的键列，按index_id分别分组并按key_ordinal排序。唯一约束及普通唯一索引都应正确识别。
- [x] 与模型UniqueConstraint逐一比较，缺失仍抛原结构错误；查询异常直接失败，不返回空结果假装成功。表结构、日志索引和问题提报字段原有核验保留。
- [x] 运行governance_upgrade_contract.py、database_upgrade_contract.py、runtime_release_contract.py、server_release_contract.py；命令使用上节同一Python和PYTHONPATH，替换测试文件名即可。
- [x] 独立只读审查修复差异、反例和无真实库写入证据；更新change.md及本计划结果。

此修复不改变数据库结构或初始化写入规则，保持数据库版本；如实施发现必须改DDL或迁移写入，暂停该部分重新说明范围。

### Task 3：重新锁定本地候选

**Files:** 本批后端修复/测试/记录；build-server-release.command保持原逻辑。

- [ ] 仅暂存本批精确路径，本地提交；原样稿、Excel、outputs和私有目录继续排除。
- [ ] 从修复提交的干净本地副本重新打包，使用既有依赖并显式禁用字节码；包名绑定新的提交SHA，保留原ZIP不覆盖。
- [ ] 再核对包内所有SHA256、源码字节、v1.0.0/7项升级说明/数据库版本、入口资源及敏感排除项，记录新的代码SHA和ZIP哈希。因没有改前端源码，可以复用原契约证据；打包仍必须重新构建前端。
- [ ] 核对实际Mac库35表/结构、受保护配置及范围外资料未变；不重启当前服务。

### Task 4：下一阶段正式预检范围（本计划不授权执行）

- [ ] 获批准后，先只读核对10.10.1.228实际运行目录、提交、数据库/版本、服务身份、后台活动、配置摘要和可用备份/隔离库条件；出现差异即按真实结果调整方案。
- [ ] 据现场路径与身份准备COPY_ONLY/CHECKSUM备份、VERIFYONLY以及隔离另名库恢复/升级演练；隔离库必须禁止ERP/SMTP外联，不能启动普通生产后台。
- [ ] 演练需逐项验证原业务/权限/日志保持、目标结构、无默认授权、重复核验及新程序启动；失败保留证据，不覆盖正式库或自动恢复。
- [ ] 仅在真实MSSQL演练和备份恢复成功后，再进入明确批准的停启PMS/限定升级/固定包替换；不得重启SQL Server、OA或Windows。实际角色授权及真实通知仍单独明确。

## 验收边界

本计划批准后完成的是本地兼容修复与重新锁定，不代表正式部署、真实MSSQL演练或企业邮箱已验收。正式现场流程必须依照已有governance-upgrade-runbook和新的现场证据执行。
