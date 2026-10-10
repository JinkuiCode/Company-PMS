# 线下档案同号补充与枚举合并实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline to implement this plan task-by-task.

**Goal:** 执行2026-10-09批准的枚举映射及空值补齐规则，支持同号补充和非同号新增的原子批次。
**Architecture:** 在现有固定V4文件读取、签名预检及批次服务中增加明确的同号补充模式；以服务器生成的目标快照绑定预检版本。明细保存补充前值，回退区分新增与补充。
**Tech Stack:** FastAPI / SQLAlchemy / Vue3 / SQLite临时库，目标MSSQL。

## Global Constraints
- 复用工作区codex/pms-offline-archive，不修改共享采购报表分支。
- V4文件和3024个编号保持不变，原始值保留在原文件；映射只按批准的89项到64项目标规则进行，疑点保留原值。
- 同号档案只补空白；名称冲突保留线上，身份、产品线、金蝶关联、同步策略及业务引用保持；不触发ERP。
- 正式导入前重新预检，不把9月24日的318/2706数量硬编码为当前数据库事实。
- 初始开发阶段不实际升级/导入；后续独立维护窗口已另行批准并执行。金蝶业务写入、GitHub推送/master合并仍不在本轮范围。

## Task 1: 批准的枚举映射
Files: backend/app/services/offline_archive_enum_mapping.py(new), offline_archive_workbook.py, enum_registry.py, models/init_db.py; tests/offline_archive_merge_contract.py(new).
- [x] RED：统一同义机型及单位，保留6.3/8、Single、辅机、给；映射全覆盖89项且64个目标；重复初始化不恢复禁用选项或复用数字值。
```python
self.assertEqual(normalize_offline_enum('quantity_unit','EA'),'个')
self.assertEqual(normalize_offline_enum('machine_model','6.3/8吋兼容CassetteType'),'6.3/8吋兼容CassetteType')
```
- [x] 实现固定服务端映射，升级时一次性准备目标枚举；复用已有稳定数字值，保留停用和历史引用。后续升级不重新补回删改项。
- [x] GREEN：运行新增契约及原workbook/approval/enum契约。

## Task 2: 同号预检与原子补充
Files: schemas/offline_archive.py, services/offline_archive_import.py, services/offline_archive_approval.py, models/archive_import.py, services/offline_archive_migration.py, services/database_revision.py.
- [x] RED：线上身份与13条冲突名保留、空名称和其他空字段补齐、0非空不覆盖；并发更改/新增冲突拒绝；失败无半批；新旧记录均零ERP任务。
```python
sealed = bind_existing_targets(db, payload)
result = apply_import(db,sealed,user_id,scope)
self.assertEqual((result['created'],result['updated']),(1,1))
```
- [x] 签名覆盖同号模式及目标快照，应用时按顺序加锁重新检查；序列号按最终写入值校验，不错误拦截同一档案自己的序列号。
- [x] 回退新增仅删除未修改未引用未同步记录；补充仅恢复白名单字段的前值，已有项目/ERP历史关系允许保留；记录变更后整批阻止回退。
- [x] 为批次明细增加操作类型及前值，独立幂等升级并提高数据库版本；升级测试覆盖旧表和重复执行。

## Task 3: 页面、回归及记录
Files: frontend/src/views/project/OfflineArchiveTools.vue, OfflineArchiveSource.vue, ProjectArchive.vue; docs/金蝶第三方应用对接SOP.md, change.md, docs/releases/PMS线下档案合并验收记录-20261009.md.
- [x] 页面预检显示新增/补充/保持不变数量，导入结果明确同号补充，已有来源记录也能查询原表来源；复用既有样式和控件。
- [x] 前端标准风格、列表、系统一致性、档案筛选、字段目录、枚举和相关导入契约及build；后端数据库升级、字段治理、权限、队列回归。
- [x] 使用V4和保密的只读快照在临时库演练混合导入、幂等及回退；确认总量、规则、来源和零ERP任务。
- [x] 完成代码审查和当前版本验证，记录change.md及SOP。交付本地开发结果及发布边界。

## 执行结果

2026-10-09本地实施和上述验证已完成，验收记录见 ../../releases/PMS线下档案合并验收记录-20261009.md。
64项目标包含全部19条疑点原值，替代初步63项建议。代码审查指出的锁后幂等返回已修复并回归。
生产发布、数据库实际升级及正式导入、GitHub推送/master合并保持独立批准边界，不包含在上述完成勾选内。

## 正式导入准备（报表完成后追加，2026-10-09）

- [x] 将已完成报表602a150整合到既有档案工作区，保留紧凑UI与两类迁移。
- [x] 补测旧报表菜单227/228占用场景；新档案按钮改为按权限代码分配编号，原报表授权保留，撤权不回补。
- [x] 当前整合版28组后端、19组前端、构建及4组浏览器流程通过，固定V4全量演练通过。
- [x] 生产服务器就地只读预检，形成具体执行与回退清单；本次维护窗口现已由用户批准；实际数据库备份及独立升级/发布结果见执行记录。
- [x] 固定本地整合提交3a83a75并制作校验过的源码/构建发布包。
- [x] 用户明确批准本次维护窗口及配套历史保存/回滚范围。
- [x] 程序/配置/前端/Git历史备份已保存并校验，原有940条档案核对基线留在服务器。
- [x] 现场独立升级凭据输入，完整COPY_ONLY/CHECKSUM备份及RESTORE VERIFYONLY校验完成。
- [x] 独立升级数据库、发布固定程序并通过服务健康、业务基线、配置及配套恢复材料复验。
- [x] 真实浏览器登录、档案/导入按钮及采购报表只读查询复验。
- [x] 独立批准仅档案导入接口请求上限4m及一次性SYSTEM加载；原字节备份/显式原代理/平滑加载/限定配置差异验收完成，临时任务已删除。
- [x] 批准V4实时签名预检、正式原子导入和零ERP写入验收，更新SOP及实际结果。

正式执行记录：../../releases/PMS线下档案期初导入执行记录-20261009.md。
