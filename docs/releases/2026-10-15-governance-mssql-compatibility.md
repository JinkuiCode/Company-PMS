# 治理候选MSSQL兼容修复记录

日期：2026-10-15。用户独立批准仅本地修复、测试、提交和重新打包，保留旧候选，不连接正式服务器、不升级实际库、不改授权、不合并/推送或发送通知。

## 原因与调整

当前固定依赖SQLAlchemy2.0.37的MSSQL dialect未实现get_unique_constraints。原候选在治理升级核验和启动结构检查中无条件调用，都会遇到NotImplementedError。本机通过模型元数据反射夹具及真正的MSSQL dialect方法复现；没有连接数据库或读取业务数据。原ZIP及摘要保持，原包不应进入正式部署。

本次只修改governance_migration.py的唯一键读取：MSSQL通过绑定schema/table查询sys目录，按index_id组合并按key_ordinal排序，拒绝禁用、假设、过滤及非唯一索引，排除主键和包含列。SQLite保留原反射方式。缺失键和目录异常仍失败；没有跳过校验、改DDL或改版本标记。数据库目标仍2026-10-15-governance-01，应用候选仍v1.0.0/7项更新。

## 验证

- RED：正例命中原未实现方法，1测试失败，失败原因符合根因。
- GREEN：governance_upgrade_contract.py共16项通过（原9+新7，含5类无效索引子场景）。使用隔离SQLite关系型sys夹具真实执行SELECT，唯一约束反射保持真实MSSQL未实现方法；验证引用schema使用绑定、组合键顺序、不同索引不能合并、包含列不能凑键、缺失键拒绝和查询异常拒绝。
- database_upgrade_contract.py、runtime_release_contract.py（4项）、server_release_contract.py（6项）均退出0。命令与完整结果见本机outputs/governance-mssql-compatibility-20261015/{tdd-results,check-results}.json。
- 独立只读复核无阻断，确认没有弱化唯一性门禁；复核者在空配置隔离环境独立运行16项退出0。
- 没有改前端源码，复用同版本必需契约和页面验收；重新打包仍必须从新提交重建前端。

## 当前边界

代码与隔离契约已完成；新提交和固定包生成结果在随后追加。当前验证不能代替真实MSSQL2017现场升级与恢复演练，也不代表正式部署或真实企业邮件验收。当前Mac仍原受控服务，本批不重启。
