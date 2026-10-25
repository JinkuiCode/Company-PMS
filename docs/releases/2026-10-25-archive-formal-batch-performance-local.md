# C3B正式档案查重行集本地候选

仅替换 `identity_batch_conflicts` 中MSSQL正式表JOIN的候选行集，由150路UNION ALL改为命名VALUES派生表。SQLite、占用比对、跨块及前批自块CTE保持。该增量已完成本机验证与固定字节复审，原生三秒门槛待维护复验。

## 批准与现场证据

沿用 `call_4fc89729a1974c7bb57d81641cb20599` 的独立性能实施及本地提交批准；`call_15d4c42d8f604864ba6d71a0886f61d4` 明确“只暂停数据补全，已批准的性能修复继续”。2026-10-25总控人类消息 `01a1708b-9004-7730-a834-fa5fd018efaa` 和事件 `PMS-COORD-C3B-PERFORMANCE-OWNER-20261025-01` 要求同范围接续。数据补全、61负责人回写和项目进度不在本批范围。

基线 `3b657774ec9ce4cc4341ebe18e476f9b91e74dbe`，独立分支 `codex/archive-serial-performance-20261023`。业务及性能契约由本线单写，维护只写其验证/发布工具。无真实SQL/ERP连接、部署、合并或推送授权；本批均未执行。

维护固定原件经本线只读核对SHA：
- namespace JSON：`121f632114db2f3d0e142bfb17f1b56d14043229c0188bbfe07053f79378f168`。
- query-shape-analysis.json：`ec550c0471043c5a47e84994d7c5cdb13ba57f03671d2339fde88208b9951abe`。
- summary.json：`5fedeedb0e84a25a50590fd3430c1ea341b3938ba3a2af9e62b786603aa607db`。

C3B native首个150/0批次，函数内部3.151976088秒超过3秒，整用例3.212秒。6条SQL客户端execute中，两条450参数的正式JOIN分别1.471565560与1.531620148秒，合计3.003185708秒。前批self-CTE仅0.021634500秒。客户端execute包含驱动、网络及服务器工作，不能据此断定服务器纯执行或编译根因。现场已停止；本批不消费原现场时隙，不修改固定回执或原生探针。

## 单一假设与最小变化

本地用相同150个双字段提案、SQLAlchemy 2.0.37、pyodbc qmark编译，精确复现现场两个慢SQL SHA。假设：正式JOIN的150路UNION输入造成过大的执行路径开销；只压缩这两条语句的行集表示，再由原生复验判定实际耗时。

三列分别声明 `Integer / NVARCHAR(64) / Integer`；包括NULL在内的archive_id继续显式Integer绑定。150行仍为450个绑定参数，所有原值一致，没有新增CAST、截断或字面量插值。正式字段置于等号左侧，继续采用列原生排序规则；`archive_id IS NULL OR formal.id != archive_id` 逐提案自身排除保持。所有草稿/待审批占用、坏JSON/状态失败关闭及身份锁校验仍先执行，锁持有至原外层事务提交/回滚。150/300块大小及原始槽位不变。

| 正式JOIN | 旧字节 | 新字节 | 旧/新参数 | 旧/新UNION ALL |
| --- | ---: | ---: | ---: | ---: |
| project_code | 8585 | 1932 | 450 / 450 | 149 / 0 |
| serial_no | 8582 | 1929 | 450 / 450 | 149 / 0 |

新qmark SQL SHA分别为 `176b4b30e341da3788af7d0fdb7ecc4e456b79adfdf1ed1472ffe386aa7173f3` 与 `65bda2fe84bfa597f990556f81fb54c0d8afc00af36643b419d130bd55f24591`。相同150提案6条SQL中，除index2/4正式JOIN外，其余4条SQL及参数完全一致。

唯一生产调用方 `offline_archive_reconciliation.build_import_plan` 不需改动。没有表、索引、revision、依赖、API、权限或业务规则变更。

SQLAlchemy既有版本已实编译支持命名VALUES；不使用较新版本的Values.cte。SQL Server允许在FROM中使用VALUES派生表，参考[Microsoft语法说明](https://learn.microsoft.com/en-us/sql/t-sql/queries/table-value-constructor-transact-sql?view=sql-server-ver15)及[SQLAlchemy values API](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.values)。文档支持不替代现场验证。

## 受影响验证

既有Python 3.12.14 / SQLAlchemy 2.0.37；应用测试清空继承环境、`PMS_CONFIG_FILE=/dev/null`，只用私有临时SQLite。新定向测试先RED：8个size子例都仅因旧SQL没有VALUES而失败，退出1；布置及语义检查先通过。修改后完整8项退出0；受影响的MSSQL代理契约2项退出0。

新增规模1/150/151/300/301/400/401/1000，检查：
- NULL/非NULL档案ID及逐行自身排除，含禁用正式档案。
- 原始槽位、每个150块精确参数数及绑定类型。
- 列collation的下划线等价、中文/Unicode/全角/引号值保持绑定。
- MSSQL新分支与SQLite既有分支的实际查询结果相同。
- 既有占用300/301/400/401、失败关闭、锁及真实build_import_plan测试继续通过。

既有MSSQL代理原在SQLite执行投影；SQLite不接受VALUES派生表的命名列别名语法，因此测试夹具仅将固定formal_candidates的slot/key/archive_id映射到SQLite column1/2/3，保留所有表达式和参数顺序。实际MSSQL语法、计划、类型推断及排序规则仍必须现场验证；该代理不模拟服务器性能。

原12组SQLite矩阵逐语句对照旧固定候选，SQL及绑定数据完全一致，据此复用未变的namespace6、serial_import1、offline_import16、offline_performance36、serial_unique14，共73执行项的原完整证据。本轮8+2与复用73合计83执行项适用通过，不重复已通过且未变的检查。旧offline_merge缺锁夹具问题继续按2026-10-23说明单列，不算作通过，也未扩改业务规避。

固定字节独立只读复审 `serial_perf_review`：Critical/Important/Minor均0；服务、测试和夹具哈希逐项匹配，未改工作区/索引/HEAD，未访问真实库/配置。复审与SQL对照、命令/工作目录/退出码/日志在本区 `.runtime/archive-serial-performance/c3b-20261025/`。

当前固定文件SHA：
- service：`8a214034fb7a76a9c51e12262a5d3f24072bc08f572577bb9ccc9fe6fb88e053`。
- MSSQL fixture：`a631d4571d4b6bac1a7ebbe0ad7028374c5301595cbdae44cd9c737448e2a5e3`。
- performance test：`8148a1a3cff6600bea28d5f017c4c4ecb33698388f719362b6c4b98dac1a4cf9`。

## 交付与下一接点

本地提交及5个文件精确清单由私有delivery.json固定，包含上述服务/两测试、本区change.md与本说明；不改维护工具和共享发布总账。交总控做定向候选复核及维护原生复验，保留三秒门槛及原有边界。不能把SQL缩短、离线编译、SQLite代理或83项适用检查通过表述为新候选的原生性能或正式兼容验收通过。
