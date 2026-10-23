# 批量序列号查重性能本地候选

本批解决同一150候选块在批内序列号比较中重复展开输入的问题。仅在 `identity_batch_conflicts` 同块分支使用一份 slot/key 双列 CTE 与两个别名；正式档案连接所需的三列输入及跨块分支保持。

## 批准、版本与范围

- 人类拆分批准：`call_4fc89729a1974c7bb57d81641cb20599` 第一问，原回复“按建议拆分并复用现有聊天”；原消息 `01a166bf-99bd-7383-99ce-bb8d8936ff5a`。代码责任交接 `PMS-COORD-FIXED-SOURCE-OWNERSHIP-TRANSFER-20261023-01`。
- 最新暂停范围：`call_15d4c42d8f604864ba6d71a0886f61d4`“只暂停数据补全，已批准的性能修复继续”。Excel、补全取数、回收和批量回填保持暂停。
- 基线：`7a8ed2cdf98dddba713ebf5a8f655099940d2b97`。
- 分支：`codex/archive-serial-performance-20261023`，独立工作区 `archive-serial-performance/PMS`。只做本地提交，不合并、不推送、不部署。
- 业务文件仅 `backend/app/services/archive_serial_unique.py`，+6/-1；定向测试仅新增 `backend/tests/archive_serial_batch_performance_contract.py`。另含本说明及本区 `change.md`。
- 服务文件 SHA256：`e71a4fbd2207e49c42defe63ab64dc6f282ffd2d1c6be9b2f4d0ce19312eac54`。
- 测试文件 SHA256：`5260a2dcb4b3a467d5b5c36c481927d8edae20c2244f3f21bc1461190d6049a5`。

## 行为保持

唯一生产调用为 `offline_archive_reconciliation.build_import_plan`，无需调用方改动。逐提案正式记录自身排除、禁用正式档案、活跃新建草稿和待审批变更占用、150候选/300占用分块、SQL列原生排序规则与跨块比较不变。坏JSON/异常占用状态仍失败关闭。函数继续要求同连接的外层身份命名空间锁，未新增提交、回滚或提前释放。0/False仍由既有导入Schema拒绝，未改变低层提案过滤规则。

没有依赖、数据库结构/索引/revision、API、认证、权限或业务规则调整，没有改维护线原生探针或发布工具，没有启动服务/端口。

## 验证与限制

环境为既有 Python 3.12.14 / SQLAlchemy 2.0.37。全部应用测试清空继承环境，使用 `PMS_CONFIG_FILE=/dev/null`、私有临时合成SQLite；没有读取真实配置/数据库或连接ERP。

原函数定向RED共6项，仅同块预算断言失败（750 != 300），退出1。最终定向7项包含12组边界矩阵、同块SQL预算及实际导入计划调用；同一输入的原函数及改后SQL/参数原文与分项计时保存在私有证据中。

| 当前通过的检查 | 执行项 | 退出码 |
| --- | ---: | ---: |
| archive_serial_batch_performance_contract | 7 | 0 |
| archive_serial_namespace_contract | 6 | 0 |
| archive_serial_mssql_contract（离线编译/伪连接） | 2 | 0 |
| archive_serial_import_contract | 1 | 0 |
| offline_archive_import_contract | 16 | 0 |
| offline_archive_performance_contract | 36 | 0 |
| archive_serial_unique_contract | 14 | 0 |
| 合计（含继承测试的执行项） | 82 | 0 |

边界矩阵覆盖候选150/151/300/301/400/401/1000与占用0/300/301/400/401，原始槽位两端、SQL原生等价而Python标准化不等的字符串、正式自身排除与草稿/待审批不排除、坏JSON/状态、缺失及结束事务、填空不覆盖已有序列号和来源ID映射。已有完整证据且未受后续测试文件增补影响的5组回归直接复用，没有重复运行。

完整命令/工作目录/退出码/输出见本区 `.runtime/archive-serial-performance/command-results.json`。统一调用前缀：

```sh
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PMS_CONFIG_FILE=/dev/null DB_DIALECT=sqlite SQLITE_DB_PATH=:memory: /Users/jin/Code/PMS/backend/.venv-security312/bin/python
```

序列号完整契约必须从工作区根目录运行 `backend/tests/archive_serial_unique_contract.py`；其夹具依赖根目录相对路径。其他上述检查从 `backend/` 运行 `tests/<name>.py`。路径问题已通过正确目录重跑解决，无源代码/夹具改动。

### 已知历史夹具问题

`offline_archive_merge_contract` 旧夹具 `existing()` 在插入正式档案前不取身份锁，本批试跑53项出现17个错误，发生于测试布置阶段、未进入批量函数。用原基线7a8的完整serial服务源码在单独进程重放代表用例，同样触发 `ARCHIVE_IDENTITY_LOCK_REQUIRED`，证据 `legacy-merge-baseline.log`。原已接受的32组清单未包括这项旧测试。本批未弱化锁或扩改历史夹具；新增实际 `build_import_plan` 测试用正确锁流程覆盖直接调用的填空保护与冲突来源映射。82项通过不包括该旧套件，不能表述为全部历史测试通过。

### SQL与本机计时

150同块比较的离线MSSQL SQL从750绑定/298个UNION ALL降为300绑定/149个UNION ALL；语句数量保持1条。12组矩阵和单独预算用例共13组测量，完整原文分别在 `before-metrics.json`、`after-metrics.json`，摘要在 `metrics-summary.json`，代表SQL及绑定在 `before-pair.sql` / `after-pair.sql` 与配套params文件。

| 单次本机样本 | 原函数SQLite秒 | 改后SQLite秒 |
| --- | ---: | ---: |
| 同块150预算用例 | 0.018384 | 0.014164 |
| 1000候选/0占用 | 0.190685 | 0.196063 |
| 1000候选/401占用 | 0.294046 | 0.246089 |

这是一轮本机样本，存在波动，不能概括为所有规模提速。另存MSSQL/SQLite离线编译、SQLite客户端执行/取数，以及包含Python校验和探针开销的剩余时间；剩余时间不是纯构造时间，客户端执行/取数不是SQL Server服务端耗时。

R3原生150用例总耗时5.267秒并非已分离的函数内部耗时。重复展开输入是已确认的SQL体积问题，尚不能证明其为原生超时唯一根因。没有放宽三秒门槛，也没有声称SQL Server 2017性能验收通过。

## 固定字节复审与下一接点

独立只读复审 `serial_perf_review` 核对以上两个文件SHA、唯一调用方、边界与证据，Critical/Important/Minor均0；没有修改文件/索引/HEAD，没有重跑已完成测试。报告为 `independent-review.json`。本地提交后总控可按准确提交及哈希接下一独立审查；提交号和最终清单由私有 `delivery.json` 固定，避免说明自引哈希。

维护线需在原生验证另获具体批准后，将这一业务增量纳入固定候选，复用其原有原生探针而不修改门槛，继续验证首个150及后续规模/占用/失败关闭/回放/恢复兼容性。任何原生连接、数据库/身份/备份操作与正式发布均不在本批权限内。当前仅本地候选交付，未上线。
