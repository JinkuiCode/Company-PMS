# 151项边界查重NULL绑定修复（本地候选）

本批只消除MSSQL批量候选中缺失档案ID的Python None参数，改为 `CAST(NULL AS INTEGER)`。非空ID、key和slot继续绑定，SQLite不变；数据补全及项目进度继续暂停。已完成本地定向验证与固定字节复审，未在真实SQL Server测量新耗时。

## 授权、版本和范围

沿用用户 `call_4fc89729a1974c7bb57d81641cb20599`、`call_15d4c42d8f604864ba6d71a0886f61d4` 及总控 `PMS-COORD-PERFORMANCE-151-OWNER-20261026-01` 的同范围修复、独立本地提交授权。基线 `09178b167f107e9abf5321fdbf0c72b69263779f`，原工作区和 `codex/archive-serial-performance-20261023` 分支继续，不新建通道。

唯一生产改动为 `identity_batch_conflicts` 当前块的ID表达式构造：MSSQL的缺失ID用带整数类型的SQL NULL，其余仍Integer绑定。当前块的UNION投影与正式VALUES共享该表达式。150/300分块、原始槽位、列collation、每行排除自身、所有占用/坏JSON状态、锁与外层事务保持。没有sentinel替代、key截断、配置、依赖、表、索引、revision、API、权限、维护探针或发布工具变化；不合并、不推送、不部署。

服务SHA `c7f77fc4ac271b7669a866bd2a098090e4443182be0d2f1810de56d48301f103`；测试SHA `b0ea820e5ee4eb1e15b4060630167552424876625539ddf3fb2bc32e250d43df`。其余提交项为本说明及本区change.md；精确提交和清单由私有delivery.json固定。

## 可证定位和单一假设

维护原件 `probe-namespace-remaining-PMS_C3B_SYN_20261023.json` SHA `03bee71bb3a46ad0de479cd9e39ad1d6e0074c6fc67217e0bb769642965fc299`。实际加载09178服务SHA8a214034匹配；150/0函数内部2.949322秒，151/0内部3.996595秒。该次原始 `outcome_uncertain=true` 保留，关闭连接/进程不等于已证实测试事务回滚。本线不访问真实库或改回执。

离线相同提案精确匹配150的6条、151的10条SQL SHA及参数数。151增加4条查询：尾块编码正式查重3参数、跨块452参数、尾块序列号正式查重3参数、尾块self2参数。跨块左侧沿用150行三列c，右侧1行两列other，合计450+2；其中150个archive_id参数全为None且未参与pair比较。两个450参数正式JOIN也各带150个None。三条慢语句execute约1.425/1.351/1.083秒，无None的自块300参数约0.017秒。冗余NULL绑定是静态可证的代码问题，时间关联不是驱动耗时分项证明。

已核对固定site_preflight.py:214在首连前要求pyodbc 5.2.0，原门禁通过；原transport记录ODBC17.03.0001。官方[pyodbc 5.2.0 params.cpp](https://github.com/mkleehammer/pyodbc/blob/5.2.0/src/params.cpp#L516-L524)的None路径经GetNullInfo/GetParamType可能调用SQLDescribeParam；[setinputsizes覆盖发生于后续绑定](https://github.com/mkleehammer/pyodbc/blob/5.2.0/src/params.cpp#L1091-L1102)。由此形成可检验假设：移除Python None参数可避开该路径；当前没有现场驱动trace或服务端计划，不能断言它就是主要耗时根因。

| 同一合成调用 | 查询数（不变） | 改前None绑定总数 | 改后None绑定 | 参数变化 |
| --- | ---: | ---: | ---: | --- |
| 150/0 | 6 | 300 | 0 | 两正式JOIN各450至300 |
| 151/0 | 10 | 452 | 0 | 两大正式JOIN各450至300、尾块各3至2、跨块452至302 |

其余非空绑定值及顺序逐项保持；本来没有None的SQL全字节保持，self-CTE不变。NULL显式写入SQL使两大正式SQL字节1932/1929增至4932/4929、跨块8584增至11584；这是消除驱动空参数绑定，不是继续追求更短文本或更少查询，不据此声称已提速。

## 当前验证与复用

既有Python3.12.14/SQLAlchemy2.0.37；清空继承环境、PMS_CONFIG_FILE=/dev/null，仅私有临时SQLite。新增151项/占用0及301的测试先RED，两个子例均仅因仍发送None失败；改后完整9项及MSSQL契约2项退出0。覆盖混合NULL/非NULL、精确参数类型/数量、原生等价关系、Unicode/引号、自身排除、原始槽位、规模及占用分块、失败关闭、锁和实际导入计划映射。

原12组SQLite矩阵的SQL/绑定与09178逐项完全一致，据此复用未变namespace6、serial_import1、offline_import16、offline_performance36、serial_unique14，共73执行项；本轮11加复用73合计84适用执行项通过。旧offline_merge缺锁夹具问题仍单列，不算通过，不扩改业务规避。

固定两文件独立只读复审C0/I0/M0；未修改索引/分支或访问真实库。原始SQL、参数、编译/客户端执行/取数/含Python残差的本机测量、命令/目录/退出码/日志和复审，位于本区 `.runtime/archive-serial-performance/151-20261026/`。这些本机检查不模拟真实服务器耗时。

## 三秒来源及上线影响分类

按用户新增要求 `01a17591-b9b8-7a83-9ab9-d635ee0f7977`，区分技术性能偏差与上线硬阻塞：
- 目前可追溯到维护2026-10-22原生合成探针的 `duration<=3` 技术断言，后继工具沿用。原工具未跟踪于Git，现有材料不能确认最初具体制定者；未找到用户直接指定三秒、业务SLA或容量模型。生产函数和导入API无三秒自动拒绝逻辑。
- 四秒是带刻意重复序列号的151条合成namespace检查，不是完整成功导入或普通单条保存耗时。唯一生产调用为期初导入build_import_plan；普通保存走ensure_serial_available。apply未提前返回时最多两次preview和一次直接build，不能以单次四秒替代完整时延。
- 与普通保存共用事务身份锁，锁申请超时1000ms，重叠执行可能等待/冲突；没有当前生产并发等待或用户失败证据。1000/1000本版未运行，规模耗时和实际锁占用影响未知，不线性推算，也不宣称一定危险或一定可接受。
- 保留原始三秒偏差，不伪造达标，不将该数值作为自动发布否决。独立已批准的备份恢复/兼容继续并行；唯一性、权限、事务正确性、适用备份恢复/升级及固定候选一致性等真实未过项分别作为硬阻塞处理。未知规模/占锁影响据实披露，由总控协调实际发布范围与后续验证。

函数内部计时包围整个调用；cursor事件只覆盖客户端execute，排除SQLAlchemy事前编译和事后fetch，但包含驱动/网络/服务器工作；外层case还含布置/清理等。三者不能混用，SQLDescribeParam机制与本次现场时长归因分开。

## 后续接点

固定本地候选交总控做定向增量复核，维护按最新失败分类并行完成独立备份恢复和适用现场验证。本线未更改原生探针或请求额外凭据、数据库、授权、连接。若新候选现场仍慢，应依据新证据讨论整体查询/占锁预算，不继续盲试同类形状参数；本批不把后续性能优化自动扩大为新架构。
